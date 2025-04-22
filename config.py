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
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "87b185003@smtp-brevo.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "f0JGmvxsnA3ECLDO")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "mspurushothama2011@gmail.com")

    # Razorpay Credentials
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_6WWw11VMvM8MXw")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "4akdtf9N66cjL36XOSNjXYBc")
    
    # Session configuration for production
    if PRODUCTION:
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = 'Lax'
        PREFERRED_URL_SCHEME = 'https'
