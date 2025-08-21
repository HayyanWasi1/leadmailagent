# import_templates_async.py
import os
import csv
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import motor.motor_asyncio

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "email_agent_db")
CSV_FILE = "templates.csv"   # header: name,subject,content

# Behavior flags
skip_duplicates = True   # if a template with same "name" exists, skip inserting
upsert = False           # if True, update existing template with same "name" (overrides skip_duplicates)

async def import_templates():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    try:
        db = client[MONGODB_DB]
        col = db["templates"]

        rows = []
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                subject = (row.get("subject") or "").strip()
                content = (row.get("content") or "").strip()
                if not name or not subject or not content:
                    # skip incomplete rows
                    print(f"Skipping incomplete row: {row}")
                    continue
                rows.append({
                    "name": name,
                    "subject": subject,
                    "content": content,
                    "created_at": datetime.now(timezone.utc)
                })

        if not rows:
            print("No valid templates to insert.")
            return

        inserted = 0
        updated = 0
        skipped = 0

        for doc in rows:
            filter_q = {"name": doc["name"]}
            if upsert:
                res = await col.replace_one(filter_q, doc, upsert=True)
                # replace_one with upsert returns matched_count/modified_count depending on driver version
                if res.upserted_id:
                    inserted += 1
                else:
                    updated += 1
            else:
                exists = await col.find_one(filter_q)
                if exists:
                    if skip_duplicates:
                        skipped += 1
                        print(f"Skipping existing template name: {doc['name']}")
                    else:
                        # insert anyway with a modified name (append timestamp) to avoid name clash
                        new_name = f"{doc['name']}_{int(datetime.now().timestamp())}"
                        doc["name"] = new_name
                        await col.insert_one(doc)
                        inserted += 1
                else:
                    await col.insert_one(doc)
                    inserted += 1

        print(f"Done. Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(import_templates())
