import os
import re
import asyncio
import base64
import traceback
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
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
SMTP_SENDER = os.getenv("SMTP_SENDER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_DELAY = float(os.getenv("SMTP_DELAY", 15.0))  # seconds between emails in the blocking send loop
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not SMTP_SENDER or not SMTP_PASSWORD:
    print("Warning: SMTP_SENDER or SMTP_PASSWORD not set in environment. /send-emails will fail without them.")

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

class SendEmailsPayload(BaseModel):
    template_id: str
    lead_ids: Optional[List[str]] = None
    attachments: Optional[List[Attachment]] = None

class RephraseOutput(BaseModel):
    rephrased_email: str

class RephraseRequest(BaseModel):
    template_id: str
    content: str

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

def send_bulk_via_smtp_blocking(sender: str, password: str, host: str, port: int, messages: List[Dict[str, Any]], delay: float = 1.0) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    sent = []
    failed = []
    
    for m in messages:
        try:
            # Create a new connection for each email
            with smtplib.SMTP_SSL(host, port, context=ctx) as server:
                server.login(sender, password)
                msgstr = build_message(
                    sender, 
                    m["to"], 
                    m["subject"], 
                    m["body"], 
                    sender_name=None,
                    attachments=m.get("attachments")
                )
                server.sendmail(sender, m["to"], msgstr)
                sent.append({"email": m["to"]})
                print(f"Sent email to {m['to']} with {len(m.get('attachments', []))} attachments")
        except Exception as e:
            error_msg = str(e)
            print(f"Failed to send to {m.get('to')}: {error_msg}")
            failed.append({"email": m.get("to"), "error": error_msg})
        
        if delay and delay > 0:
            time.sleep(delay)
    
    return {"sent": sent, "failed": failed}

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

async def background_send(template_id: str, lead_ids: List[str], attachments: Optional[List[Dict[str, str]]] = None):
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
            "attachments": attachments  # Each message gets its own copy
        })

    if not messages:
        return {"status": "no_valid_recipients"}

    result = await asyncio.to_thread(
        send_bulk_via_smtp_blocking, 
        SMTP_SENDER, 
        SMTP_PASSWORD, 
        SMTP_HOST, 
        SMTP_PORT, 
        messages, 
        SMTP_DELAY
    )

    # Update tracking of sent emails
    sent_emails = [s["email"] for s in result.get("sent", [])]
    sent_lead_ids = [str(l["_id"]) for l in leads if l.get("email") in sent_emails]
    if sent_lead_ids:
        await mark_leads_sent(sent_lead_ids)

    await db["mail_logs"].insert_one({
        "template_id": template_id,
        "sent_count": len(result.get("sent", [])),
        "failed": result.get("failed", []),
        "created_at": datetime.utcnow(),
        "had_attachments": bool(attachments)
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

    background_tasks.add_task(background_send, payload.template_id, lead_ids, attachments)
    return {"status": "queued", "leads_count": len(lead_ids)}

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
    return {"status": "seeded"}

@app.get("/")
async def root():
    return {"status": "ok", "db": MONGODB_DB}