from pymongo import MongoClient
from bson.binary import Binary
from dotenv import load_dotenv
import os

load_dotenv()

# ✅ Connect to MongoDB
client = MongoClient(
    os.getenv("MONGODB_URI"),
    serverSelectionTimeoutMS=5000,  # 5 seconds
    connectTimeoutMS=10000,         # 10 seconds
    socketTimeoutMS=45000           # 45 seconds
)
db = client["temple_system"]

# ✅ Define collections
seva_collection = db["seva_collection"]
seva_list = db["seva_list"]
events_collection = db["events_collection"]
user_collection = db["user_collection"]
donations_list = db["donations_list"]  # Contains donation types/options
donations_collection = db["donations_collection"]  # Contains completed donations





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