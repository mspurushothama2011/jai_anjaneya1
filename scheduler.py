from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from database import seva_collection
import pytz

# Set your timezone if needed
TIMEZONE = pytz.timezone('Asia/Kolkata')

def delete_old_seva_bookings():
    """Delete seva_collection records with seva_date older than 1 year from today."""
    now = datetime.now(TIMEZONE)
    one_year_ago = now - timedelta(days=365)
    # Remove timezone info for comparison if needed
    one_year_ago_naive = one_year_ago.replace(tzinfo=None)
    result = seva_collection.delete_many({
        "seva_date": {"$lt": one_year_ago_naive}
    })
    print(f"[Scheduler] Deleted {result.deleted_count} old seva bookings (older than 1 year)")

scheduler = BackgroundScheduler(timezone=TIMEZONE)
scheduler.add_job(delete_old_seva_bookings, 'cron', hour=0, minute=0)  # Run daily at midnight
scheduler.start()

# To keep the scheduler running if this is a standalone script
if __name__ == "__main__":
    import time
    print("Scheduler started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown() 