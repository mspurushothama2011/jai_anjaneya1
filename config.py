import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
    DEBUG = os.getenv("FLASK_ENV", "development") != "production"
    
    # Check if we're in production environment (Render)
    PRODUCTION = os.getenv("FLASK_ENV") == "production"
    
    # Server configuration
    SERVER_NAME = os.getenv("SERVER_NAME")  # Will be automatically set by Render

    # Email Configuration
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    # Razorpay Credentials
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    
    # Session configuration for production
    if PRODUCTION:
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = 'Lax'
        PREFERRED_URL_SCHEME = 'https'
