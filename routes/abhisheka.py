from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import abhisheka_types, abhisheka_bookings, user_collection
from bson.objectid import ObjectId
from datetime import datetime
from utils import get_current_time
from routes.payment import razorpay_client
import hashlib
import hmac
from config import Config
from admin_required import admin_required
from database import abhisheka_types, user_collection, seva_collection  # Import new collections
from utils import get_current_time  # Import for booking date
from datetime import datetime, timedelta  # Import for date calculations

abhisheka_bp = Blueprint("abhisheka", __name__, template_folder='../templates')

# Initialize Abhisheka Types if not exists
def init_abhisheka_types():
    """Initialize default Abhisheka types if collection is empty"""
    if abhisheka_types.count_documents({}) == 0:
        default_types = [
            {
                "seva_type": "Milk Abhisheka",
                "price": 501,
                "description": "Sacred bathing of the deity with pure cow's milk for purity and long life.",
                "is_active": True
            },
            {
                "seva_type": "Honey Abhisheka",
                "price": 751,
                "description": "Sacred bathing of the deity with pure honey for vitality and happiness.",
                "is_active": True
            },
            {
                "seva_type": "Tender Coconut Abhisheka",
                "price": 601,
                "description": "Sacred bathing of the deity with fresh tender coconut water for spiritual cleansing and peace.",
                "is_active": True
            },
            {
                "seva_type": "Panchamrutham Abhisheka",
                "price": 1001,
                "description": "A sacred ritual with five nectars: milk, curd, ghee, honey, and sugar, for overall prosperity.",
                "is_active": True
            }
        ]
        abhisheka_types.insert_many(default_types)
        print("Initialized default Abhisheka types with new format")

# Call this function when the blueprint is registered
init_abhisheka_types()


# New route for the user-facing Abhisheka booking page
@abhisheka_bp.route("/booking")
def abhisheka_booking():
    """Render the Abhisheka booking page for users."""
    if "user_id" not in session:
        flash("Please login to access this page", "warning")
        return redirect(url_for("user.login"))

    try:
        # Get user details from session
        user_id = ObjectId(session["user_id"])
        user = user_collection.find_one({"_id": user_id})
        if not user:
            flash("User not found. Please login again.", "error")
            return redirect(url_for("user.login"))

        # Fetch only active Abhisheka types from the database
        types = list(abhisheka_types.find({"is_active": True}))

        # Get tomorrow's date for the date picker
        tomorrow = get_current_time() + timedelta(days=1)
        min_date = tomorrow.strftime("%Y-%m-%d")

        return render_template(
            "user/book_abhisheka.html",
            user=user,
            abhisheka_types=types,
            min_date=min_date,
            razorpay_key=Config.RAZORPAY_KEY_ID
        )
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("user_seva.seva_list_view"))


# New API endpoint to fetch details for a specific Abhisheka type
@abhisheka_bp.route("/api/details/<seva_type>")
def get_abhisheka_details(seva_type):
    """API endpoint to get the price and description of an Abhisheka type."""
    if "user_id" not in session:
        return jsonify({"error": "Please login to perform this action."}), 401
    try:
        details = abhisheka_types.find_one({"seva_type": seva_type})
        if details:
            # Convert ObjectId to string for JSON serialization
            details["_id"] = str(details["_id"])
            return jsonify(details)
        else:
            return jsonify({"error": "Details not found for the selected type."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@abhisheka_bp.route("/store-abhisheka-details", methods=["POST"])
def store_abhisheka_details():
    """Store abhisheka details in session before payment"""
    try:
        data = request.json
        
        # Store essential data in session
        session["abhisheka_id"] = data.get("seva_id")
        session["abhisheka_name"] = data.get("seva_name")
        session["abhisheka_type"] = data.get("type_name")
        session["abhisheka_price"] = data.get("price")
        session["abhisheka_date"] = data.get("seva_date")
        
        # Make sure session is saved
        session.modified = True
        
        return jsonify({"message": "Abhisheka details stored successfully", "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@abhisheka_bp.route("/abhisheka-payment", methods=["POST"])
def abhisheka_payment():
    """Process abhisheka payment and create Razorpay order"""
    try:
        data = request.json
        seva_id = data.get("seva_id")
        seva_name = data.get("seva_name")
        type_name = data.get("type_name")
        amount = float(data.get("price", 0))
        seva_date = data.get("seva_date")

        if not all([seva_id, seva_name, type_name, amount, seva_date]):
            return jsonify({"error": "Missing required fields"}), 400

        # Store payment type in session
        session["payment_type"] = "abhisheka"
        session["amount"] = amount

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"abhisheka_{get_current_time().strftime('%d-%m-%Y %H:%M')}",
            "payment_capture": 1,
            "notes": {
                "seva_name": seva_name,
                "seva_date": seva_date,
                "seva_id": seva_id,
                "type_name": type_name
            }
        })

        if not order.get("id"):
            return jsonify({"error": "Failed to create order"}), 500

        # Store order ID in session
        session["order_id"] = order["id"]

        return jsonify(order)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@abhisheka_bp.route("/verify-abhisheka-payment", methods=["POST"])
def verify_abhisheka_payment():
    """Verifies Razorpay payment and stores the abhisheka booking"""
    try:
        data = request.json
        print("--- Verifying Abhisheka Payment ---")
        print(f"Received data: {data}")

        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature")
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return jsonify({"status": "error", "message": "Missing payment verification data"}), 400
            
        # Get and validate session data
        user_id = session.get("user_id")
        abhisheka_id = session.get("abhisheka_id")
        abhisheka_name = session.get("abhisheka_name")
        abhisheka_type = session.get("abhisheka_type")
        abhisheka_price = session.get("abhisheka_price")
        abhisheka_date = session.get("abhisheka_date")
        
        print(f"Session data - User ID: {user_id}, Seva ID: {abhisheka_id}, Price: {abhisheka_price}")

        if not all([user_id, abhisheka_id, abhisheka_name, abhisheka_type, abhisheka_price, abhisheka_date]):
            print("Verification failed: Missing required session data.")
            return jsonify({"status": "error", "message": "Your session may have expired. Please try booking again."}), 400
        
        # Verify Razorpay signature
        key_secret = Config.RAZORPAY_KEY_SECRET
        generated_signature = hmac.new(
            key_secret.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != razorpay_signature:
            print(f"Verification failed: Invalid signature. Generated: {generated_signature}, Received: {razorpay_signature}")
            return jsonify({"status": "error", "message": "Payment signature verification failed."}), 400
        
        print("Payment signature verified successfully.")
        
        if not user_id:
            return jsonify({"status": "error", "message": "User not logged in"}), 401

        # Get user details
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Store booking in seva_collection
        formatted_time = get_current_time().strftime("%d-%m-%Y (%H:%M:%S)")
        
        # Create booking record in the same format as other sevas
        abhisheka_booking_db = {
            "user_id": ObjectId(user_id),
            "user_name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "seva_id": abhisheka_id, # This is the ID from abhisheka_types collection
            "seva_name": abhisheka_name, # e.g., "Abhisheka"
            "seva_type": abhisheka_type, # e.g., "Milk Abhisheka"
            "seva_price": float(abhisheka_price),
            "booking_date": formatted_time,
            "seva_date": abhisheka_date,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "status": "Not Collected"
        }
        
        # Insert into the database
        seva_collection.insert_one(abhisheka_booking_db)
        
        # --- Store complete booking details in session for the confirmation page ---
        abhisheka_booking_db['_id'] = str(abhisheka_booking_db['_id'])
        abhisheka_booking_db['user_id'] = str(abhisheka_booking_db['user_id'])
        
        session['seva_booking'] = abhisheka_booking_db

        # Clear temporary session data
        session.pop("abhisheka_id", None)
        session.pop("abhisheka_name", None)
        session.pop("abhisheka_type", None)
        session.pop("abhisheka_price", None)
        session.pop("abhisheka_date", None)
        session.pop("order_id", None)
        session.modified = True
        
        # Redirect to the centralized confirmation page
        return jsonify({
            "status": "success", 
            "message": "Booking successful!", 
            "redirect_url": url_for('payment.payment_confirmation_page')
        })

    except Exception as e:
        print(f"Error in Abhisheka payment verification: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {e}"}), 500


@abhisheka_bp.route("/abhisheka-confirmation")
def abhisheka_confirmation():
    """This route is deprecated. The new confirmation page is handled by the payment blueprint."""
    flash("This page is no longer in use. Please check your dashboard for booking details.", "info")
    return redirect(url_for('user.dashboard')) 