"""
init_sevas.py

Purpose:
    - Script to initialize the database with hard-coded sevas from seva_config.py.
    - Useful for setting up a new environment or resetting the seva list.

Note:
    - Not required for production or runtime.
    - Useful for development, setup, or admin tasks.
    - Can be moved to a 'scripts/' or 'tools/' folder to keep the root directory clean.
"""

from database import seva_list
from seva_config import ABHISHEKA_SEVAS, ALANKARA_SEVAS, VADAMALA_SEVAS
from pymongo import MongoClient
import os
from dotenv import load_dotenv

def init_fixed_sevas():
    """Initialize the database with hard-coded sevas"""
    print("Initializing fixed sevas in the database...")
    
    # Count existing sevas by type
    abhisheka_count = seva_list.count_documents({"seva_type": "Abhishekas"})
    alankara_count = seva_list.count_documents({"seva_type": "Alankar"})
    vadamala_count = seva_list.count_documents({"seva_type": "Vadamala"})
    
    print(f"Found {abhisheka_count} existing Abhisheka sevas")
    print(f"Found {alankara_count} existing Alankara sevas")
    print(f"Found {vadamala_count} existing Vadamala sevas")
    
    # Remove existing fixed sevas
    seva_list.delete_many({"seva_type": {"$in": ["Abhishekas", "Alankar", "Vadamala"]}})
    print("Removed existing fixed sevas")
    
    # Insert new fixed sevas
    all_fixed_sevas = []
    
    # Convert the hard-coded sevas to database format
    for seva in ABHISHEKA_SEVAS:
        db_seva = {
            "seva_id": seva["id"],
            "seva_type": seva["seva_type"],
            "seva_name": seva["seva_name"],
            "seva_price": seva["seva_price"],
            "seva_description": seva["seva_description"],
            "seva_date": seva["seva_date"]
        }
        all_fixed_sevas.append(db_seva)
    
    for seva in ALANKARA_SEVAS:
        db_seva = {
            "seva_id": seva["id"],
            "seva_type": seva["seva_type"],
            "seva_name": seva["seva_name"],
            "seva_price": seva["seva_price"],
            "seva_description": seva["seva_description"],
            "seva_date": seva["seva_date"]
        }
        all_fixed_sevas.append(db_seva)
    
    for seva in VADAMALA_SEVAS:
        db_seva = {
            "seva_id": seva["id"],
            "seva_type": seva["seva_type"],
            "seva_name": seva["seva_name"],
            "seva_price": seva["seva_price"],
            "seva_description": seva["seva_description"],
            "seva_date": seva["seva_date"]
        }
        all_fixed_sevas.append(db_seva)
    
    # Insert all fixed sevas
    if all_fixed_sevas:
        result = seva_list.insert_many(all_fixed_sevas)
        print(f"Inserted {len(result.inserted_ids)} fixed sevas")
    else:
        print("No fixed sevas to insert")
    
    # Count sevas after initialization
    abhisheka_count = seva_list.count_documents({"seva_type": "Abhishekas"})
    alankara_count = seva_list.count_documents({"seva_type": "Alankar"})
    vadamala_count = seva_list.count_documents({"seva_type": "Vadamala"})
    pooja_count = seva_list.count_documents({"seva_type": "Pooja/Vratha"})
    
    print(f"Now have {abhisheka_count} Abhisheka sevas")
    print(f"Now have {alankara_count} Alankara sevas")
    print(f"Now have {vadamala_count} Vadamala sevas")
    print(f"Now have {pooja_count} Pooja/Vratha sevas (managed by admin)")

if __name__ == "__main__":
    load_dotenv()
    
    # Check if MongoDB URI is set
    mongodb_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not mongodb_uri:
        print("Error: No MongoDB connection string found in environment variables!")
        print("Please set MONGODB_URI or MONGO_URI in your .env file")
        exit(1)
    
    # Initialize fixed sevas
    init_fixed_sevas()
    print("Fixed sevas initialization complete!") 