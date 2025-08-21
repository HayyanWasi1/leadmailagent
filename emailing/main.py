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
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
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


load_dotenv()

# --------------------
# Config
# --------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "email_agent_db")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_DELAY = float(os.getenv("SMTP_DELAY", 15.0))  # seconds between emails in the blocking send loop
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

# --------------------
# Utilities
# --------------------
EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

def is_valid_email(email: str) -> bool:
    return re.match(EMAIL_REGEX, email) is not None

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
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
class TemplateIn(BaseModel):
    name: str = Field(..., example="Default")
    subject: str = Field(..., example="Hello from Acme")
    content: str = Field(..., example="Hi {First Name}, ...")

class TemplateOut(TemplateIn):
    id: str
    created_at: datetime

class LeadIn(BaseModel):
    company_name: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    owner_name: Optional[str] = None

class LeadOut(LeadIn):
    id: str
    mail_sent: bool = False
    created_at: datetime

class Attachment(BaseModel):
    filename: str
    content: str  # base64 encoded content

class EmailAccountIn(BaseModel):
    email: EmailStr
    password: str = Field(..., description="App password for the email account")
    sender_name: Optional[str] = None
    daily_limit: int = Field(100, ge=1, description="Maximum emails to send per day")
    is_active: bool = True

class EmailAccountOut(EmailAccountIn):
    id: str
    created_at: datetime
    emails_sent_today: int = 0
    last_reset_date: datetime

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

# --------------------
# Email Account Management
# --------------------
async def get_available_email_accounts() -> List[Dict[str, Any]]:
    """Get all active email accounts that haven't reached their daily limit"""
    # First, check if we need to reset daily counts
    today = datetime.utcnow().date()
    
    # Find accounts that need reset
    accounts_to_reset = await email_accounts_col.find({
        "last_reset_date": {"$lt": datetime(today.year, today.month, today.day)}
    }).to_list(length=None)
    
    # Reset counts for these accounts
    if accounts_to_reset:
        await email_accounts_col.update_many(
            {"_id": {"$in": [acc["_id"] for acc in accounts_to_reset]}},
            {"$set": {"emails_sent_today": 0, "last_reset_date": datetime.utcnow()}}
        )
    
    # Get all active accounts that haven't reached their daily limit
    cursor = email_accounts_col.find({
        "is_active": True,
        "emails_sent_today": {"$lt": "$daily_limit"}
    })
    
    accounts = []
    async for acc in cursor:
        accounts.append(acc)
    
    return accounts

async def update_email_account_usage(account_id: ObjectId, emails_sent: int):
    """Update the count of emails sent for an account"""
    await email_accounts_col.update_one(
        {"_id": account_id},
        {"$inc": {"emails_sent_today": emails_sent}}
    )

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
    """Send emails using multiple accounts with round-robin distribution"""
    sent = []
    failed = []
    account_usage = {acc["_id"]: 0 for acc in email_accounts}
    
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
            
        # Check if account has reached its daily limit
        if account["emails_sent_today"] + account_usage[account["_id"]] >= account["daily_limit"]:
            # Skip this account, try next one
            current_account_index = (current_account_index + 1) % len(account_ids)
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
            account_usage[account["_id"]] += 1
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
    
    return {"sent": sent, "failed": failed, "account_usage": account_usage}

async def mark_leads_sent(lead_ids: List[str]):
    oids = []
    for lid in lead_ids:
        try:
            oids.append(ObjectId(lid))
        except Exception:
            continue
    if not oids:
        return
    await leads_col.update_many(
        {"_id": {"$in": oids}}, 
        {"$set": {"mail_sent": True, "last_mailed_at": datetime.utcnow()}}
    )

async def background_send(template_id: str, lead_ids: List[str], attachments: Optional[List[Dict[str, str]]] = None, email_account_ids: Optional[List[str]] = None):
    tmpl = await templates_col.find_one({"_id": oid(template_id)})
    if not tmpl:
        return {"status": "template_not_found"}

    q = {"_id": {"$in": [ObjectId(l) for l in lead_ids if ObjectId.is_valid(l)]}}
    leads_cursor = leads_col.find(q)
    leads = []
    async for l in leads_cursor:
        leads.append(l)

    messages = []
    for l in leads:
        recipient = l.get("email")
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

    if not messages:
        return {"status": "no_valid_recipients"}

    # Get available email accounts
    if email_account_ids:
        # Use specific accounts requested
        account_oids = [ObjectId(acc_id) for acc_id in email_account_ids if ObjectId.is_valid(acc_id)]
        email_accounts = await email_accounts_col.find({
            "_id": {"$in": account_oids},
            "is_active": True
        }).to_list(length=None)
    else:
        # Use all available accounts
        email_accounts = await get_available_email_accounts()
    
    if not email_accounts:
        return {"status": "no_valid_accounts", "message": "No active email accounts available"}

    result = await asyncio.to_thread(
        send_bulk_via_smtp_blocking, 
        email_accounts, 
        messages, 
        SMTP_DELAY
    )

    # Update tracking of sent emails and account usage
    sent_emails = [s["email"] for s in result.get("sent", [])]
    sent_lead_ids = [str(l["_id"]) for l in leads if l.get("email") in sent_emails]
    if sent_lead_ids:
        await mark_leads_sent(sent_lead_ids)
    
    # Update account usage counts
    for account_id, count in result.get("account_usage", {}).items():
        if count > 0:
            await update_email_account_usage(ObjectId(account_id), count)

    await mail_logs_col.insert_one({
        "template_id": template_id,
        "sent_count": len(result.get("sent", [])),
        "failed": result.get("failed", []),
        "created_at": datetime.utcnow(),
        "had_attachments": bool(attachments),
        "accounts_used": [str(acc["_id"]) for acc in email_accounts]
    })
    return result

# --------------------
# API Endpoints
# --------------------
@app.post("/rephrase-email")
async def rephrase_email(request: RephraseRequest):
    if not rephrase_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rephrasing service not configured"
        )
    
    try:
        # Verify template exists first
        template = await templates_col.find_one({"_id": oid(request.template_id)})
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
            {"_id": oid(request.template_id)},
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
async def get_templates():
    cursor = templates_col.find().sort("created_at", -1)
    docs = []
    async for d in cursor:
        docs.append(serialize_doc(d))
    return docs

@app.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(template_id: str):
    t = await templates_col.find_one({"_id": oid(template_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return serialize_doc(t)

@app.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateIn):
    doc = payload.dict()
    doc["created_at"] = datetime.utcnow()
    r = await templates_col.insert_one(doc)
    created = await templates_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.put("/templates/{template_id}", response_model=TemplateOut)
async def update_template(template_id: str, payload: TemplateIn):
    update_doc = {"$set": payload.dict()}
    res = await templates_col.update_one({"_id": oid(template_id)}, update_doc)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    new = await templates_col.find_one({"_id": oid(template_id)})
    return serialize_doc(new)

@app.get("/leads", response_model=List[LeadOut])
async def get_leads(limit: int = 100, sent: Optional[bool] = None):
    query = {"mail_sent": False}  # Default to only unsent leads
    if sent is not None:
        query["mail_sent"] = sent
        
    cursor = leads_col.find(query).sort("created_at", -1).limit(limit)
    out = []
    async for d in cursor:
        doc = serialize_doc(d)
        doc.setdefault("mail_sent", False)
        out.append(doc)
    return out

@app.get("/leads/count")
async def leads_count(sent: Optional[bool] = None):
    query = {"mail_sent": False}  # Default to only unsent leads
    if sent is not None:
        query["mail_sent"] = sent
        
    count = await leads_col.count_documents(query)
    return {"count": count}

@app.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadIn):
    doc = payload.dict()
    doc["mail_sent"] = False
    doc["created_at"] = datetime.utcnow()
    r = await leads_col.insert_one(doc)
    created = await leads_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.post("/send-emails")
async def send_emails(payload: SendEmailsPayload, background_tasks: BackgroundTasks):
    try:
        template_obj = await templates_col.find_one({"_id": oid(payload.template_id)})
    except HTTPException as e:
        raise e
    if not template_obj:
        raise HTTPException(status_code=404, detail="Template not found")

    lead_ids = payload.lead_ids or []
    if not lead_ids:
        cursor = leads_col.find({"mail_sent": False}).sort("created_at", 1).limit(100)
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
        attachments, 
        payload.email_account_ids
    )
    return {"status": "queued", "leads_count": len(lead_ids)}

# --------------------
# Email Accounts Endpoints
# --------------------
@app.get("/email-accounts", response_model=List[EmailAccountOut])
async def get_email_accounts(active_only: bool = True):
    query = {"is_active": True} if active_only else {}
    cursor = email_accounts_col.find(query).sort("created_at", -1)
    accounts = []
    async for acc in cursor:
        accounts.append(serialize_doc(acc))
    return accounts

@app.post("/email-accounts", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_email_account(payload: EmailAccountIn):
    # Check if email already exists
    existing = await email_accounts_col.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email account already exists")
    
    doc = payload.dict()
    doc["created_at"] = datetime.utcnow()
    doc["last_reset_date"] = datetime.utcnow()
    doc["emails_sent_today"] = 0
    doc["smtp_host"] = SMTP_HOST
    doc["smtp_port"] = SMTP_PORT
    
    r = await email_accounts_col.insert_one(doc)
    created = await email_accounts_col.find_one({"_id": r.inserted_id})
    return serialize_doc(created)

@app.put("/email-accounts/{account_id}", response_model=EmailAccountOut)
async def update_email_account(account_id: str, payload: EmailAccountIn):
    update_doc = {"$set": payload.dict()}
    res = await email_accounts_col.update_one({"_id": oid(account_id)}, update_doc)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Email account not found")
    updated = await email_accounts_col.find_one({"_id": oid(account_id)})
    return serialize_doc(updated)

@app.delete("/email-accounts/{account_id}")
async def delete_email_account(account_id: str):
    res = await email_accounts_col.delete_one({"_id": oid(account_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Email account not found")
    return {"status": "deleted"}

@app.post("/email-accounts/{account_id}/reset")
async def reset_email_account_usage(account_id: str):
    res = await email_accounts_col.update_one(
        {"_id": oid(account_id)},
        {"$set": {"emails_sent_today": 0, "last_reset_date": datetime.utcnow()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Email account not found")
    return {"status": "reset"}

# --------------------
# Analytics Endpoints
# --------------------
@app.get("/analytics/daily-stats")
async def get_daily_stats(days: int = 30):
    """Get daily statistics for leads and emails"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get daily lead counts
    lead_pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "leads_count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    # Get daily email counts from mail_logs
    email_pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
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
async def get_analytics_summary():
    """Get overall analytics summary"""
    total_leads = await leads_col.count_documents({})
    unsent_leads = await leads_col.count_documents({"mail_sent": False})
    sent_leads = total_leads - unsent_leads
    
    # Get email stats from mail_logs
    email_stats = await mail_logs_col.aggregate([
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
async def scrape_bing_maps_endpoint(request: ScrapeRequest, background_tasks: BackgroundTasks):
    try:
        # Start the scraping in the background
        background_tasks.add_task(
            save_scraped_data_to_db,
            request.query,
            request.max_businesses
        )
        
        return {
            "status": "started",
            "message": f"Scraping started for '{request.query}'. Results will be saved to database.",
            "total_requested": request.max_businesses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def save_scraped_data_to_db(query: str, max_businesses: int):
    """Background task that performs scraping and saves to DB"""
    try:
        # Import here to avoid circular imports
        from scraper import scrape_bing_maps
        
        results = scrape_bing_maps(query, max_businesses)
        
        # Convert to lead format for your database
        leads_to_insert = []
        for business in results:
            lead = {
                "company_name": business.shop_name,
                "contact_number": business.phone,
                "email": business.emails[0] if business.emails else None,
                "owner_name": "",  # Can't get this from Bing Maps
                "mail_sent": False,
                "created_at": datetime.utcnow(),
                "source": "bing_maps_scraper",
                "website": business.website,
                "additional_info": {
                    "website_name": business.website_name,
                    "all_emails": business.emails,
                    "scraped_with_proxy": business.proxy_used
                }
            }
            leads_to_insert.append(lead)
        
        if leads_to_insert:
            await leads_col.insert_many(leads_to_insert)
            print(f"✅ Saved {len(leads_to_insert)} leads to database")
        
    except Exception as e:
        print(f"❌ Error in background scraping task: {str(e)}")
        traceback.print_exc()

# --------------------
# Dev endpoints
# --------------------
@app.post("/_dev/seed")
async def seed_dev():
    default = await templates_col.find_one({"name": "default"})
    if not default:
        tdoc = {
            "name": "default",
            "subject": "Hello from EmailAgent",
            "content": "Hi {First Name},\n\nWe're reaching out from {Company} to share an opportunity.\n\nBest,\nYour Team",
            "created_at": datetime.utcnow()
        }
        await templates_col.insert_one(tdoc)
    
    sample_leads = [
        {"company_name": "Acme Ltd", "contact_number": "03121234567", "email": "lead1@example.com", "owner_name": "Ali Khan", "mail_sent": False, "created_at": datetime.utcnow()},
        {"company_name": "Beta Co", "contact_number": "03127654321", "email": "lead2@example.com", "owner_name": "Sara Ahmed", "mail_sent": False, "created_at": datetime.utcnow()},
    ]
    await leads_col.insert_many(sample_leads)
    
    # Add sample email accounts if none exist
    email_count = await email_accounts_col.count_documents({})
    if email_count == 0:
        sample_accounts = [
            {
                "email": "example1@gmail.com",
                "password": "your_app_password_here",
                "sender_name": "Sales Team",
                "daily_limit": 100,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_reset_date": datetime.utcnow(),
                "emails_sent_today": 0,
                "smtp_host": SMTP_HOST,
                "smtp_port": SMTP_PORT
            }
        ]
        await email_accounts_col.insert_many(sample_accounts)
    
    return {"status": "seeded"}

@app.get("/")
async def root():
    return {"status": "ok", "db": MONGODB_DB}

from datetime import datetime, timedelta
from collections import defaultdict

# Add these endpoints after the existing API endpoints
@app.get("/analytics/daily-stats")
async def get_daily_stats(days: int = 30):
    """Get daily statistics for leads created and emails sent"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get daily lead creation stats
    pipeline_leads = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "leads_created": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    # Get daily email sending stats
    pipeline_emails = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "emails_sent": {"$sum": "$sent_count"},
            "emails_failed": {"$sum": {"$size": "$failed"}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    leads_cursor = leads_col.aggregate(pipeline_leads)
    emails_cursor = db["mail_logs"].aggregate(pipeline_emails)
    
    leads_stats = await leads_cursor.to_list(length=None)
    emails_stats = await emails_cursor.to_list(length=None)
    
    # Convert to dictionaries for easier merging
    leads_dict = {stat["_id"]: stat["leads_created"] for stat in leads_stats}
    emails_dict = {stat["_id"]: stat["emails_sent"] for stat in emails_stats}
    
    # Generate all dates in the range
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
            "leads_created": leads_dict.get(date_str, 0),
            "emails_sent": emails_dict.get(date_str, 0)
        })
    
    return result

@app.get("/analytics/summary")
async def get_analytics_summary():
    """Get overall analytics summary"""
    total_leads = await leads_col.count_documents({})
    total_sent_leads = await leads_col.count_documents({"mail_sent": True})
    total_unsent_leads = await leads_col.count_documents({"mail_sent": False})
    
    # Get total emails sent from mail_logs
    pipeline = [
        {"$group": {
            "_id": None,
            "total_emails_sent": {"$sum": "$sent_count"},
            "total_emails_failed": {"$sum": {"$size": "$failed"}}
        }}
    ]
    
    email_stats = await db["mail_logs"].aggregate(pipeline).to_list(length=1)
    email_stats = email_stats[0] if email_stats else {"total_emails_sent": 0, "total_emails_failed": 0}
    
    return {
        "total_leads": total_leads,
        "sent_leads": total_sent_leads,
        "unsent_leads": total_unsent_leads,
        "total_emails_sent": email_stats["total_emails_sent"],
        "total_emails_failed": email_stats["total_emails_failed"],
        "success_rate": (email_stats["total_emails_sent"] / (email_stats["total_emails_sent"] + email_stats["total_emails_failed"])) * 100 if (email_stats["total_emails_sent"] + email_stats["total_emails_failed"]) > 0 else 100
    }