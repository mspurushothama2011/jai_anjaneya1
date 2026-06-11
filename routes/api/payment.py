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
    try:
        data = request.json
        amount = data.get("amount", 0)
        currency = data.get("currency", "INR")
        payment_type = data.get("payment_type")  # "seva" or "donation"

        if not amount or float(amount) <= 0:
            return jsonify({"success": False, "message": "Invalid amount"}), 400

        if not payment_type:
            return jsonify({"success": False, "message": "Payment type is required"}), 400

        # Generate receipt ID
        current_time = get_current_time("Asia/Kolkata")
        receipt = f"{payment_type}_{current_time.strftime('%Y%m%d%H%M%S')}"

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(float(amount) * 100),  # Convert to paise
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1
        })

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": Config.RAZORPAY_KEY_ID
        }), 200

    except Exception as e:
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

        # Save to DB based on payment_type
        if payment_type == "seva":
            seva_booking = {
                "user_id": user_id,
                "user_name": user.get("username", user.get("name")),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_id": data.get("seva_id"), # Optional if needed
                "seva_name": data.get("seva_name", "General Seva"),
                "seva_type": data.get("seva_type", "General Seva"),
                "seva_price": float(data.get("amount", 0)),
                "amount": float(data.get("amount", 0)),
                "seva_date": data.get("date", get_current_time().strftime("%Y-%m-%d")),
                "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
                "payment_id": payment_id,
                "order_id": order_id,
                "status": "Paid",
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
