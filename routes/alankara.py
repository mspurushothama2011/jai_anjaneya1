from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import seva_collection, user_collection, db
from bson.objectid import ObjectId
from datetime import datetime, timedelta, date, timezone
from utils import get_current_time
from config import Config
import hmac
import hashlib

alankara_bp = Blueprint("alankara", __name__, template_folder='../templates')

# Define the collection for Alankara types
alankara_types = db["alankara_types"]

def init_alankara_types():
    """Initialize default Alankara types if the collection is empty."""
    if alankara_types.count_documents({}) == 0:
        default_types = [
            {"seva_type": "Butter Alankara", "price": 1501, "description": "A cooling and soothing decoration using fresh butter.", "is_active": True},
            {"seva_type": "Betel Leaf Alankara", "price": 1201, "description": "An intricate decoration made from sacred betel leaves.", "is_active": True},
            {"seva_type": "Sindoor Alankara", "price": 1101, "description": "A vibrant decoration using holy sindoor (vermilion).", "is_active": True},
            {"seva_type": "Sri Gandha Alankara", "price": 1801, "description": "A fragrant decoration using pure sandalwood paste.", "is_active": True},
            {"seva_type": "Silver Cladding (Kavacha)", "price": 5001, "description": "A special covering of the deity with an embossed silver plate.", "is_active": True}
        ]
        alankara_types.insert_many(default_types)
        print("Initialized default Alankara types.")

init_alankara_types()

@alankara_bp.route("/booking")
def alankara_booking():
    """Renders the booking page for Alankara sevas."""
    if "user_id" not in session:
        flash("Please login to book a seva.", "warning")
        return redirect(url_for("user.login"))

    user = user_collection.find_one({"_id": ObjectId(session["user_id"])})

    # Fetch already booked seva_date values for any Alankara seva
    booked_seva_dates = [
        record['seva_date'].strftime("%Y-%m-%d") if isinstance(record['seva_date'], (datetime, date))
        else record['seva_date']
        for record in seva_collection.find(
            {"seva_name": "Alankara"},
            {"seva_date": 1, "_id": 0}
        )
    ]

    # Calculate available dates, starting from tomorrow
    available_dates = []
    start_date = date.today() + timedelta(days=1)  # Bookings must be made 1 day in advance

    for i in range(60):
        current_date = start_date + timedelta(days=i)
        # Tuesday is 1, Thursday is 3
        if current_date.weekday() in [1, 3]:
            date_str = current_date.strftime("%Y-%m-%d")
            if date_str not in booked_seva_dates:
                available_dates.append(date_str)
    
    types = list(alankara_types.find({"is_active": True}))

    return render_template(
        "user/book_alankara.html",
        user=user,
        alankara_types=types,
        available_dates=available_dates,
        razorpay_key=Config.RAZORPAY_KEY_ID
    )

@alankara_bp.route("/store-alankara-details", methods=["POST"])
def store_alankara_details():
    """Stores the details of the selected Alankara seva in the session."""
    try:
        data = request.json
        session['alankara_seva_id'] = data.get('seva_id')
        session['alankara_seva_date'] = data.get('seva_date')
        session.modified = True
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@alankara_bp.route("/alankara-payment", methods=["POST"])
def alankara_payment():
    """Creates a Razorpay order for the Alankara seva."""
    if "user_id" not in session:
        return jsonify({"error": "User not logged in"}), 401
    
    try:
        data = request.json
        seva_id = data.get("seva_id")
        
        # Get price from the database to ensure it hasn't been tampered with
        seva_type = alankara_types.find_one({"_id": ObjectId(seva_id)})
        if not seva_type:
            return jsonify({"error": "Invalid Seva ID"}), 400
        
        amount = seva_type.get("price")
        
        from routes.payment import razorpay_client
        order = razorpay_client.order.create({
            "amount": int(amount * 100),
            "currency": "INR",
            "receipt": f"alankara_{get_current_time().strftime('%Y%m%d%H%M%S')}"
        })
        return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@alankara_bp.route("/verify-alankara-payment", methods=["POST"])
def verify_alankara_payment():
    """Verifies the payment and creates the booking in the seva_collection."""
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "User session expired."}), 401

    try:
        data = request.json
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")
        
        # Get details from session
        seva_id = session.get("alankara_seva_id")
        seva_date = session.get("alankara_seva_date")
        # Convert seva_date to datetime in UTC if possible
        try:
            seva_date_obj = datetime.strptime(seva_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            seva_date_obj = seva_date

        if not all([seva_id, seva_date_obj]):
            return jsonify({"status": "error", "message": "Session data missing. Please try again."})

        # Get authoritative data from the database
        seva_type_details = alankara_types.find_one({"_id": ObjectId(seva_id)})
        user = user_collection.find_one({"_id": ObjectId(session["user_id"])})

        if not seva_type_details or not user:
            return jsonify({"status": "error", "message": "Invalid data. Could not complete booking."})

        # Verify signature
        key_secret = Config.RAZORPAY_KEY_SECRET
        generated_signature = hmac.new(key_secret.encode(), f"{razorpay_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
        
        if generated_signature != razorpay_signature:
            return jsonify({"status": "error", "message": "Payment verification failed."})

        # --- RACE CONDITION FIX & REFUND LOGIC ---
        # Re-check availability before inserting the booking
        is_slot_available = seva_collection.find_one({
            "seva_name": "Alankara",
            "seva_date": seva_date_obj
        })

        if is_slot_available:
            # The slot was filled. Refund the payment.
            try:
                from routes.payment import razorpay_client
                amount_to_refund = int(float(seva_type_details.get("price", 0)) * 100)
                if amount_to_refund > 0:
                    razorpay_client.payment.refund(razorpay_payment_id, {
                        "amount": amount_to_refund,
                        "speed": "normal",
                        "notes": {
                            "reason": "Booking slot filled during payment (Alankara race condition)."
                        }
                    })
                
                return jsonify({
                    "status": "error", 
                    "message": "We're sorry, but the selected date was fully booked while you were making the payment. Your payment has been automatically refunded."
                }), 409

            except Exception as e:
                print(f"CRITICAL: Refund failed for payment {razorpay_payment_id}. Error: {e}")
                return jsonify({
                    "status": "error",
                    "message": "Booking failed because the slot is full. We tried to refund your payment automatically but failed. Please contact support with your payment ID for a manual refund."
                }), 500

        # Create booking record
        booking_record = {
            "user_id": ObjectId(session["user_id"]),
            "user_name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "seva_id": ObjectId(seva_id),
            "seva_name": "Alankara",
            "seva_type": seva_type_details.get("seva_type"),
            "seva_price": float(seva_type_details.get("price")),
            "seva_date": seva_date_obj,
            "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "status": "Not Collected"
        }
        
        seva_collection.insert_one(booking_record)
        
        # Store booking in session for confirmation page
        booking_record['_id'] = str(booking_record['_id'])
        booking_record['user_id'] = str(booking_record['user_id'])
        booking_record['seva_id'] = str(booking_record['seva_id'])
        session['seva_booking'] = booking_record

        # Clear temporary session data
        session.pop("alankara_seva_id", None)
        session.pop("alankara_seva_date", None)
        session.modified = True

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
