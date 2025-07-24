from database import seva_collection, db
from datetime import datetime

# Define the new dedicated collections
alankara_bookings_collection = db["alankara_bookings"]
vadamala_bookings_collection = db["vadamala_bookings"]

def migrate_alankara_bookings():
    """Migrates Alankara bookings from seva_collection to a dedicated collection."""
    print("Starting Alankara booking migration...")
    alankara_sevas = seva_collection.find({"seva_name": "Alankara"})
    
    migrated_count = 0
    for seva in alankara_sevas:
        try:
            # The new collection uses the seva_date as the _id
            new_booking = {
                "_id": seva["seva_date"],
                "user_id": seva["user_id"],
                "user_name": seva.get("user_name"),
                "email": seva.get("email"),
                "phone": seva.get("phone"),
                "seva_id": seva["seva_id"],
                "seva_name": "Alankara",
                "seva_type": seva.get("seva_type"),
                "seva_price": seva.get("seva_price"),
                "booking_date": seva.get("booking_date"),
                "payment_id": seva.get("payment_id"),
                "order_id": seva.get("order_id"),
                "status": seva.get("status", "Not Collected")
            }
            alankara_bookings_collection.insert_one(new_booking)
            # Optionally, remove the old record
            # seva_collection.delete_one({"_id": seva["_id"]})
            migrated_count += 1
        except Exception as e:
            print(f"Could not migrate Alankara booking {seva['_id']}: {e}")
            
    print(f"Successfully migrated {migrated_count} Alankara bookings.")

def migrate_vadamala_bookings():
    """Migrates Vadamala bookings to a new day-based document structure."""
    print("Starting Vadamala booking migration...")
    vadamala_sevas = seva_collection.find({"seva_name": "Vadamala"})
    
    migrated_count = 0
    for seva in vadamala_sevas:
        try:
            seva_date_obj = datetime.strptime(seva["seva_date"], "%d-%m-%Y")

            booking_details = {
                "booking_id": seva["_id"],
                "user_id": seva["user_id"],
                "user_name": seva.get("user_name"),
                "email": seva.get("email"),
                "phone": seva.get("phone"),
                "seva_type": seva.get("seva_type"),
                "seva_price": seva.get("seva_price"),
                "booking_date": seva.get("booking_date"),
                "payment_id": seva.get("payment_id"),
                "order_id": seva.get("order_id"),
                "status": seva.get("status", "Not Collected"),
            }
            
            vadamala_bookings_collection.update_one(
                {"_id": seva_date_obj},
                {
                    "$push": {"bookings": booking_details},
                    "$inc": {"bookings_count": 1}
                },
                upsert=True
            )
            # Optionally, remove the old record
            # seva_collection.delete_one({"_id": seva["_id"]})
            migrated_count += 1
        except Exception as e:
            print(f"Could not migrate Vadamala booking {seva['_id']}: {e}")
            
    print(f"Successfully migrated {migrated_count} Vadamala bookings.")

if __name__ == "__main__":
    migrate_alankara_bookings()
    migrate_vadamala_bookings()
    print("\nMigration complete. It is recommended to remove or rename this script now.") 