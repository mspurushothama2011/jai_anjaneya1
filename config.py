import os
import secrets
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class Config:
    # Check if we're in production environment (Render/Railway)
    PRODUCTION = os.getenv("FLASK_ENV") == "production"

    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY or SECRET_KEY == "default_secret_key":
        if PRODUCTION:
            SECRET_KEY = secrets.token_hex(24)
        else:
            SECRET_KEY = "default_secret_key"

    DEBUG = os.getenv("FLASK_ENV", "development") != "production"
    
    # JWT Configuration for Mobile API
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY or JWT_SECRET_KEY == "b3fed354-01e9-4a85-9920-a4f2765b159f":
        if PRODUCTION:
            JWT_SECRET_KEY = secrets.token_hex(24)
        else:
            JWT_SECRET_KEY = "b3fed354-01e9-4a85-9920-a4f2765b159f"

    JWT_ACCESS_TOKEN_EXPIRES = 3600 * 24 * 7  # Tokens expire in 7 days
    JWT_REFRESH_TOKEN_EXPIRES = 3600 * 24 * 30  # Refresh tokens expire in 30 days
    
    # Server configuration
    # SERVER_NAME is intentionally left unconfigured to allow Railway to route both www and non-www domains
    # safely without Host-header rejections.
    # Email Configuration
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    # Razorpay Credentials
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

    # Admin credentials
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    
    # Session configuration for production
    if PRODUCTION:
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = 'Lax'
        PREFERRED_URL_SCHEME = 'https'
