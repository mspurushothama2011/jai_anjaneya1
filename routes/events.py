from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import events_collection
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import pytz
from functools import wraps
from utils import get_current_time

events_bp = Blueprint("events", __name__, url_prefix="/admin")

#admin required to use admin side pages

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please login as admin to access this page.", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function

#automatically delete events that are more than 30 days old

@events_bp.before_request
def auto_delete_past_events():
    """Automatically delete events that are more than 30 days old"""
    # Get today's date for reference - use the same year as in the database (2025)
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    # Check if any events exist to get their year
    sample_event = events_collection.find_one()
    if sample_event and isinstance(sample_event.get('date'), datetime):
        # Use the year from the database events
        target_year = sample_event['date'].year
        # Adjust current date to match the year from the database
        current_date = current_date.replace(year=target_year)
    
    thirty_days_ago = current_date - timedelta(days=30)
    
    # Delete events where the date is more than 30 days in the past
    result = events_collection.delete_many({"date": {"$lt": thirty_days_ago}})

    if result.deleted_count > 0:
        print(f"✅ Deleted {result.deleted_count} events older than 30 days.")

#admin manage events page
@events_bp.route("/events")
@admin_required
def list_events():
    """List all events"""
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    # Ensure current_date is naive
    if hasattr(current_date, 'tzinfo') and current_date.tzinfo is not None:
        current_date = current_date.replace(tzinfo=None)
    all_events = list(events_collection.find())
    def to_naive(dt):
        if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    upcoming_events = [e for e in all_events if e.get("date") and to_naive(e["date"]) >= current_date]
    past_events = [e for e in all_events if e.get("date") and to_naive(e["date"]) < current_date]
    return render_template(
        "admin/manage_events.html",
        upcoming_events=upcoming_events,
        past_events=past_events,
        current_date=current_date
    )

@events_bp.route("/events/past")
@admin_required
def past_events():
    """List past events"""
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    # Query for events before the current date
    events = list(events_collection.find({"date": {"$lt": current_date}}).sort("date", -1))
    return render_template("admin/past_events.html", events=events)

@events_bp.route("/events/upcoming")
@admin_required
def upcoming_events():
    """List upcoming events"""
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    # Query for events on or after the current date
    events = list(events_collection.find({"date": {"$gte": current_date}}).sort("date", 1))
    return render_template("admin/upcoming_events.html", events=events)

#admin add event page
@events_bp.route("/add_event", methods=["GET", "POST"])
@admin_required
def add_event():
    """Handle form submission to add a new event"""
    try:
        # Convert input date (string) to a real datetime object
        event_date = datetime.strptime(request.form["date"], "%Y-%m-%d")
        
        # Check if any events exist to get the target year
        sample_event = events_collection.find_one()
        if sample_event and isinstance(sample_event.get('date'), datetime):
            # Use the year from existing events for consistency
            target_year = sample_event['date'].year
            # If the event year doesn't match existing events, update it
            if event_date.year != target_year:
                event_date = event_date.replace(year=target_year)

        new_event = {
            "title": request.form["title"],
            "date": event_date,  # Store as datetime
            "venue": request.form["venue"],
            "description": request.form["description"],
        }
        events_collection.insert_one(new_event)

        flash("Event added successfully!", "success")
    except Exception as e:
        print(f"❌ Error adding event: {str(e)}")
        flash(f"Error adding event: {str(e)}", "error")

    return redirect(url_for("events.list_events"))  # Redirect to events page after adding event

#admin delete event page

@events_bp.route("/delete-event/<event_id>", methods=["POST"])
@admin_required
def delete_event(event_id):
    """Delete an event manually"""
    try:
        events_collection.delete_one({"_id": ObjectId(event_id)})
        flash("Event deleted successfully!", "success")
    except:
        flash("Failed to delete Event. Please try again.", "error")

    return redirect(url_for("events.list_events"))  # Refresh events page after deletion

#admin cleanup past events page

@events_bp.route("/cleanup-past-events", methods=["POST"])
def cleanup_past_events():
    """Manually delete all past events (older than today)"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    # Get current date - handle year adjustment
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Check if any events exist to get their year
    sample_event = events_collection.find_one()
    if sample_event and isinstance(sample_event.get('date'), datetime):
        # Use the year from the database events
        target_year = sample_event['date'].year
        # Adjust current date to match the year from the database
        current_date = current_date.replace(year=target_year)
    
    result = events_collection.delete_many({"date": {"$lt": current_date}})
    
    if result.deleted_count > 0:
        flash(f"Successfully deleted {result.deleted_count} past events.", "success")
    else:
        flash("No past events to delete.", "info")
        
    return redirect(url_for("events.list_events"))


#user event page

@events_bp.route("/event")
def event():
    """Fetch and display all events for user, split into upcoming and past"""
    today = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    # Ensure today is naive
    if hasattr(today, 'tzinfo') and today.tzinfo is not None:
        today = today.replace(tzinfo=None)
    all_events = list(events_collection.find())
    def to_naive(dt):
        if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    upcoming_events = [e for e in all_events if e.get("date") and to_naive(e["date"]) >= today]
    past_events = [e for e in all_events if e.get("date") and to_naive(e["date"]) < today]
    for event in all_events:
        event["_id"] = str(event["_id"])  # Convert ObjectId to string for rendering
    return render_template("events.html", upcoming_events=upcoming_events, past_events=past_events, current_date=today)