import os
import re
import asyncio
import base64
import traceback
import random
from typing import List, Optional, Any, Dict
from datetime import timedelta
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from imap_tools import MailBox
import email.utils
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import motor.motor_asyncio
from bson import ObjectId
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email import encoders
from email.mime.base import MIMEBase
import time
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
from agents.run import RunConfig
from passlib.context import CryptContext
from jose import JWTError, jwt

load_dotenv()

# --------------------
# Config
# --------------------
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "email_agent_db")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_DELAY = float(os.getenv("SMTP_DELAY", 15.0))  # seconds between emails in the blocking send loop
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")  # 🔐 change in production
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 30))  # 30 days

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not set. Email rephrasing will not work.")

# --------------------
# FastAPI + Mongo
# --------------------
app = FastAPI(title="Email Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[MONGODB_DB]
templates_col = db["templates"]
leads_col = db["leads"]
email_accounts_col = db["email_accounts"]
mail_logs_col = db["mail_logs"]
users_collection = db["users"]

# --------------------
# Authentication
# --------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await users_collection.find_one({"email": email})
    if user is None:
        raise credentials_exception
    return user

# --------------------
# Utilities
# --------------------
EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if not email:
        return False
    return re.match(EMAIL_REGEX, email) is not None

def oid(id_str: str) -> ObjectId:
    try:
        print(f"Converting to ObjectId: {id_str}")  # Debug
        return ObjectId(id_str)
    except Exception as e:
        print(f"Invalid ObjectId: {id_str}, error: {e}")  # Debug
        raise HTTPException(status_code=400, detail=f"Invalid id: {id_str}")

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = {**doc}
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

# --------------------
# Pydantic models
# --------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: EmailStr

class TemplateIn(BaseModel):
    name: str = Field(..., example="Default")
    subject: str = Field(..., example="Hello from Acme")
    content: str = Field(..., example="Hi {First Name}, ...")

class TemplateOut(TemplateIn):
    id: str
    created_at: datetime
    user_id: str
    
class UnreadEmail(BaseModel):
    sender_email: str
    recipient_email: str
    subject: str
    time: str
    preview: str

class LeadIn(BaseModel):
    company_name: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None  # This uses EmailStr which provides basic validation
    owner_name: Optional[str] = None

    @validator('email', pre=True, always=True)
    def validate_email(cls, v):
        if v is None or v == '':
            return None
        if not is_valid_email(v):
            return None  # Or raise validation error if you prefer
        return v

class LeadOut(LeadIn):
    id: str
    mail_sent: bool = False
    created_at: datetime
    user_id: str

class Attachment(BaseModel):
    filename: str
    content: str  # base64 encoded content

class EmailAccountIn(BaseModel):
    email: EmailStr
    password: str = Field(..., description="App password for the email account")
    sender_name: Optional[str] = None
    is_active: bool = True

class EmailAccountOut(EmailAccountIn):
    id: str
    created_at: datetime
    emails_sent_today: int = 0
    last_reset_date: datetime
    user_id: str

class SendEmailsPayload(BaseModel):
    template_id: str
    lead_ids: Optional[List[str]] = None
    attachments: Optional[List[Attachment]] = None
    email_account_ids: Optional[List[str]] = None  # Specific accounts to use

class RephraseOutput(BaseModel):
    rephrased_email: str

class RephraseRequest(BaseModel):
    template_id: str
    content: str

class ScrapeRequest(BaseModel):
    query: str
    max_businesses: int

class ScrapeResponse(BaseModel):
    status: str
    message: str
    scraped_count: int = 0
    total_requested: int = 0

class Token(BaseModel):
    access_token: str
    token_type: str

# --------------------
# Email Rephrase Agent Setup
# --------------------
def setup_rephrase_agent():
    if not GEMINI_API_KEY:
        return None
    
    try:
        external_client = AsyncOpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=30.0
        )

        model = OpenAIChatCompletionsModel(
            model='gemini-2.0-flash',
            openai_client=external_client
        )

        return Agent(
            name='Email Rephrase agent',
            instructions='You are email rephrase agent. You rephrase the given email in human wordings. Do not change the meaning and just change the wordings.',
            model=model,
            output_type=RephraseOutput
        )
    except Exception as e:
        print(f"Failed to initialize rephrase agent: {str(e)}")
        traceback.print_exc()
        return None

rephrase_agent = setup_rephrase_agent()

async def check_unread_emails(user_id: str, max_emails: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent emails (read or unread) for all email accounts of a user"""
    print(f"🔍 Starting recent email check for user_id: {user_id}, max_emails: {max_emails}")
    
    # Get all email accounts for the user
    email_accounts = await email_accounts_col.find({
        "user_id": user_id,
        "is_active": True
    }).to_list(length=None)
    
    print(f"📧 Found {len(email_accounts)} active email accounts for user")
    for i, acc in enumerate(email_accounts):
        print(f"  Account {i+1}: {acc.get('email', 'No email')} (ID: {acc.get('_id', 'No ID')})")
    
    recent_emails = []
    emails_lock = threading.Lock()
    
    def process_email_account(account):
        nonlocal recent_emails
        account_email = account.get("email", "Unknown")
        print(f"🔎 Checking account: {account_email}")
        
        try:
            print(f"🔄 Connecting to IMAP server for {account_email}")
            with MailBox("imap.gmail.com").login(account["email"], account["password"], "INBOX") as mailbox:
                print(f"✅ Successfully connected to {account_email}")
                
                # Fetch recent emails (read + unread)
                emails_found = 0
                for msg in mailbox.fetch(criteria="ALL", limit=max_emails, reverse=True):  
                    emails_found += 1
                    sender_name, sender_email = email.utils.parseaddr(msg.from_)
                    email_time = msg.date.strftime("%d-%m-%Y %I:%M:%p") if msg.date else "Unknown"
                    
                    # Get first 100 chars as preview
                    preview = msg.text or msg.html or ""
                    if preview:
                        preview = preview[:100] + "..." if len(preview) > 100 else preview
                    
                    with emails_lock:
                        recent_emails.append({
                            "sender_email": sender_email,
                            "recipient_email": account["email"],
                            "subject": msg.subject or "No Subject",
                            "time": email_time,
                            "preview": preview,
                            "is_unread": "\\Seen" not in msg.flags  # mark unread flag
                        })
                    
                    print(f"📩 Found email from {sender_email} to {account_email} at {email_time} | Flags: {msg.flags}")
                
                if emails_found == 0:
                    print(f"ℹ️ No emails found for {account_email}")
                else:
                    print(f"✅ Found {emails_found} recent emails for {account_email}")
                    
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error checking emails for {account_email}: {error_msg}")
            if "Authentication failed" in error_msg:
                print(f"🔐 Authentication issue with {account_email}. Check password/app password.")
            elif "connection failed" in error_msg.lower():
                print(f"🌐 Connection issue with {account_email}. Check network/IMAP settings.")
            elif "SSL" in error_msg:
                print(f"🔒 SSL issue with {account_email}. Check port/SSL configuration.")
    
    # Create threads for each email account
    threads = []
    print(f"🧵 Creating threads for {len(email_accounts)} email accounts")
    
    for account in email_accounts:
        thread = threading.Thread(target=process_email_account, args=(account,))
        thread.start()
        threads.append(thread)
        print(f"➡️ Started thread for account: {account.get('email', 'Unknown')}")
    
    # Wait for all threads to complete
    print("⏳ Waiting for all email accounts to be checked...")
    for i, thread in enumerate(threads):
        thread.join(timeout=30)
        if thread.is_alive():
            print(f"⏰ Thread {i+1} timed out after 30 seconds")
        else:
            print(f"✅ Thread {i+1} completed successfully")
    
    # Sort by time (newest first) and limit to max_emails
    print(f"📊 Sorting {len(recent_emails)} found emails by time")
    recent_emails.sort(key=lambda x: x.get("time", ""), reverse=True)
    result = recent_emails[:max_emails]
    
    print(f"🎉 Recent email check completed. Returning {len(result)} emails")
    return result

# --------------------
# Email Account Management
# --------------------
async def get_available_email_accounts(user_id: str) -> List[Dict[str, Any]]:
    """Get all active email accounts for a specific user (no daily limit checks)"""
    # Get all active accounts
    cursor = email_accounts_col.find({
        "user_id": user_id,
        "is_active": True
    })
    
    accounts = []
    async for acc in cursor:
        accounts.append(acc)
    
    return accounts

async def update_email_account_usage(account_id: ObjectId, emails_sent: int):
    """Update the count of emails sent for an account - now a no-op"""
    # No longer tracking usage, so this function does nothing
    pass

# --------------------
# Authentication Endpoints
# --------------------
@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    print(f"Login attempt for username: {form_data.username}")  # Debug
    
    user = await users_collection.find_one({"email": form_data.username})
    print(f"User found: {user}")  # Debug
    
    if not user:
        print("User not found in database")  # Debug
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Debug password verification
    print(f"Stored hash: {user.get('password')}")  # Debug
    password_valid = verify_password(form_data.password, user["password"])
    print(f"Password valid: {password_valid}")  # Debug
    
    if not password_valid:
        print("Password verification failed")  # Debug
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    access_token = create_access_token({"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/signup", response_model=UserOut)
async def signup(user: UserCreate):
    # Check if user already exists
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    user_dict = {
        "email": user.email,
        "password": hashed_password,
        "created_at": datetime.utcnow()
    }
    
    result = await users_collection.insert_one(user_dict)
    return {"id": str(result.inserted_id), "email": user.email}

# --------------------
# Email sending helpers
# --------------------
def build_message(
    sender_email: str, 
    recipient_email: str, 
    subject: str, 
    body: str, 
    sender_name: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None
) -> str:
    msg = MIMEMultipart()
    if sender_name:
        msg["From"] = formataddr((sender_name, sender_email))
    else:
        msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    
    # Add body
    msg.attach(MIMEText(body, "plain"))
    
    # Add attachments
    if attachments:
        for attachment in attachments:
            try:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(base64.b64decode(attachment["content"]))
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={attachment['filename']}",
                )
                msg.attach(part)
            except Exception as e:
                print(f"Failed to attach {attachment['filename']}: {str(e)}")
                continue
    
    return msg.as_string()

def send_bulk_via_smtp_blocking(
    email_accounts: List[Dict[str, Any]], 
    messages: List[Dict[str, Any]], 
    delay: float = 1.0
) -> Dict[str, Any]:
    """Send emails using multiple accounts with round-robin distribution (no daily limits)"""
    sent = []
    failed = []
    
    # Create SMTP connections for each account
    connections = {}
    for acc in email_accounts:
        try:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(acc.get("smtp_host", SMTP_HOST), acc.get("smtp_port", SMTP_PORT), context=ctx)
            server.login(acc["email"], acc["password"])
            connections[str(acc["_id"])] = server
        except Exception as e:
            print(f"Failed to connect with account {acc['email']}: {str(e)}")
            # Remove failed account from pool
            email_accounts = [a for a in email_accounts if a["_id"] != acc["_id"]]
    
    if not connections:
        raise Exception("No valid email accounts available")
    
    # Round-robin distribution of emails to accounts
    account_ids = list(connections.keys())
    current_account_index = 0
    
    for i, m in enumerate(messages):
        if not email_accounts:
            break  # No accounts left
            
        # Select next account in round-robin fashion
        account_id = account_ids[current_account_index]
        account = next((acc for acc in email_accounts if str(acc["_id"]) == account_id), None)
        
        if not account:
            continue
            
        try:
            msgstr = build_message(
                account["email"], 
                m["to"], 
                m["subject"], 
                m["body"], 
                sender_name=account.get("sender_name"),
                attachments=m.get("attachments")
            )
            connections[account_id].sendmail(account["email"], m["to"], msgstr)
            sent.append({"email": m["to"], "account_id": str(account["_id"])})
            print(f"Sent email to {m['to']} using account {account['email']}")
        except Exception as e:
            error_msg = str(e)
            print(f"Failed to send to {m.get('to')} using account {account['email']}: {error_msg}")
            failed.append({"email": m.get("to"), "error": error_msg, "account_id": str(account["_id"])})
            
            # If connection failed, remove this account from pool
            try:
                connections[account_id].quit()
            except:
                pass
            del connections[account_id]
            email_accounts = [a for a in email_accounts if str(a["_id"]) != account_id]
            account_ids = list(connections.keys())
            if not account_ids:
                break
            current_account_index = current_account_index % len(account_ids)
        
        # Move to next account
        current_account_index = (current_account_index + 1) % len(account_ids)
        
        if delay and delay > 0:
            time.sleep(delay)
    
    # Close all connections
    for conn in connections.values():
        try:
            conn.quit()
        except:
            pass
    
    return {"sent": sent, "failed": failed}

async def mark_leads_sent(lead_ids: List[str], user_id: str):
    oids = []
    for lid in lead_ids:
        try:
            oids.append(ObjectId(lid))
        except Exception:
            continue
    if not oids:
        return
    await leads_col.update_many(
        {"_id": {"$in": oids}, "user_id": user_id}, 
        {"$set": {"mail_sent": True, "last_mailed_at": datetime.utcnow()}}
    )

async def background_send(template_id: str, lead_ids: List[str], user_id: str, attachments: Optional[List[Dict[str, str]]] = None, email_account_ids: Optional[List[str]] = None):
    tmpl = await templates_col.find_one({"_id": oid(template_id), "user_id": user_id})
    if not tmpl:
        return {"status": "template_not_found"}

    # Convert lead IDs to ObjectIds
    lead_object_ids = []
    for lid in lead_ids:
        try:
            if ObjectId.is_valid(lid):
                lead_object_ids.append(ObjectId(lid))
        except Exception:
            continue
    
    if not lead_object_ids:
        return {"status": "no_valid_leads"}
    
    q = {"_id": {"$in": lead_object_ids}, "user_id": user_id}
    leads_cursor = leads_col.find(q)
    leads = []
    async for l in leads_cursor:
        leads.append(l)

    messages = []
    valid_leads = []
    for l in leads:
        recipient = l.get("email")
        # Skip leads without email or with invalid email
        if not recipient or not is_valid_email(recipient):
            continue
        
        body = tmpl.get("content", "")
        first = l["owner_name"].split()[0] if l.get("owner_name") else ""
        body = body.replace("{First Name}", first)
        body = body.replace("{Company}", l.get("company_name", ""))
        subject = tmpl.get("subject", "")
        
        messages.append({
            "to": recipient, 
            "subject": subject, 
            "body": body,
            "attachments": attachments
        })
        valid_leads.append(l)

    if not messages:
        return {"status": "no_valid_recipients"}

    # Get available email accounts
    if email_account_ids:
        # Use specific accounts requested
        account_oids = [ObjectId(acc_id) for acc_id in email_account_ids if ObjectId.is_valid(acc_id)]
        email_accounts = await email_accounts_col.find({
            "_id": {"$in": account_oids},
            "user_id": user_id,
            "is_active": True
        }).to_list(length=None)
    else:
        # Use all available accounts for this user
        email_accounts = await get_available_email_accounts(user_id)
    
    if not email_accounts:
        return {"status": "no_valid_accounts", "message": "No active email accounts available"}

    result = await asyncio.to_thread(
        send_bulk_via_smtp_blocking, 
        email_accounts, 
        messages, 
        SMTP_DELAY
    )

    # Update tracking of sent emails
    sent_emails = [s["email"] for s in result.get("sent", [])]
    sent_lead_ids = [str(l["_id"]) for l in valid_leads if l.get("email") in sent_emails]
    if sent_lead_ids:
        await mark_leads_sent(sent_lead_ids, user_id)

    await mail_logs_col.insert_one({
        "template_id": template_id,
        "user_id": user_id,
        "sent_count": len(result.get("sent", [])),
        "failed": result.get("failed", []),
        "created_at": datetime.utcnow(),
        "had_attachments": bool(attachments),
        "accounts_used": [str(acc["_id"]) for acc in email_accounts],
        "total_leads_processed": len(leads),
        "valid_leads_count": len(valid_leads)
    })
    return result

# --------------------
# API Endpoints (All require authentication)
# --------------------
@app.post("/rephrase-email")
async def rephrase_email(request: RephraseRequest, current_user: dict = Depends(get_current_user)):
    print(f"Rephrase request received from user: {current_user['email']}")  # Debug
    print(f"Requested template ID: {request.template_id}")  # Debug
    
    if not rephrase_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVERAGE,
            detail="Rephrasing service not configured"
        )
    
    try:
        # Verify template exists first and belongs to user
        template = await templates_col.find_one({"_id": oid(request.template_id), "user_id": current_user["_id"]})
        print(f"Template lookup result: {template is not None}")  # Debug
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Run the rephrase agent
        result = await Runner.run(
            rephrase_agent,
            request.content,
            run_config=RunConfig(
                model=rephrase_agent.model,
                tracing_disabled=True
            )
        )
        
        rephrased_content = result.final_output.rephrased_email
        
        # Update the template in the database
        update_result = await templates_col.update_one(
            {"_id": oid(request.template_id), "user_id": current_user["_id"]},
            {"$set": {"content": rephrased_content}}
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template not updated"
            )
        
        return {
            "success": True,
            "rephrased_content": rephrased_content,
            "template": serialize_doc(template)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Rephrase error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rephrase email: {str(e)}"
        )

@app.get("/templates", response_model=List[TemplateOut])
async def get_templates(current_user: dict = Depends(get_current_user)):
    cursor = templates_col.find({"user_id": str(current_user["_id"])}).sort("created_at", -1)
    docs = []
    async for d in cursor:
        docs.append(serialize_doc(d))
    return docs

@app.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(template_id: str, current_user: dict = Depends(get_current_user)):
    t = await templates_col.find_one({"_id": oid(template_id), "user_id": str(current_user["_id"])})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return serialize_doc(t)

@app.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateIn, current_user: dict = Depends(get_current_user)):
    doc = payload.dict()
    doc["created_at"] = datetime.utcnow()
    doc["user_id"] = str(current_user["_id"])
    r = await templates_col.insert_one(doc)
    created = await templates_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.put("/templates/{template_id}", response_model=TemplateOut)
async def update_template(template_id: str, payload: TemplateIn, current_user: dict = Depends(get_current_user)):
    update_doc = {"$set": payload.dict()}
    res = await templates_col.update_one({"_id": oid(template_id), "user_id": str(current_user["_id"])}, update_doc)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    new = await templates_col.find_one({"_id": oid(template_id)})
    return serialize_doc(new)

@app.get("/leads", response_model=List[LeadOut])
async def get_leads(limit: int = 100, sent: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    query = {"user_id": str(current_user["_id"])}
    if sent is not None:
        query["mail_sent"] = sent
    else:
        query["mail_sent"] = False  # Default to only unsent leads
        
    cursor = leads_col.find(query).sort("created_at", -1).limit(limit)
    out = []
    async for d in cursor:
        doc = serialize_doc(d)
        doc.setdefault("mail_sent", False)
        out.append(doc)
    return out

@app.get("/leads/count")
async def leads_count(sent: Optional[bool] = None, current_user: dict = Depends(get_current_user)):
    query = {"user_id": str(current_user["_id"])}
    if sent is not None:
        query["mail_sent"] = sent
        
    count = await leads_col.count_documents(query)
    return {"count": count}

@app.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadIn, current_user: dict = Depends(get_current_user)):
    doc = payload.dict()
    doc["mail_sent"] = False
    doc["created_at"] = datetime.utcnow()
    doc["user_id"] = str(current_user["_id"])
    r = await leads_col.insert_one(doc)
    created = await leads_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.post("/send-emails")
async def send_emails(payload: SendEmailsPayload, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    try:
        template_obj = await templates_col.find_one({"_id": oid(payload.template_id), "user_id": str(current_user["_id"])})
    except HTTPException as e:
        raise e
    if not template_obj:
        raise HTTPException(status_code=404, detail="Template not found")

    lead_ids = payload.lead_ids or []
    if not lead_ids:
        cursor = leads_col.find({"user_id": str(current_user["_id"]), "mail_sent": False}).sort("created_at", 1).limit(100)
        lead_ids = []
        async for l in cursor:
            lead_ids.append(str(l["_id"]))

    if not lead_ids:
        return JSONResponse({"status": "no_leads_to_send"}, status_code=200)

    # Convert attachments to dict if they exist
    attachments = None
    if payload.attachments:
        attachments = [a.dict() for a in payload.attachments]

    background_tasks.add_task(
        background_send, 
        payload.template_id, 
        lead_ids, 
        str(current_user["_id"]),
        attachments, 
        payload.email_account_ids
    )
    return {"status": "queued", "leads_count": len(lead_ids)}

# --------------------
# Email Accounts Endpoints
# --------------------
@app.get("/email-accounts", response_model=List[EmailAccountOut])
async def get_email_accounts(active_only: bool = True, current_user: dict = Depends(get_current_user)):
    query = {"user_id": str(current_user["_id"])}
    if active_only:
        query["is_active"] = True
        
    cursor = email_accounts_col.find(query).sort("created_at", -1)
    accounts = []
    async for acc in cursor:
        accounts.append(serialize_doc(acc))
    return accounts

@app.get("/unread-emails", response_model=List[UnreadEmail])
async def get_unread_emails(max_emails: int = 10, current_user: dict = Depends(get_current_user)):
    """Get unread emails from all email accounts"""
    print(f"📨 API request for unread emails from user: {current_user['email']}")
    try:
        unread_emails = await check_unread_emails(str(current_user["_id"]), max_emails)
        print(f"✅ API request completed. Returning {len(unread_emails)} emails")
        return unread_emails
    except Exception as e:
        print(f"❌ API error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch unread emails"
        )

@app.post("/email-accounts", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_email_account(payload: EmailAccountIn, current_user: dict = Depends(get_current_user)):
    # Check if email already exists for this user
    existing = await email_accounts_col.find_one({"email": payload.email, "user_id": str(current_user["_id"])})
    if existing:
        raise HTTPException(status_code=400, detail="Email account already exists")
    
    doc = payload.dict()
    doc["created_at"] = datetime.utcnow()
    doc["smtp_host"] = SMTP_HOST
    doc["smtp_port"] = SMTP_PORT
    doc["user_id"] = str(current_user["_id"])
    
    r = await email_accounts_col.insert_one(doc)
    created = await email_accounts_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.put("/email-accounts/{account_id}", response_model=EmailAccountOut)
async def update_email_account(account_id: str, payload: EmailAccountIn, current_user: dict = Depends(get_current_user)):
    update_doc = {"$set": payload.dict()}
    res = await email_accounts_col.update_one({"_id": oid(account_id), "user_id": str(current_user["_id"])}, update_doc)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Email account not found")
    updated = await email_accounts_col.find_one({"_id": oid(account_id)})
    return serialize_doc(updated)

@app.delete("/email-accounts/{account_id}")
async def delete_email_account(account_id: str, current_user: dict = Depends(get_current_user)):
    res = await email_accounts_col.delete_one({"_id": oid(account_id), "user_id": str(current_user["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Email account not found")
    return {"status": "deleted"}

# --------------------
# Analytics Endpoints
# --------------------
@app.get("/analytics/daily-stats")
async def get_daily_stats(days: int = 30, current_user: dict = Depends(get_current_user)):
    """Get daily statistics for leads and emails for the current user"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    user_id = str(current_user["_id"])
    
    # Get daily lead counts
    lead_pipeline = [
        {"$match": {"user_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "leads_count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    # Get daily email counts from mail_logs
    email_pipeline = [
        {"$match": {"user_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "emails_sent": {"$sum": "$sent_count"},
            "emails_failed": {"$sum": {"$size": "$failed"}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    lead_stats = await leads_col.aggregate(lead_pipeline).to_list(None)
    email_stats = await mail_logs_col.aggregate(email_pipeline).to_list(None)
    
    # Convert to dictionaries for easier merging
    leads_dict = {stat["_id"]: stat["leads_count"] for stat in lead_stats}
    emails_dict = {stat["_id"]: stat["emails_sent"] for stat in email_stats}
    
    # Generate all dates in range
    all_dates = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        all_dates.append(date_str)
        current_date += timedelta(days=1)
    
    # Build complete dataset
    result = []
    for date_str in all_dates:
        result.append({
            "date": date_str,
            "leads": leads_dict.get(date_str, 0),
            "emails_sent": emails_dict.get(date_str, 0)
        })
    
    return result

@app.get("/analytics/summary")
async def get_analytics_summary(current_user: dict = Depends(get_current_user)):
    """Get overall analytics summary for the current user"""
    user_id = str(current_user["_id"])
    total_leads = await leads_col.count_documents({"user_id": user_id})
    unsent_leads = await leads_col.count_documents({"user_id": user_id, "mail_sent": False})
    sent_leads = total_leads - unsent_leads
    
    # Get email stats from mail_logs
    email_stats = await mail_logs_col.aggregate([
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_sent": {"$sum": "$sent_count"},
            "total_failed": {"$sum": {"$size": "$failed"}}
        }}
    ]).to_list(None)
    
    total_emails_sent = email_stats[0]["total_sent"] if email_stats else 0
    total_emails_failed = email_stats[0]["total_failed"] if email_stats else 0
    
    return {
        "total_leads": total_leads,
        "sent_leads": sent_leads,
        "unsent_leads": unsent_leads,
        "total_emails_sent": total_emails_sent,
        "total_emails_failed": total_emails_failed,
        "success_rate": (total_emails_sent / (total_emails_sent + total_emails_failed)) * 100 if (total_emails_sent + total_emails_failed) > 0 else 100
    }

# --------------------
# Bing Maps Scraping Endpoints
# --------------------
@app.post("/scrape-bing-maps", response_model=ScrapeResponse)
async def scrape_bing_maps_endpoint(request: ScrapeRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    try:
        # Start the scraping in the background
        background_tasks.add_task(
            save_scraped_data_to_db,
            request.query,
            request.max_businesses,
            str(current_user["_id"])
        )
        
        return {
            "status": "started",
            "message": f"Scraping started for '{request.query}'. Results will be saved to database.",
            "total_requested": request.max_businesses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def save_scraped_data_to_db(query: str, max_businesses: int, user_id: str):
    """Background task that performs scraping and saves to DB in batches of 10"""
    try:
        # Import here to avoid circular imports
        from scraper import scrape_bing_maps
        
        results = scrape_bing_maps(query, max_businesses)
        
        # Convert to lead format for your database
        leads_to_insert = []
        batch_size = 10  # Save in batches of 10 to reduce API calls
        
        for i, business in enumerate(results):
            lead = {
                "company_name": business.shop_name,
                "contact_number": business.phone,
                "email": business.emails[0] if business.emails else None,
                "owner_name": "",  # Can't get this from Bing Maps
                "mail_sent": False,
                "created_at": datetime.utcnow(),
                "user_id": user_id,
                "source": "bing_maps_scraper",
                "website": business.website,
                "additional_info": {
                    "website_name": business.website_name,
                    "all_emails": business.emails,
                    "scraped_with_proxy": business.proxy_used
                }
            }
            leads_to_insert.append(lead)
            
            # Save in batches of 10
            if len(leads_to_insert) >= batch_size or i == len(results) - 1:
                await leads_col.insert_many(leads_to_insert)
                print(f"✅ Saved batch of {len(leads_to_insert)} leads to database")
                leads_to_insert = []  # Reset for next batch
        
        print(f"🎉 Total {len(results)} leads processed and saved in batches")
        
    except Exception as e:
        print(f"❌ Error in background scraping task: {str(e)}")
        traceback.print_exc()

# --------------------
# Dev endpoints
# --------------------
@app.post("/_dev/seed")
async def seed_dev():
    # Create a default user if none exists
    default_user = await users_collection.find_one({"email": "admin@example.com"})
    if not default_user:
        hashed_password = get_password_hash("password123")
        user_doc = {
            "email": "admin@example.com",
            "password": hashed_password,
            "created_at": datetime.utcnow()
        }
        user_result = await users_collection.insert_one(user_doc)
        user_id = str(user_result.inserted_id)
    else:
        user_id = str(default_user["_id"])
    
    # Create default template
    default = await templates_col.find_one({"name": "default", "user_id": user_id})
    if not default:
        tdoc = {
            "name": "default",
            "subject": "Hello from EmailAgent",
            "content": "Hi {First Name},\n\nWe're reaching out from {Company} to share an opportunity.\n\nBest,\nYour Team",
            "created_at": datetime.utcnow(),
            "user_id": user_id
        }
        await templates_col.insert_one(tdoc)
    
    # Create sample leads
    sample_leads = [
        {"company_name": "Acme Ltd", "contact_number": "03121234567", "email": "lead1@example.com", "owner_name": "Ali Khan", "mail_sent": False, "created_at": datetime.utcnow(), "user_id": user_id},
        {"company_name": "Beta Co", "contact_number": "03127654321", "email": "lead2@example.com", "owner_name": "Sara Ahmed", "mail_sent": False, "created_at": datetime.utcnow(), "user_id": user_id},
    ]
    await leads_col.insert_many(sample_leads)
    
    # Add sample email accounts if none exist
    email_count = await email_accounts_col.count_documents({"user_id": user_id})
    if email_count == 0:
        sample_accounts = [
            {
                "email": "example1@gmail.com",
                "password": "your_app_password_here",
                "sender_name": "Sales Team",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "smtp_host": SMTP_HOST,
                "smtp_port": SMTP_PORT,
                "user_id": user_id
            }
        ]
        await email_accounts_col.insert_many(sample_accounts)
    
    return {"status": "seeded", "user_id": user_id}

# --------------------
# Google Maps Scraping Endpoints
# --------------------
@app.post("/scrape-google-maps", response_model=ScrapeResponse)
async def scrape_google_maps_endpoint(request: ScrapeRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    try:
        # Start the scraping in the background
        background_tasks.add_task(
            save_google_scraped_data_to_db,
            request.query,
            request.max_businesses,
            str(current_user["_id"])
        )
        
        return {
            "status": "started",
            "message": f"Google Maps scraping started for '{request.query}'. Results will be saved to database.",
            "total_requested": request.max_businesses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def save_google_scraped_data_to_db(query: str, max_businesses: int, user_id: str):
    """Background task that performs Google Maps scraping and saves to DB in batches of 10"""
    try:
        # Import the Google Maps scraping function
        from google_scraper import scrape_google_maps
        
        results = scrape_google_maps(query, max_businesses)
        
        # Convert to lead format for your database
        leads_to_insert = []
        batch_size = 10  # Save in batches of 10 to reduce API calls
        
        for i, business in enumerate(results):
            lead = {
                "company_name": business.get("company_name", ""),
                "contact_number": business.get("phone", ""),
                "email": business.get("emails", [""])[0] if business.get("emails") else None,
                "owner_name": "",  # Can't get this from Google Maps
                "mail_sent": False,
                "created_at": datetime.utcnow(),
                "user_id": user_id,
                "source": "google_maps_scraper",
                "website": business.get("website", ""),
                "additional_info": {
                    "all_emails": business.get("emails", []),
                    "scraped_with_proxy": True
                }
            }
            leads_to_insert.append(lead)
            
            # Save in batches of 10
            if len(leads_to_insert) >= batch_size or i == len(results) - 1:
                await leads_col.insert_many(leads_to_insert)
                print(f"✅ Saved batch of {len(leads_to_insert)} Google Maps leads to database")
                leads_to_insert = []  # Reset for next batch
        
        print(f"🎉 Total {len(results)} Google Maps leads processed and saved in batches")
        
    except Exception as e:
        print(f"❌ Error in background Google Maps scraping task: {str(e)}")
        traceback.print_exc()

@app.get("/")
async def root():
    return {"status": "ok", "db": MONGODB_DB}