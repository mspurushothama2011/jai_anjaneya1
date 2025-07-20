"""
utils.py

Purpose:
    - Provides timezone and datetime utility functions (IST conversion, formatting, etc.).
    - Used by seva_config.py and other parts of the app for time handling.

Note:
    - This file is required for correct time handling in the app.
    - Do not remove unless you refactor all time utilities elsewhere.
"""
from datetime import datetime, timedelta
import pytz
from dateutil import tz

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
def get_current_time(timezone_str="Asia/Kolkata"):
    """
    Get current time in the specified timezone.
    Default is Asia/Kolkata (IST) if no timezone is provided.
    """
    # Get current UTC time with timezone info
    utc = datetime.now(tz.tzutc())
    
    # Convert to target timezone
    to_zone = tz.gettz(timezone_str)
    if not to_zone:
        # Fallback to IST if timezone is invalid
        to_zone = tz.gettz("Asia/Kolkata")
    
    # Convert UTC to target timezone
    local_time = utc.astimezone(to_zone)
    
    return local_time

# Format time in a specific timezone
def format_time_in_timezone(dt, timezone_str="Asia/Kolkata", format_str="%Y-%m-%d %H:%M:%S"):
    """Format a datetime in the specified timezone"""
    to_zone = tz.gettz(timezone_str)
    if not to_zone:
        to_zone = tz.gettz("Asia/Kolkata")
    
    # Convert to target timezone if it's timezone-aware
    if dt.tzinfo:
        dt = dt.astimezone(to_zone)
        
    return dt.strftime(format_str) 