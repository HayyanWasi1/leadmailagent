# import_leads_async.py
import os
import csv
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import motor.motor_asyncio

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "email_agent_db")
CSV_FILE = "abcd.csv"   # expected columns: company_name,contact_number,email,owner_name

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'
def is_valid_email(e: str) -> bool:
    return re.match(EMAIL_REGEX, e or "") is not None

async def main():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]
    leads_col = db["leads"]

    to_insert = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("email") or "").strip()
            doc = {
                "company_name": (row.get("company_name") or "").strip(),
                "contact_number": (row.get("contact_number") or "").strip(),
                "email": email if is_valid_email(email) else None,
                "owner_name": (row.get("owner_name") or "").strip(),
                "mail_sent": False,
                "created_at": datetime.utcnow()
            }
            to_insert.append(doc)

    if not to_insert:
        print("No rows found to insert.")
        return

    result = await leads_col.insert_many(to_insert)
    print(f"Inserted {len(result.inserted_ids)} leads.")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
