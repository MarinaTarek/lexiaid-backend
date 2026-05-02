from flask import Blueprint, request, jsonify
from datetime import datetime

from db import cursor, conn
from services.auth_service import login_user
from services.otp_service import save_otp

auth = Blueprint("auth", __name__)


# =========================
# LOGIN
# =========================
@auth.route("/login", methods=["POST"])
def login():
    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "status": "fail",
            "message": "Missing email or password"
        }), 400

    user = login_user(email, password)

    if user:
        return jsonify({
            "status": "success",
            "name": user[1],
            "email": user[2],
            "level": user[3]
        })

    return jsonify({
        "status": "fail",
        "message": "Invalid email or password"
    }), 401
# =========================
# verify OTP
# =========================
@auth.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    cursor.execute("""
        SELECT otp, otp_expiry 
        FROM users 
        WHERE email=%s
    """, (email,))

    result = cursor.fetchone()

    if not result:
        return jsonify({"status": "fail", "message": "Email not found"}), 404

    stored_otp, expiry = result

    if expiry and expiry < datetime.utcnow():
        return jsonify({"status": "fail", "message": "OTP expired"}), 400

    if stored_otp != otp:
        return jsonify({"status": "fail", "message": "Invalid OTP"}), 400

    return jsonify({"status": "success", "message": "OTP verified"}), 200
# =========================
# SEND OTP
# =========================
@auth.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({
            "status": "fail",
            "message": "Email required"
        }), 400

    # check user exists
    cursor.execute("SELECT email FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        return jsonify({
            "status": "fail",
            "message": "Email not found"
        }), 404

    otp = save_otp(email)

    return jsonify({
        "status": "success",
        "message": "OTP sent successfully",
        "otp": otp  # احذفيه في production
    }), 200


# =========================
# RESET PASSWORD
# =========================
@auth.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if not email or not otp or not new_password:
        return jsonify({
            "status": "fail",
            "message": "Missing data"
        }), 400

    cursor.execute("""
        SELECT otp, otp_expiry 
        FROM users 
        WHERE email=%s
    """, (email,))

    result = cursor.fetchone()

    if not result:
        return jsonify({
            "status": "fail",
            "message": "Email not found"
        }), 404

    stored_otp, expiry = result

    # check expiry
    if expiry and expiry < datetime.utcnow():
        return jsonify({
            "status": "fail",
            "message": "OTP expired"
        }), 400

    # check OTP
    if stored_otp != otp:
        return jsonify({
            "status": "fail",
            "message": "Invalid OTP"
        }), 400

    # update password + clear OTP
    cursor.execute("""
        UPDATE users 
        SET password=%s, otp=NULL, otp_expiry=NULL
        WHERE email=%s
    """, (new_password, email))

    conn.commit()

    return jsonify({
        "status": "success",
        "message": "Password updated successfully"
    })