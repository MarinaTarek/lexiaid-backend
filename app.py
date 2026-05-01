from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
import time
import random
import os
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================
load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

OTP_EXPIRE_SECONDS = int(os.getenv("OTP_EXPIRE_SECONDS", 300))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", 3))

app = Flask(__name__)
CORS(app)

# =========================
# OTP STORE
# =========================
otp_store = {}

# =========================
# SEND EMAIL
# =========================
def send_email(email, otp):
    msg = MIMEText(f"Your OTP Code is: {otp}")
    msg["Subject"] = "LexiAid OTP Verification"
    msg["From"] = EMAIL_USER
    msg["To"] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()

        # ⚠️ متخليش OTP يظهر في production
        print(f"OTP sent to {email} ✅")
        return True

    except Exception as e:
        print("Email error:", e)
        return False

# =========================
# GENERATE OTP
# =========================
def generate_otp():
    return str(random.randint(100000, 999999))

# =========================
# SEND OTP
# =========================
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"status": "error", "message": "Email required"}), 400

    otp = generate_otp()
    expiry = time.time() + OTP_EXPIRE_SECONDS

    otp_store[email] = {
        "otp": otp,
        "expiry": expiry,
        "attempts": 0,
        "verified": False
    }

    if not send_email(email, otp):
        return jsonify({"status": "error", "message": "Failed to send email"}), 500

    return jsonify({"status": "success", "message": "OTP sent"})

# =========================
# VERIFY OTP
# =========================
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    if not email or not otp:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    if email not in otp_store:
        return jsonify({"status": "error", "message": "No OTP found"}), 400

    record = otp_store[email]

    if time.time() > record["expiry"]:
        return jsonify({"status": "error", "message": "OTP expired"}), 400

    if record["attempts"] >= OTP_MAX_ATTEMPTS:
        return jsonify({"status": "error", "message": "Too many attempts"}), 400

    if record["otp"] != otp:
        otp_store[email]["attempts"] += 1
        return jsonify({"status": "error", "message": "Invalid OTP"}), 400

    otp_store[email]["verified"] = True

    return jsonify({"status": "success", "message": "OTP verified"})

# =========================
# RESET PASSWORD
# =========================
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if not email or not otp or not new_password:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    if email not in otp_store:
        return jsonify({"status": "error", "message": "No OTP found"}), 400

    record = otp_store[email]

    if not record.get("verified"):
        return jsonify({"status": "error", "message": "OTP not verified"}), 400

    if record["otp"] != otp:
        return jsonify({"status": "error", "message": "Invalid OTP"}), 400

    # 🔥 هنا تربطيه بالداتابيز
    print(f"Password updated for {email}")

    del otp_store[email]

    return jsonify({"status": "success", "message": "Password updated successfully"})

# =========================
# RESEND OTP
# =========================
@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"status": "error", "message": "Email required"}), 400

    otp = generate_otp()
    expiry = time.time() + OTP_EXPIRE_SECONDS

    otp_store[email] = {
        "otp": otp,
        "expiry": expiry,
        "attempts": 0,
        "verified": False
    }

    if not send_email(email, otp):
        return jsonify({"status": "error", "message": "Failed to resend email"}), 500

    return jsonify({"status": "success", "message": "OTP resent"})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)