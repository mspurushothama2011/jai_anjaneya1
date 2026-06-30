from flask import Blueprint, jsonify, url_for
from database import gallery_collection
from bson.objectid import ObjectId

api_general_bp = Blueprint("api_general", __name__)

@api_general_bp.route("/gallery", methods=["GET"])
def get_gallery():
    """Returns a list of gallery images for the mobile app."""
    try:
        # Fetch gallery images (exclude raw image_data for the list)
        gallery_items = list(gallery_collection.find({}, {"image_data": 0}).sort("upload_date", -1))
        
        formatted_gallery = []
        for item in gallery_items:
            image_id = str(item["_id"])
            formatted_gallery.append({
                "id": image_id,
                "title": item.get("title", "Temple Image"),
                "description": item.get("description", ""),
                # Use the existing web route to serve the image
                "image_url": url_for("general.get_gallery_image", image_id=image_id, _external=True)
            })
            
        return jsonify({
            "success": True,
            "data": formatted_gallery
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@api_general_bp.route("/check-update", methods=["GET"])
def check_update():
    """Returns latest mobile version info and download URL from the website."""
    # To trigger an update prompt in the app, set build_number to a value greater than 1
    # and update latest_version / release_notes accordingly.
    return jsonify({
        "success": True,
        "latest_version": "1.0.0",
        "build_number": 1,
        "apk_url": "https://www.sriveeranjaneyaswamy.org.in/static/downloads/app-release.apk",
        "release_notes": "First release of Sri Veeranjaneya Swamy Temple mobile app.",
        "mandatory": False
    }), 200

