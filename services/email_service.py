import smtplib
from email.mime.text import MIMEText
from config import GMAIL_EMAIL, GMAIL_APP_PASSWORD

def send_email(to_email, subject, body):
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        raise Exception("Email config missing (.env not loaded properly)")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_EMAIL
    msg["To"] = to_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)

    server.send_message(msg)
    server.quit()