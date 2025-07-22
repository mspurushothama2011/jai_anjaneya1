from pymongo import MongoClient
from bson.binary import Binary
from dotenv import load_dotenv
import os
from pymongo.server_api import ServerApi

load_dotenv()

# Use a local MongoDB instance
mongodb_uri = "mongodb+srv://mspurushothama20:c435qmGPQMUB3J50@cluster0.nlxfpzd.mongodb.net/"

# Connect to MongoDB with improved error handling and connection parameters
try:
    client = MongoClient(mongodb_uri)
    
    # Test the connection
    client.admin.command('ping')
    print("MongoDB connection successful!")
    
    db = client["temple_system"]
    
    # Define collections
    seva_collection = db["seva_collection"]#contains booked seva details   
    seva_list = db["seva_list"]#contains pooja/varatha types
    events_collection = db["events_collection"]#contains events details
    user_collection = db["user_collection"]#contains user details
    donations_list = db["donations_list"]  # Contains donation types/options
    donations_collection = db["donations_collection"]  # Contains completed donations

    # New collections for Abhisheka functionality
    abhisheka_types = db["abhisheka_types"]#contains abhisheka types
    alankara_types = db["alankara_types"]#contains alankara types
    vadamala_types = db["vadamala_types"]#contains vadamala types
    abhisheka_bookings = db["abhisheka_bookings"]#contains abhisheka bookings
except Exception as e:
    print(f"MongoDB connection error: {e}")
    raise

def initialize_db():
    print("Database initialized successfully!")

def get_user_by_email(email):
    """Fetch user details from MongoDB using their email."""
    user = user_collection.find_one({"email": email})

    if user:
        password_hash = user.get("password", "")  # Get password hash (default to empty string if missing)
        verified = user.get("verified", False)  # ✅ Fetch 'verified' status (default to False)

        # Convert Binary data to string if stored as Binary
        if isinstance(password_hash, Binary):
            password_hash = password_hash.decode("utf-8")  

        return {
            "id": str(user["_id"]),  # Convert ObjectId to string
            "email": user["email"],
            "password": password_hash,  # Ensure password is a string
            "verified": verified  # ✅ Include 'verified' field
        }
    return None  # Return None if user not found