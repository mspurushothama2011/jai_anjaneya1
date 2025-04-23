from datetime import datetime, timedelta
import pytz

def utc_to_ist(utc_datetime):
    """Convert UTC datetime to IST (Indian Standard Time)"""
    if isinstance(utc_datetime, str):
        try:
            utc_datetime = datetime.strptime(utc_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Try other common formats if the first one fails
            try:
                utc_datetime = datetime.strptime(utc_datetime, "%Y-%m-%d")
            except ValueError:
                return utc_datetime  # Return as is if we can't parse it
    
    # Add 5 hours and 30 minutes to convert from UTC to IST
    ist_datetime = utc_datetime + timedelta(hours=5, minutes=30)
    return ist_datetime

def format_datetime_ist(utc_datetime, format_string="%Y-%m-%d %H:%M:%S"):
    """Format a UTC datetime as IST with the specified format"""
    ist_datetime = utc_to_ist(utc_datetime)
    if isinstance(ist_datetime, datetime):
        return ist_datetime.strftime(format_string)
    return str(ist_datetime)  # Fallback for non-datetime objects

# Create a timezone-aware datetime utility function
def get_current_time():
    # First get UTC time
    utc_now = datetime.now(pytz.UTC)
    
    # Convert to IST (UTC+5:30)
    india_tz = pytz.timezone('Asia/Kolkata')
    ist_now = utc_now.astimezone(india_tz)
    
    return ist_now 