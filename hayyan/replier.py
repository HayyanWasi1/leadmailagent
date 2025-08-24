from imap_tools import MailBox
import email.utils
import time
import threading

EMAIL_ACCOUNTS = [
    {
        'username': 'sample@gmail.com',
        'password': 'txghrfzssgaordqh1234'
    },
    {
        'username': 'sample2@gmail.com', 
        'password': 'funrhujnhsuwmma'
    },
]

all_emails = []
emails_lock = threading.Lock()

def process_email_info(msg, account_email):
    sender_name, sender_email = email.utils.parseaddr(msg.from_)
    email_time = msg.date.strftime("%d-%m-%Y %I:%M:%p")
    
    print(f"From: {sender_email} To: {account_email} Time: {email_time}")

def fetch_emails_for_account(username, password):
    while True:
        try:
            with MailBox("imap.gmail.com").login(username, password, "Inbox") as mb:
                processed_uids = set()
                
                while True:
                    try:
                        for msg in mb.fetch('UNSEEN', mark_seen=False, reverse=True):
                            if msg.uid not in processed_uids:
                                process_email_info(msg, username)
                                processed_uids.add(msg.uid)
                        
                        time.sleep(5)
                        
                    except:
                        break 
                        
        except KeyboardInterrupt:
            break
        except:
            time.sleep(15)

def main():
    threads = []
    
    for i, account in enumerate(EMAIL_ACCOUNTS):
        if i > 0:
            time.sleep(3)
        
        thread = threading.Thread(
            target=fetch_emails_for_account, 
            args=(account['username'], account['password']),
            daemon=True
        )
        thread.start()
        threads.append(thread)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()