from datetime import datetime, timedelta
from database import seva_collection, donations_collection
from pymongo import DeleteOne

def cleanup_old_records():
    now = datetime.now()
    one_year_ago = now - timedelta(days=365)
    one_year_ago_naive = one_year_ago.replace(tzinfo=None)

    # --- Seva Collection ---
    seva_dt = seva_collection.delete_many({
        "seva_date": {"$lte": one_year_ago_naive}
    })
    seva_str_docs = seva_collection.find({"seva_date": {"$type": "string"}})
    seva_to_delete = []
    seva_formats = ["%d-%m-%Y (%H:%M:%S)", "%Y-%m-%d", "%d-%m-%Y"]
    for doc in seva_str_docs:
        for fmt in seva_formats:
            try:
                parsed_date = datetime.strptime(doc["seva_date"], fmt)
                if parsed_date <= one_year_ago_naive:
                    seva_to_delete.append(DeleteOne({"_id": doc["_id"]}))
                break  # Stop after first successful parse
            except Exception:
                continue
    if seva_to_delete:
        seva_collection.bulk_write(seva_to_delete)

    # --- Donation Collection ---
    donation_dt = donations_collection.delete_many({
        "donation_date": {"$lte": one_year_ago_naive}
    })
    donation_str_docs = donations_collection.find({"donation_date": {"$type": "string"}})
    donation_to_delete = []
    donation_formats = ["%d-%m-%Y (%H:%M:%S)", "%Y-%m-%d", "%d-%m-%Y"]
    for doc in donation_str_docs:
        for fmt in donation_formats:
            try:
                parsed_date = datetime.strptime(doc["donation_date"], fmt)
                if parsed_date <= one_year_ago_naive:
                    donation_to_delete.append(DeleteOne({"_id": doc["_id"]}))
                break
            except Exception:
                continue
    if donation_to_delete:
        donations_collection.bulk_write(donation_to_delete) 