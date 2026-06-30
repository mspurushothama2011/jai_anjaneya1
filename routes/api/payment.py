from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import razorpay
import hmac
import hashlib
from bson.objectid import ObjectId
from config import Config
from database import seva_collection, donations_collection, user_collection
from utils import get_current_time

api_payment_bp = Blueprint("api_payment", __name__)

razorpay_client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

@api_payment_bp.route("/create-order", methods=["POST"])
@jwt_required()
def create_order():
    """
    Mobile API: Create a Razorpay order.
    Requires JWT token.
    """
    import time
    start_time = time.time()
    try:
        data = request.json
        amount = data.get("amount", 0)
        currency = data.get("currency", "INR")
        payment_type = data.get("payment_type")  # "seva" or "donation"

        print(f"[BACKEND_PAYMENT] Received create-order: type={payment_type}, amount={amount}")

        if not amount or float(amount) <= 0:
            return jsonify({"success": False, "message": "Invalid amount"}), 400

        if not payment_type:
            return jsonify({"success": False, "message": "Payment type is required"}), 400

        # Generate receipt ID
        current_time = get_current_time("Asia/Kolkata")
        receipt = f"{payment_type}_{current_time.strftime('%Y%m%d%H%M%S')}"

        # Create Razorpay order
        print("[BACKEND_PAYMENT] Calling Razorpay API razorpay_client.order.create...")
        rz_start = time.time()
        order = razorpay_client.order.create({
            "amount": int(float(amount) * 100),  # Convert to paise
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1
        })
        rz_elapsed = time.time() - rz_start
        print(f"[BACKEND_PAYMENT] Razorpay API responded in {rz_elapsed:.3f} seconds. Order ID: {order.get('id')}")

        total_elapsed = time.time() - start_time
        print(f"[BACKEND_PAYMENT] Total create_order route execution: {total_elapsed:.3f} seconds")

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": Config.RAZORPAY_KEY_ID
        }), 200

    except Exception as e:
        print(f"[BACKEND_PAYMENT] Error in create-order: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@api_payment_bp.route("/verify-payment", methods=["POST"])
@jwt_required()
def verify_payment():
    """
    Mobile API: Verify Razorpay payment and save to DB.
    Requires JWT token.
    """
    try:
        user_id_str = get_jwt_identity()
        user_id = ObjectId(user_id_str)
        user = user_collection.find_one({"_id": user_id})

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        data = request.json
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")
        payment_type = data.get("payment_type")  # "seva" or "donation"

        if not all([order_id, payment_id, signature, payment_type]):
            return jsonify({"success": False, "message": "Missing payment details"}), 400

        # Verify Razorpay signature
        key_secret = Config.RAZORPAY_KEY_SECRET
        if not key_secret:
            return jsonify({"success": False, "message": "Payment configuration error"}), 500

        generated_signature = hmac.new(
            key_secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != signature:
            return jsonify({"success": False, "message": "Invalid signature"}), 400

        # Check for duplicate payment
        existing_booking = None
        if payment_type == "seva":
            existing_booking = seva_collection.find_one({"payment_id": payment_id})
        elif payment_type == "donation":
            existing_booking = donations_collection.find_one({"payment_id": payment_id})

        if existing_booking:
            return jsonify({
                "success": True,
                "message": f"This {payment_type} has already been recorded."
            }), 200

        # Save to DB based on payment_type
        if payment_type == "seva":
            # Parse date string from mobile client (could be YYYY-MM-DD or DD-MM-YYYY)
            date_str = data.get("date")
            seva_date_obj = None
            from datetime import datetime, timezone
            if date_str:
                for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        seva_date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        pass
            
            if not seva_date_obj:
                current_time = get_current_time("Asia/Kolkata")
                seva_date_obj = datetime(current_time.year, current_time.month, current_time.day)

            seva_name = data.get("seva_name", "General Seva")
            seva_type = data.get("seva_type", "General Seva")
            
            # --- RACE CONDITION FIX & REFUND LOGIC ---
            if seva_name == "Vadamala":
                # Vadamala capacity limit: max 3 bookings per Saturday
                booking_count = seva_collection.count_documents({
                    "seva_name": "Vadamala",
                    "seva_date": seva_date_obj
                })
                
                if booking_count >= 3:
                    # Slot filled. Automatically refund payment.
                    try:
                        amount_to_refund = int(float(data.get("amount", 0)) * 100)
                        if amount_to_refund > 0:
                            razorpay_client.payment.refund(payment_id, {
                                "amount": amount_to_refund,
                                "speed": "normal",
                                "notes": {
                                    "reason": "Booking slot filled during payment (mobile Vadamala race condition)."
                                }
                            })
                        return jsonify({
                            "success": False,
                            "message": "We're sorry, but the selected date was fully booked while you were making the payment. Your payment has been automatically refunded."
                        }), 409
                    except Exception as refund_err:
                        print(f"CRITICAL: Refund failed for Vadamala payment {payment_id}. Error: {refund_err}")
                        return jsonify({
                            "success": False,
                            "message": "Booking failed because slots are full. Auto-refund failed. Please contact support with your payment ID."
                        }), 500

            elif seva_name == "Alankara":
                # Alankara capacity limit: max 1 booking per day
                # Check both naive and UTC-aware dates for safety
                alankara_date_obj = seva_date_obj.replace(tzinfo=timezone.utc)
                is_slot_booked = seva_collection.find_one({
                    "seva_name": "Alankara",
                    "seva_date": {"$in": [seva_date_obj, alankara_date_obj]}
                })
                
                if is_slot_booked:
                    # Slot filled. Automatically refund payment.
                    try:
                        amount_to_refund = int(float(data.get("amount", 0)) * 100)
                        if amount_to_refund > 0:
                            razorpay_client.payment.refund(payment_id, {
                                "amount": amount_to_refund,
                                "speed": "normal",
                                "notes": {
                                    "reason": "Booking slot filled during payment (mobile Alankara race condition)."
                                }
                            })
                        return jsonify({
                            "success": False,
                            "message": "We're sorry, but the selected date was fully booked while you were making the payment. Your payment has been automatically refunded."
                        }), 409
                    except Exception as refund_err:
                        print(f"CRITICAL: Refund failed for Alankara payment {payment_id}. Error: {refund_err}")
                        return jsonify({
                            "success": False,
                            "message": "Booking failed because the slot is full. Auto-refund failed. Please contact support with your payment ID."
                        }), 500

            # Determine appropriate seva_date format for DB insertion
            if seva_name == "Vadamala":
                db_seva_date = seva_date_obj
            elif seva_name in ("Alankara", "Pooja/Vratha"):
                db_seva_date = seva_date_obj.replace(tzinfo=timezone.utc)
            else:
                db_seva_date = seva_date_obj

            seva_booking = {
                "user_id": user_id,
                "user_name": user.get("username", user.get("name")),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_id": data.get("seva_id"), # Optional if needed
                "seva_name": seva_name,
                "seva_type": seva_type,
                "seva_price": float(data.get("amount", 0)),
                "amount": float(data.get("amount", 0)),
                "seva_date": db_seva_date,
                "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
                "payment_id": payment_id,
                "order_id": order_id,
                "status": "Not Collected",
                "source": "mobile_app"
            }
            seva_collection.insert_one(seva_booking)
            
        elif payment_type == "donation":
            donation = {
                "user_id": user_id,
                "amount": float(data.get("amount", 0)),
                "donation_name": data.get("donation_name", "General Donation"),
                "donor_name": user.get("username", user.get("name")),
                "donor_email": user.get("email"),
                "order_id": order_id,
                "payment_id": payment_id,
                "donation_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
                "status": "Paid",
                "source": "mobile_app"
            }
            donations_collection.insert_one(donation)
            
        else:
            return jsonify({"success": False, "message": "Invalid payment type"}), 400

        return jsonify({
            "success": True,
            "message": f"{payment_type.capitalize()} processed successfully!"
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
