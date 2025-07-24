import hmac
import hashlib
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from bson import ObjectId
from datetime import datetime, timedelta
from database import seva_collection, vadamala_types, user_collection
from config import Config
import razorpay
from utils import get_current_time

vadamala_bp = Blueprint('vadamala', __name__)

# Razorpay client setup
razorpay_client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

def get_available_saturdays():
    """
    Calculates the available Saturdays for the next two months, excluding days
    that are already booked to capacity (3 bookings). Also, if today is Saturday, do not allow booking for today.
    """
    today = get_current_time()
    end_date = today + timedelta(days=60)
    saturdays = []

    # Query the database to find dates that are fully booked for "Vadamala"
    pipeline = [
        {"$match": {
            "seva_name": "Vadamala",
            # Use seva_date for checking bookings, ensuring it's a datetime object for comparison
            "seva_date": {"$gte": today.replace(hour=0, minute=0, second=0, microsecond=0), "$lte": end_date}
        }},
        {"$group": {
            "_id": "$seva_date",
            "count": {"$sum": 1}
        }},
        {"$match": {
            "count": {"$gte": 3}
        }}
    ]
    
    # The pipeline returns datetime objects. We need to convert them to date strings for comparison.
    fully_booked_dates_set = {
        item['_id'].strftime("%d-%m-%Y") for item in seva_collection.aggregate(pipeline)
    }

    current_date = today
    while current_date <= end_date:
        if current_date.weekday() == 5:  # 5 represents Saturday
            # Exclude today if today is Saturday
            if not (current_date.date() == today.date() and today.weekday() == 5):
                date_str = current_date.strftime("%d-%m-%Y")
                if date_str not in fully_booked_dates_set:
                    saturdays.append(date_str)
        current_date += timedelta(days=1)
        
    return saturdays

@vadamala_bp.route('/booking')
def booking_page():
    """Renders the new Vadamala booking page for users."""
    if 'user_id' not in session:
        flash('Please login to book a seva.', 'warning')
        return redirect(url_for('user.login'))

    try:
        user_id = ObjectId(session["user_id"])
        user = user_collection.find_one({"_id": user_id})
        if not user:
            flash("User not found. Please login again.", "error")
            return redirect(url_for("user.login"))

        # Fetch the single, active Vadamala type directly
        vada_mala_seva = vadamala_types.find_one({"is_active": True})

        if not vada_mala_seva:
            flash("Vadamala seva is not available at the moment. Please check back later.", "warning")
            return redirect(url_for('general.home'))

        available_dates = get_available_saturdays()
        
        # Get current date for display on the form
        current_date_formatted = get_current_time().strftime("%Y-%m-%d")

        return render_template(
            'user/book_vadamala.html',
            user=user,
            seva=vada_mala_seva, # Pass the single object
            available_dates=available_dates,
            current_date=current_date_formatted,
            razorpay_key=Config.RAZORPAY_KEY_ID
        )
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("general.home"))

@vadamala_bp.route('/store-details', methods=['POST'])
def store_details():
    """Store selected Vadamala details in session before payment."""
    try:
        data = request.json
        session['vadamala_type_id'] = data.get('vadamala_type_id')
        session['seva_date'] = data.get('seva_date')
        session.modified = True
        return jsonify({"status": "success", "message": "Details stored successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@vadamala_bp.route('/create-order', methods=['POST'])
def create_order():
    """Create a Razorpay order using the price from the database."""
    try:
        if 'user_id' not in session:
            return jsonify({"error": "User not logged in"}), 401

        vadamala_type_id = session.get('vadamala_type_id')
        if not vadamala_type_id:
            return jsonify({"error": "Vadamala type not found in session. Please select a type."}), 400

        # --- Security: Get price from the database ---
        vadamala_type = vadamala_types.find_one({"_id": ObjectId(vadamala_type_id)})
        if not vadamala_type:
            return jsonify({"error": "Invalid Vadamala type."}), 400
        
        amount = float(vadamala_type.get("price", 0))
        if amount <= 0:
            return jsonify({"error": "Invalid price for the selected seva."}), 400

        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Amount in paise
            "currency": "INR",
            "receipt": f"vadamala_{get_current_time().timestamp()}",
            "payment_capture": 1
        })

        session['razorpay_order_id'] = order['id']
        session.modified = True
        return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@vadamala_bp.route('/verify-payment', methods=['POST'])
def verify_payment():
    """Verifies Razorpay payment and stores the booking."""
    try:
        data = request.json
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')

        # Verify signature
        generated_signature = hmac.new(
            Config.RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != razorpay_signature:
            return jsonify({"status": "error", "message": "Payment signature verification failed."}), 400

        # Retrieve data from session
        user_id = session.get('user_id')
        vadamala_type_id = session.get('vadamala_type_id')
        seva_date_str = session.get('seva_date')
        
        if not all([user_id, vadamala_type_id, seva_date_str]):
            return jsonify({"status": "error", "message": "Your session has expired. Please try again."}), 400

        # Get authoritative data from DB
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        vadamala_type = vadamala_types.find_one({"_id": ObjectId(vadamala_type_id)})

        if not user or not vadamala_type:
            return jsonify({"status": "error", "message": "Could not retrieve booking details."}), 400

        # --- Format dates as per the new requirement ---
        # seva_date: "YYYY-MM-DD"
        seva_date_obj = datetime.strptime(seva_date_str, "%d-%m-%Y")
        
        # --- RACE CONDITION FIX & REFUND LOGIC ---
        # Re-check availability atomically before inserting the booking
        booking_count = seva_collection.count_documents({
            "seva_name": "Vadamala",
            "seva_date": seva_date_obj
        })

        if booking_count >= 3:
            # The slot was filled while payment was being made. Refund the payment.
            try:
                amount_to_refund = int(float(vadamala_type.get("price", 0)) * 100)
                if amount_to_refund > 0:
                    razorpay_client.payment.refund(razorpay_payment_id, {
                        "amount": amount_to_refund,
                        "speed": "normal",
                        "notes": {
                            "reason": "Booking slot filled during payment (race condition)."
                        }
                    })
                
                # Inform user of the situation
                return jsonify({
                    "status": "error", 
                    "message": "We're sorry, but the selected date was fully booked while you were making the payment. Your payment has been automatically refunded."
                }), 409 # 409 Conflict is a good status code here

            except Exception as e:
                # Log the critical error and inform user to contact support
                print(f"CRITICAL: Refund failed for payment {razorpay_payment_id}. Error: {e}")
                return jsonify({
                    "status": "error",
                    "message": "Booking failed because slots are full. We tried to refund your payment automatically but failed. Please contact support with your payment ID for a manual refund."
                }), 500

        # booking_date: "DD-MM-YYYY (HH:MM:SS)"
        booking_timestamp = get_current_time()
        booking_date_formatted = booking_timestamp.strftime("%d-%m-%Y (%H:%M:%S)")

        # Construct final booking document
        booking = {
            "user_id": ObjectId(user_id),
            "user_name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "seva_id": vadamala_type_id,
            "seva_name": "Vadamala",
            "seva_type": vadamala_type.get("seva_type"),
            "seva_price": float(vadamala_type.get("price")),
            "booking_date": booking_date_formatted,
            "seva_date": seva_date_obj,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "status": "Not Collected",
        }
        
        result = seva_collection.insert_one(booking)
        
        # --- Store complete booking details in session for the confirmation page ---
        booking['_id'] = str(result.inserted_id)
        booking['user_id'] = str(booking['user_id'])
        booking['seva_id'] = str(booking['seva_id'])
        booking['seva_date'] = seva_date_str # Use the string version for JSON serialization

        session['seva_booking'] = booking
        # --- Remove the old order_id storage ---
        # session['latest_order_id'] = razorpay_order_id

        # Clean up session
        session.pop('vadamala_type_id', None)
        session.pop('seva_date', None)
        session.pop('razorpay_order_id', None)
        session.modified = True

        return jsonify({
            "status": "success",
            "message": "Booking confirmed!",
            "redirect_url": url_for('payment.payment_confirmation_page')
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected server error occurred: {str(e)}"}), 500

@vadamala_bp.route('/confirmation')
def confirmation_page():
    """Displays the booking confirmation page."""
    # This route is now deprecated and will be removed.
    # The new confirmation page is handled by the payment blueprint.
    flash("This page is no longer in use. Please check your dashboard for booking details.", "info")
    return redirect(url_for('user.dashboard'))

@vadamala_bp.route('/setup')
def setup_vadamala_seva():
    """
    A one-time setup route to insert a sample Vadamala seva type into the database.
    """
    try:
        # Check if the seva already exists to avoid duplicates
        if vadamala_types.count_documents({}) > 0:
            return "Vadamala seva types already exist in the database."

        vadamala_seva_doc = {
            "seva_type": "Regular Mala",
            "price": 501,
            "description": "A special seva offering of a 'Vada' (savory doughnut) garland to the deity.",
            "is_active": True
        }
        vadamala_types.insert_one(vadamala_seva_doc)
        return "Successfully inserted a sample Vadamala seva type."
    except Exception as e:
        return f"An error occurred: {e}" 