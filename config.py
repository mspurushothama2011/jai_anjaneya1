import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
    DEBUG = os.getenv("FLASK_ENV", "development") != "production"
    
    # JWT Configuration for Mobile API
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "b3fed354-01e9-4a85-9920-a4f2765b159f")
    JWT_ACCESS_TOKEN_EXPIRES = 3600 * 24 * 7  # Tokens expire in 7 days
    JWT_REFRESH_TOKEN_EXPIRES = 3600 * 24 * 30  # Refresh tokens expire in 30 days
    
    # Check if we're in production environment (Render)
    PRODUCTION = os.getenv("FLASK_ENV") == "production"

    if PRODUCTION:
        if SECRET_KEY == "default_secret_key" or JWT_SECRET_KEY == "b3fed354-01e9-4a85-9920-a4f2765b159f":
            raise ValueError("SECRET_KEY and JWT_SECRET_KEY must be explicitly set in production!")
    
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
