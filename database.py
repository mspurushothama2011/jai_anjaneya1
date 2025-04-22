from pymongo import MongoClient
from bson.binary import Binary
from dotenv import load_dotenv
import os

load_dotenv()

# Get MongoDB URI from environment variable - this will be set in Render
mongodb_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

if not mongodb_uri:
    raise ValueError("No MongoDB connection string found in environment variables! Set MONGODB_URI or MONGO_URI")

# Connect to MongoDB with improved error handling and connection parameters
try:
    client = MongoClient(
        mongodb_uri,
        serverSelectionTimeoutMS=5000,  # 5 seconds
        connectTimeoutMS=10000,         # 10 seconds
        socketTimeoutMS=45000,          # 45 seconds
        retryWrites=True,               # Enable retry writes for reliability
        w="majority"                    # Write concern for data durability
    )
    
    # Test the connection
    client.admin.command('ping')
    print("MongoDB connection successful!")
    
    db = client["temple_system"]
    
    # Define collections
    seva_collection = db["seva_collection"]
    seva_list = db["seva_list"]
    events_collection = db["events_collection"]
    user_collection = db["user_collection"]
    donations_list = db["donations_list"]  # Contains donation types/options
    donations_collection = db["donations_collection"]  # Contains completed donations
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





#Use this connection string in your application

#  mongodb+srv://mspurushothama20:egEQD9sJZtl6wFk3@cluster0.nlxfpzd.mongodb.net/