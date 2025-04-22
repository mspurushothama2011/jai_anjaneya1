from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from database import seva_collection, donations_collection, seva_list, donations_list, events_collection  
from datetime import datetime
import os

general_bp = Blueprint("general", __name__)

@general_bp.route("/")
def home():
    return render_template("user/index.html")

@general_bp.route("/gallery")
def gallery():
    """Display all images from the gallery folder"""
    # Path to the gallery folder within static/images
    gallery_path = os.path.join('static', 'images', 'gallery')
    print(f"Gallery path: {gallery_path}")
    print(f"Gallery path exists: {os.path.exists(gallery_path)}")
    
    # Get all image files from the directory
    image_files = []
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    # Check if directory exists
    if os.path.exists(gallery_path):
        for file in os.listdir(gallery_path):
            # Check if it's an image file
            ext = os.path.splitext(file)[1].lower()
            if ext in allowed_extensions:
                image_files.append(file)
                print(f"Found image: {file}")
    
    # Create full paths for template (use forward slashes for URLs)
    gallery_images = []
    for img in image_files:
        img_path = 'images/gallery/' + img
        gallery_images.append(img_path)
    
    print(f"Number of images found: {len(gallery_images)}")
    return render_template("user/gallery.html", gallery_images=gallery_images)

@general_bp.route("/pooja-timings")
def pooja_timings():
    return render_template("user/pooja_timings.html")

@general_bp.route("/events")
def events():
    """User view to display events"""
    # Get today's date for comparison
    current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Fetch all events
    events_data = list(events_collection.find())
    print(f"Found {len(events_data)} total events in the database")
    
    # Manually create a sample event if none exist (for testing)
    if not events_data:
        print("No events found, creating sample events")
        sample_events = [
            {
                "title": "Navratri Celebration",
                "date": datetime(2025, 4, 18),
                "venue": "Temple Grounds",
                "description": "Nine days of music and dance celebrating the Divine Mother"
            },
            {
                "title": "Diwali Festival",
                "date": datetime(2025, 4, 28),
                "venue": "Temple Complex",
                "description": "Festival of lights with special ceremonies and cultural programs"
            },
            {
                "title": "Yoga Workshop",
                "date": datetime(2025, 4, 3),
                "venue": "Meditation Hall",
                "description": "Learn traditional yoga practices with experienced teachers"
            }
        ]
        events_data = sample_events
    
    # Process events data
    for event in events_data:
        # Convert ObjectId to string for MongoDB documents
        if "_id" in event:
            event["_id"] = str(event["_id"])
            
        # Ensure date is a datetime object
        if not isinstance(event.get("date"), datetime):
            try:
                if isinstance(event.get("date"), str):
                    event["date"] = datetime.strptime(event["date"], "%Y-%m-%d")
            except ValueError:
                event["date"] = datetime.now()  # Fallback to today's date if parsing fails
        
        print(f"Event: {event.get('title', 'No title')} - Date: {event.get('date')}")

    # Sort events by date
    events_data.sort(key=lambda x: x["date"])
    
    return render_template("user/events.html", events=events_data, current_date=current_date)

@general_bp.route("/history")
def general_history():
    # If user is logged in, redirect to user history
    if "user_id" in session:
        return redirect(url_for("user.history", filter=request.args.get("filter", "all")))
    
    # If not logged in, show message and redirect to login
    flash("Please login to view your history", "warning")
    return redirect(url_for("user.login"))

@general_bp.route("/temple_history")
def general_temhistory():
    return render_template("user/temple_history.html")


@general_bp.route("/donation")
def user_donations():
    """User donations page"""
    donations_data = list(donations_list.find({}))  # ✅ Fetch all donation details with _id

    # Convert ObjectId to string for template use
    for donation in donations_data:
        donation["_id"] = str(donation["_id"])

    return render_template("user/user_donation.html", donations=donations_data)

@general_bp.route("/e_hundi")
def e_hundi():
    return render_template("user/e_hundi.html")

@general_bp.route("/general-sevas")
def get_general_sevas():  
    """Public view to display available sevas"""
    sevas_data = list(seva_list.find())  

    for seva in sevas_data:
        seva["_id"] = str(seva["_id"])  # Convert ObjectId to string

    return render_template("user/user_seva_list.html", sevas=sevas_data, seva_types=set(seva["seva_type"] for seva in sevas_data))

@general_bp.route("/logout")
def logout():
    """General Logout"""
    # Clear all session data
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("general.home"))  

@general_bp.route("/privacy-policy")
def privacy_policy():
    """Display the privacy policy page"""
    return render_template("user/legal/privacy_policy.html")

@general_bp.route("/terms-of-service")
def terms_of_service():
    """Display the terms of service page"""
    return render_template("user/legal/terms_of_service.html")  

@general_bp.route("/contact")
def contact():
    """Display the contact page"""
    return render_template("user/contact.html")  
