from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import bcrypt
from database import user_collection
from bson.objectid import ObjectId

from extensions import limiter

api_auth_bp = Blueprint("api_auth", __name__)

@api_auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    """Mobile API Login - Returns JWT Token"""
    data = request.get_json()
    
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Email and password are required"}), 400
        
    email = data.get("email")
    password = data.get("password")
    
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"success": False, "message": "Invalid input format"}), 400
    
    # Fetch user from MongoDB
    user = user_collection.find_one({"email": email})
    
    if not user:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
        
    hashed_password = user.get("password")
    
    # Validate hashed password using bcrypt
    if hashed_password and bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8")):
        # Create JWT token containing the user's ID as a string
        access_token = create_access_token(identity=str(user["_id"]))
        refresh_token = create_refresh_token(identity=str(user["_id"]))
        
        # Return the token and basic user info
        return jsonify({
            "success": True, 
            "message": "Login successful",
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": str(user["_id"]),
                "name": user.get("name", ""),
                "email": user.get("email", "")
            }
        }), 200
    else:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

@api_auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_user_profile():
    """Get the current logged-in user's profile using JWT"""
    # get_jwt_identity() returns the identity we passed into create_access_token()
    current_user_id = get_jwt_identity()
    
    user = user_collection.find_one({"_id": ObjectId(current_user_id)})
    
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
        
    # Return user profile (exclude password)
    return jsonify({
        "success": True,
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", "")
        }
    }), 200

@api_auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """Refresh the access token using a valid refresh token"""
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify({
        "success": True,
        "token": new_access_token
    }), 200
