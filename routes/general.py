from flask import Blueprint, render_template, session, redirect, url_for, flash, request, Response
from database import seva_collection, donations_collection, seva_list, donations_list, events_collection, gallery_collection
from datetime import datetime
from bson import ObjectId
import os
from utils import get_current_time

general_bp = Blueprint("general", __name__)

@general_bp.route("/")
def home():
    return render_template("user/index.html")

@general_bp.route("/gallery")
def gallery():
    """Display all images from the database"""
    # Fetch images from MongoDB, sorted by newest first
    # Only fetch _id to generate URLs, we don't need the binary data here
    gallery_images = list(gallery_collection.find({}, {"image_data": 0}).sort("upload_date", -1))
    
    # Convert IDs to string
    for img in gallery_images:
        img['_id'] = str(img['_id'])
        
    return render_template("user/gallery.html", gallery_images=gallery_images)

@general_bp.route("/gallery/image/<image_id>")
def get_gallery_image(image_id):
    """Serve a gallery image from the database"""
    try:
        image = gallery_collection.find_one({"_id": ObjectId(image_id)})
        if image and "image_data" in image:
            return Response(image["image_data"], mimetype=image.get("content_type", "image/jpeg"))
        else:
            return "Image not found", 404
    except Exception as e:
        return f"Error: {str(e)}", 500

@general_bp.route("/pooja-timings")
def pooja_timings():
    return render_template("user/pooja_timings.html")

@general_bp.route("/events")
def events():
    """Fetch and display upcoming and past events"""
    current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
    def to_naive(dt):
        if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    current_date = to_naive(current_date)
    events_data = list(events_collection.find())

    # Ensure all event dates are datetime objects and naive
    for event in events_data:
        if not isinstance(event.get("date"), datetime):
            try:
                if isinstance(event.get("date"), str):
                    event["date"] = datetime.strptime(event["date"], "%Y-%m-%d")
            except (ValueError, TypeError):
                event["date"] = current_date
        event["date"] = to_naive(event["date"])
        if "_id" in event:
            event["_id"] = str(event["_id"])

    # Split into upcoming and past events
    upcoming_events = [e for e in events_data if e.get("date") and e["date"] >= current_date]
    past_events = [e for e in events_data if e.get("date") and e["date"] < current_date]
    upcoming_events.sort(key=lambda x: x["date"])
    past_events.sort(key=lambda x: x["date"], reverse=True)

    return render_template("user/events.html", upcoming_events=upcoming_events, past_events=past_events, current_date=current_date)

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
def redirect_to_seva_categories():  
    """Redirects the old sevas page to the new category-based view."""
    return redirect(url_for("user_seva.seva_categories_view"))

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
