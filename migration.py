from database import seva_collection, alankara_bookings, vadamala_slots
from pymongo.errors import DuplicateKeyError

def migrate_alankara():
    """Migrates Alankara bookings from seva_collection to alankara_bookings."""
    print("Starting Alankara migration...")
    alankara_sevas = list(seva_collection.find({"seva_name": "Alankara"}))
    migrated_count = 0
    
    for seva in alankara_sevas:
        booking_doc = {
            "_id": seva["seva_date"],
            **seva
        }
        try:
            alankara_bookings.insert_one(booking_doc)
            seva_collection.delete_one({"_id": seva["_id"]})
            migrated_count += 1
        except DuplicateKeyError:
            print(f"Skipping duplicate Alankara booking for date: {seva['seva_date']}")
            # Assumes the one in the new collection is correct, deletes the old one
            seva_collection.delete_one({"_id": seva["_id"]})

    print(f"Migrated {migrated_count} Alankara bookings.")

def migrate_vadamala():
    """Migrates Vadamala bookings to the new vadamala_slots collection."""
    print("Starting Vadamala migration...")
    vadamala_sevas = list(seva_collection.find({"seva_name": "Vadamala"}))
    
    # Group bookings by date
    slots = {}
    for seva in vadamala_sevas:
        date_str = seva["seva_date"]
        if date_str not in slots:
            slots[date_str] = []
        
        slots[date_str].append({
            "booking_id": seva["_id"],
            "user_id": seva["user_id"],
            "payment_id": seva["payment_id"],
            "order_id": seva["order_id"],
            "booking_timestamp": seva["booking_date"],
            "status": seva["status"]
        })

    migrated_count = 0
    for date_str, bookings in slots.items():
        vadamala_slots.update_one(
            {"_id": date_str},
            {"$push": {"bookings": {"$each": bookings}}},
            upsert=True
        )
        migrated_count += len(bookings)

    # Delete the old Vadamala bookings from seva_collection
    seva_collection.delete_many({"seva_name": "Vadamala"})
    
    print(f"Migrated {migrated_count} Vadamala bookings into daily slots.")

if __name__ == "__main__":
    migrate_alankara()
    migrate_vadamala()
    print("Data migration complete!")