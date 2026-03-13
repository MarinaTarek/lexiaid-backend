from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2 import IntegrityError
import language_tool_python
from language_tool_python.utils import correct
import os
import smtplib
import random
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import random

# =========================
# Fix Java PATH for LanguageTool
# =========================

app = Flask(__name__)
CORS(app)

# =========================
# Gmail Config
# =========================
GMAIL_EMAIL = "marinatarek560@gmail.com"
GMAIL_APP_PASSWORD = "sqit doge kiax vrpu"
# =========================
# Database connection
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# =========================
# LanguageTool setup
# =========================
tool = language_tool_python.LanguageTool('en-US')

# =========================
# Improve sentence
# =========================
def improve_sentence(text):
    replacements = {
        "are plays": "play",
        "is plays": "plays",
        "is play": "plays",
        "are play": "play",
        "we is": "we are",
        "i plays": "i play",
        "he play": "he plays",
        "she play": "she plays",
        "they plays": "they play",
        "playstation": "PlayStation"
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text[:1].upper() + text[1:]

# =========================
# Home
# =========================
@app.route("/")
def home():
    return {"message": "LexiAid backend running"}

# =========================
# Register
# =========================
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"status": "fail", "message": "Please provide all required fields"}), 400

    try:
        cursor.execute(
            "INSERT INTO users (name,email,password,level) VALUES (%s,%s,%s,%s) RETURNING id",
            (name, email, password, "beginner")
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({"status": "success", "message": "User created successfully", "user_id": user_id}), 201

    except IntegrityError:
        conn.rollback()
        return jsonify({"status": "fail", "message": "User already exists"}), 400

# =========================
# Login
# =========================
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"status": "fail", "message": "Please provide email and password"}), 400

    cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
    user = cursor.fetchone()

    if user:
        return jsonify({"status": "success", "user_id": user[0], "name": user[1], "email": user[2], "level": user[4]})

    return jsonify({"status": "fail", "message": "Email or password incorrect"}), 401

# =========================
# Send OTP
# =========================
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"status": "fail", "message": "Email required"}), 400

    otp = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=5)

    try:
        cursor.execute(
            "UPDATE users SET otp=%s, otp_expiry=%s WHERE email=%s RETURNING id",
            (otp, expiry, email)
        )

        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({"status": "fail", "message": "Email not found"}), 404

        conn.commit()

        # تجهيز الرسالة
        msg = MIMEText(f"Your LexiAid OTP code is: {otp}\nIt will expire in 5 minutes.")
        msg["Subject"] = "LexiAid Password Reset OTP"
        msg["From"] = GMAIL_EMAIL
        msg["To"] = email

        # ارسال الايميل
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, email, msg.as_string())
        server.quit()

        return jsonify({"status": "success", "message": "OTP sent to email"})

    except Exception as e:
        print("Email error:", e)
        return jsonify({"status": "fail", "message": str(e)}), 500
# =========================
# Reset Password
# =========================
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    cursor.execute("SELECT otp, otp_expiry FROM users WHERE email=%s", (email,))
    result = cursor.fetchone()
    if not result:
        return jsonify({"status": "fail", "message": "Email not found"}), 404

    stored_otp, otp_expiry = result
    if stored_otp != otp:
        return jsonify({"status": "fail", "message": "Invalid OTP"}), 400

    if otp_expiry < datetime.utcnow():
        return jsonify({"status": "fail", "message": "OTP expired"}), 400

    try:
        cursor.execute("UPDATE users SET password=%s, otp=NULL, otp_expiry=NULL WHERE email=%s", (new_password, email))
        conn.commit()
        return jsonify({"status": "success", "message": "Password updated"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "fail", "message": str(e)}), 500

# =========================
# Grammar Correction
# =========================
@app.route("/correct", methods=["POST"])
def correct_text():
    data = request.json
    text = data.get("text", "").strip()
    if text == "":
        return jsonify({"correctedText": "", "corrections": [], "word_count": 0, "correct_words": 0, "to_fix": 0, "similarity": 0})

    matches = tool.check(text)
    corrected_text = correct(text, matches)
    corrected_text = improve_sentence(corrected_text)
    corrections = [{"wrong": text[m.offset:m.offset + m.error_length], "suggestion": m.replacements[0] if m.replacements else "", "message": m.message} for m in matches]

    words = text.split()
    word_count = len(words)
    to_fix = len(matches)
    correct_words = max(word_count - to_fix, 0)
    similarity = int((correct_words / word_count) * 100) if word_count > 0 else 100

    return jsonify({"correctedText": corrected_text, "corrections": corrections, "word_count": word_count, "correct_words": correct_words, "to_fix": to_fix, "similarity": similarity})

# =========================
# Run server
# =========================
if __name__ == "__main__":
    app.run()