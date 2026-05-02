import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# EMAIL CONFIG
# =========================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# =========================
# OTP SETTINGS
# =========================
OTP_EXPIRE_SECONDS = int(os.getenv("OTP_EXPIRE_SECONDS", 300))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", 3))

# =========================
# SECURITY
# =========================
SECRET_KEY = os.getenv("SECRET_KEY")
