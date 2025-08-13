import os
import csv
import time
import re
import smtplib, ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
sender_email = os.getenv("SMTP_SENDER")
password = os.getenv("SMTP_PASSWORD")

# File paths
csv_file = "contacts.csv"   # CSV with name,email
attachment_file = "dummy.pdf"

# Email subject
subject = "Personalized Test Email"

# SSL context
context = ssl.create_default_context()

# Simple email validation
def is_valid_email(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(regex, email) is not None

# Open CSV and send emails
with open(csv_file, newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)  # Expect columns: name,email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        
        for row in reader:
            name = row["name"].strip()
            recipient_email = row["email"].strip()
            
            if not is_valid_email(recipient_email):
                print(f"Skipping invalid email: {recipient_email}")
                continue

            # Create the email
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = recipient_email
            message["Subject"] = subject

            # Personalized body
            body = f"Hello {name}."
            message.attach(MIMEText(body, "plain"))

            # Attach file
            with open(attachment_file, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={attachment_file}")
            message.attach(part)

            # Send email
            try:
                server.sendmail(sender_email, recipient_email, message.as_string())
                print(f"Email sent to {name} <{recipient_email}>")
            except Exception as e:
                print(f"Failed to send to {recipient_email}: {e}")

            # Delay to avoid spam flags (adjust as needed)
            time.sleep(10)  # 10 seconds between emails

print("All emails processed!")
