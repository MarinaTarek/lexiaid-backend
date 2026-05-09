import random
from datetime import datetime, timedelta
from db import get_cursor
import smtplib
from email.mime.text import MIMEText
from config import GMAIL_EMAIL, GMAIL_APP_PASSWORD

# =========================
# EMAIL SENDER (FIXED + SAFE)
# =========================
def send_email_otp(email, otp):
    try:
        sender = GMAIL_EMAIL
        password = GMAIL_APP_PASSWORD

        msg = MIMEText(f"Your OTP Code is: {otp}")
        msg["Subject"] = "OTP Verification"
        msg["From"] = sender
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        server.login(sender, password)
        server.sendmail(sender, email, msg.as_string())
        server.quit()

        print("✅ OTP sent")

    except Exception as e:
        print("❌ Email failed:", e)

# =========================
# OTP GENERATOR (SECURE)
# =========================
def generate_otp():
    return str(random.randint(100000, 999999))


# =========================
# SAVE OTP
# =========================
def save_otp(email):
    email = email.strip().lower()
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    cursor, conn = get_cursor()
    cursor.execute("""
        UPDATE users 
        SET otp=%s, otp_expiry=%s 
        WHERE email=%s
    """, (otp, expiry, email))

    conn.commit()
    cursor.close()
    conn.close()

    send_email_otp(email, otp)

    return otp


# =========================
# VERIFY OTP (SAFE CHECK)
# =========================
def verify_otp(email, otp):
    cursor, conn = get_cursor()
    cursor.execute("""
        SELECT otp, otp_expiry 
        FROM users 
        WHERE email=%s
    """, (email,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return False, "Email not found"

    stored_otp, expiry = result

    if not stored_otp:
        return False, "No OTP requested"

    if expiry and expiry < datetime.utcnow():
        return False, "OTP expired"

    if stored_otp != otp:
        return False, "Invalid OTP"

    return True, "Verified"
