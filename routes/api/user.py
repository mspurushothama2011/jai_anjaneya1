from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import seva_collection, donations_collection, user_collection
from bson.objectid import ObjectId

api_user_bp = Blueprint("api_user", __name__)

@api_user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    """Returns basic profile information for the logged-in user."""
    try:
        user_id = ObjectId(get_jwt_identity())
        user = user_collection.find_one({"_id": user_id})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        return jsonify({
            "success": True,
            "data": {
                "name": user.get("name", user.get("username", "")),
                "email": user.get("email", ""),
                "dob": user.get("dob", ""),
                "phone": user.get("phone", ""),
                "address": user.get("address", "")
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@api_user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """Updates profile information for the logged-in user."""
    try:
        user_id = ObjectId(get_jwt_identity())
        data = request.json
        
        update_data = {}
        if "name" in data: update_data["name"] = data["name"]
        if "dob" in data: update_data["dob"] = data["dob"]
        if "phone" in data: update_data["phone"] = data["phone"]
        if "address" in data: update_data["address"] = data["address"]
        
        if not update_data:
            return jsonify({"success": False, "message": "No data to update"}), 400
            
        result = user_collection.update_one({"_id": user_id}, {"$set": update_data})
        
        if result.matched_count == 0:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        return jsonify({"success": True, "message": "Profile updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@api_user_bp.route("/history", methods=["GET"])
@jwt_required()
def get_user_history():
    """
    Mobile API: Returns the logged-in user's booking and donation history.
    Requires a valid JWT token.
    """
    try:
        current_user_id_str = get_jwt_identity()
        user_id = ObjectId(current_user_id_str)
        
        # Fetch data from MongoDB
        seva_bookings = list(seva_collection.find({"user_id": user_id}))
        donations = list(donations_collection.find({"user_id": user_id}))
        
        # Format the data for JSON serialization (convert ObjectIds to strings)
        formatted_history = []
        
        for booking in seva_bookings:
            # Handle datetime objects for seva_date
            seva_date = booking.get("seva_date", "")
            if hasattr(seva_date, "strftime"):
                seva_date = seva_date.strftime("%d-%m-%Y")
                
            formatted_history.append({
                "id": str(booking["_id"]),
                "type": booking.get("seva_name", "Seva"),
                "amount": booking.get("amount", booking.get("seva_price", 0)),
                "date": booking.get("booking_date", ""),
                "seva_date": str(seva_date),
                "status": booking.get("status", "Paid"),
                "payment_id": booking.get("payment_id", ""),
                "order_id": booking.get("order_id", ""),
                "category": "seva"
            })
            
        for donation in donations:
            formatted_history.append({
                "id": str(donation["_id"]),
                "type": donation.get("donation_name", "General Donation"),
                "amount": donation.get("amount", 0),
                "date": donation.get("donation_date", ""),
                "status": donation.get("status", "Paid"),
                "payment_id": donation.get("payment_id", ""),
                "order_id": donation.get("order_id", ""),
                "category": "donation"
            })
            
        # Sort the combined list by date (newest first)
        from datetime import datetime
        def parse_date(date_str):
            if not date_str:
                return datetime.min
            # Try parsing dd-mm-yyyy or yyyy-mm-dd
            try:
                date_only = date_str.split(' ')[0]
                parts = date_only.split('-')
                if len(parts) == 3:
                    if len(parts[0]) == 4:
                        return datetime.strptime(date_only, "%Y-%m-%d")
                    else:
                        return datetime.strptime(date_only, "%d-%m-%Y")
            except Exception:
                pass
            return datetime.min

        formatted_history.sort(key=lambda x: parse_date(x["date"]), reverse=True)

        # Return the combined list
        return jsonify({
            "success": True,
            "data": formatted_history
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
