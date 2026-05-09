from flask import Blueprint, request, jsonify, send_from_directory
from datetime import datetime
import os

from db import get_db_connection
from services.auth_service import login_user, register_user
from services.otp_service import save_otp
from werkzeug.security import generate_password_hash

auth = Blueprint("auth", __name__)

UPLOAD_FOLDER = "uploads/profile_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _check_otp(email, otp):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT otp, otp_expiry, COALESCE(is_verified, FALSE)
        FROM users WHERE LOWER(email)=LOWER(%s)
    """, (email,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        conn.close()
        return None, None, None, ("fail", "Email not found", 404)

    stored_otp, expiry, is_verified = result
    stored_otp = str(stored_otp or "").strip()

    if not stored_otp:
        cursor.close()
        conn.close()
        return None, None, None, ("fail", "No OTP requested or OTP already used", 400)

    if expiry and expiry < datetime.utcnow():
        cursor.close()
        conn.close()
        return None, None, None, ("fail", "OTP expired", 400)

    if stored_otp != otp:
        cursor.close()
        conn.close()
        return None, None, None, ("fail", "Invalid OTP", 400)

    return conn, cursor, is_verified, None


# =========================
# LOGIN
# =========================
@auth.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"status": "fail", "message": "Missing email or password"}), 400

    try:
        user, error = login_user(email, password)
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)}), 500

    if user:
        return jsonify({
            "status": "success",
            "user_id": user[0],
            "name": user[1],
            "email": user[2],
            "level": user[3]
        })

    if error == "email_not_verified":
        print(f"LOGIN BLOCKED: email not verified ({email})")
        return jsonify({
            "status": "fail",
            "message": "Please verify your email before logging in",
            "needs_verification": True
        }), 403

    print(f"LOGIN FAILED: invalid credentials ({email})")
    return jsonify({"status": "fail", "message": "Invalid email or password"}), 401


# =========================
# REGISTER
# =========================
@auth.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"status": "fail", "message": "Missing data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, COALESCE(is_verified, FALSE) FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        conn.close()
        if existing[1]:
            return jsonify({"status": "fail", "message": "Email already registered"}), 400

        save_otp(email)
        return jsonify({
            "status": "pending_verification",
            "message": "Account already exists. A new verification code was sent.",
            "user_id": existing[0],
            "email": email,
            "needs_verification": True
        }), 200

    user_id = register_user(name, email, password)
    otp = save_otp(email)

    cursor.execute("""
        INSERT INTO progress (user_id, points, streak, tasks_done, active_days)
        VALUES (%s, 0, 0, 0, 0)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "status": "pending_verification",
        "user_id": user_id,
        "name": name,
        "email": email,
        "needs_verification": True,
        "message": "Account created. Please verify your email.",
        "otp": otp
    })


# =========================
# UPLOAD IMAGE
# =========================
@auth.route("/upload-profile-image", methods=["POST"])
def upload_profile_image():

    user_id = request.form.get("user_id")

    if not user_id:
        return jsonify({"status": "fail", "message": "user_id required"}), 400

    if "image" not in request.files:
        return jsonify({"status": "fail", "message": "No image"}), 400

    image = request.files["image"]

    ext = image.filename.rsplit(".", 1)[-1]
    filename = f"user_{user_id}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)

    image.save(path)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET profile_image=%s WHERE id=%s",
        (filename, user_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "filename": filename})


# =========================
# GET IMAGE
# =========================
@auth.route("/profile-image/<int:user_id>")
def get_image(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT profile_image FROM users WHERE id=%s", (user_id,))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if not result or not result[0]:
        return jsonify({"status": "fail"}), 404

    return send_from_directory(UPLOAD_FOLDER, result[0])


# =========================
# SEND OTP
# =========================
@auth.route("/send-otp", methods=["POST"])
def send_otp():

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"status": "fail", "message": "Email required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT email FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"status": "fail", "message": "Email not found"}), 404

    otp = save_otp(email)

    cursor.close()
    conn.close()

    return jsonify({"status": "success", "otp": otp})


# =========================
# VERIFY OTP
# =========================
@auth.route("/verify-otp", methods=["POST"])
@auth.route("/verify-email", methods=["POST"])
def verify_otp():

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp = str(data.get("otp") or "").strip()

    if not email or not otp:
        return jsonify({"status": "fail", "message": "Missing email or OTP"}), 400

    conn, cursor, is_verified, error = _check_otp(email, otp)
    if error:
        status, message, code = error
        return jsonify({"status": status, "message": message}), code

    if not is_verified or request.path == "/verify-email":
        cursor.execute("""
            UPDATE users
            SET is_verified=TRUE, otp=NULL, otp_expiry=NULL
            WHERE LOWER(email)=LOWER(%s)
        """, (email,))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({
            "status": "success",
            "message": "Email verified successfully",
            "is_verified": True
        })

    cursor.close()
    conn.close()
    return jsonify({"status": "success", "message": "OTP verified"})


# =========================
# RESET PASSWORD
# =========================
@auth.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp = str(data.get("otp") or "").strip()
    new_password = data.get("new_password")

    if not email or not otp or not new_password:
        return jsonify({"status": "fail", "message": "Missing data"}), 400

    if len(new_password) < 6:
        return jsonify({"status": "fail", "message": "Password must be at least 6 characters"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT otp, otp_expiry, COALESCE(is_verified, FALSE) FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        conn.close()
        return jsonify({"status": "fail"}), 404

    stored_otp, expiry, is_verified = result
    stored_otp = str(stored_otp or "").strip()

    if not is_verified:
        cursor.close()
        conn.close()
        return jsonify({"status": "fail", "message": "Please verify your email first"}), 403

    if expiry and expiry < datetime.utcnow():
        cursor.close()
        conn.close()
        return jsonify({"status": "fail", "message": "Expired"}), 400

    if not stored_otp:
        cursor.close()
        conn.close()
        return jsonify({"status": "fail", "message": "OTP already used. Please request a new code."}), 400

    if stored_otp != otp:
        cursor.close()
        conn.close()
        return jsonify({"status": "fail", "message": "Invalid OTP"}), 400

    cursor.execute("""
        UPDATE users
        SET password=%s, otp=NULL, otp_expiry=NULL
        WHERE LOWER(email)=LOWER(%s)
    """, (generate_password_hash(new_password), email))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Password updated successfully"})
