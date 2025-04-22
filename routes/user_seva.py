from flask import flash, Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import seva_list, seva_collection, user_collection
import requests
import os
from routes.payment import razorpay_client
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import hashlib
import hmac
from config import Config

user_seva_bp = Blueprint("user_seva", __name__)

# ✅ 1. Display Seva List (with dropdown filter)
@user_seva_bp.route("/seva-list")
def seva_list_view():
    """Fetch and display available sevas with a dropdown filter"""
    sevas = list(seva_list.find())  # Fetch all available sevas
    seva_types = {seva["seva_type"] for seva in sevas}  # Unique seva types for dropdown

    for seva in sevas:
        seva["_id"] = str(seva["_id"])  # Convert ObjectId to string for frontend

    return render_template("user/user_seva_list.html", sevas=sevas, seva_types=seva_types)

# ✅ 2. Seva Booking Page
@user_seva_bp.route("/seva-booking/<seva_id>")
def seva_booking(seva_id):
    """Seva booking page with user and seva details"""
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to book a seva", "warning")
        return redirect(url_for("user.login"))

    try:
        # Get user details
        user_id = ObjectId(session["user_id"])
        user = user_collection.find_one({"_id": user_id})
        if not user:
            flash("User not found. Please login again.", "error")
            return redirect(url_for("user.login"))

        # Get seva details
        seva = seva_list.find_one({"_id": ObjectId(seva_id)})
        if not seva:
            flash("Seva not found.", "error")
            return redirect(url_for("user_seva.seva_list_view"))

        # Get current date for min date in template
        current_date = datetime.now().strftime("%Y-%m-%d")

        return render_template(
            "user/user_seva_booking.html",
            seva=seva,
            user=user,
            current_date=current_date
        )

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("user_seva.seva_list_view"))

# Add this route before the seva_payment route

@user_seva_bp.route("/store-seva-details", methods=["POST"])
def store_seva_details():
    """Store seva details in session before payment"""
    try:
        print("Storing seva details in session...")  # Debug log
        data = request.json
        print("Received data:", data)  # Debug log
        
        # Store essential data in session
        session["seva_id"] = data.get("seva_id")
        session["seva_name"] = data.get("seva_name")
        session["seva_price"] = data.get("amount")
        session["seva_date"] = data.get("seva_date")
        
        # For debugging, check what was stored
        print(f"Stored in session - ID: {session.get('seva_id')}, Name: {session.get('seva_name')}, Price: {session.get('seva_price')}")
        
        # Make sure session is saved
        session.modified = True
        
        return jsonify({"message": "Seva details stored successfully", "status": "success"})
    except Exception as e:
        print(f"Error storing seva details: {str(e)}")  # Debug log
        return jsonify({"error": str(e), "status": "error"}), 500

# ✅ 3. Proceed to Payment (Create Razorpay Order)
@user_seva_bp.route("/seva-payment", methods=["POST"])
def seva_payment():
    """Process seva payment and create Razorpay order"""
    try:
        data = request.json
        seva_id = data.get("seva_id")
        seva_name = data.get("seva_name")
        amount = float(data.get("amount", 0))
        seva_date = data.get("seva_date")

        if not all([seva_id, seva_name, amount, seva_date]):
            return jsonify({"error": "Missing required fields"}), 400

        # Store payment type in session
        session["payment_type"] = "seva"
        session["amount"] = amount

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"seva_{datetime.now().strftime('%d-%m-%Y %H:%M')}",  # Shortened receipt
            "payment_capture": 1,
            "notes": {
                "seva_name": seva_name,
                "seva_date": seva_date,
                "seva_id": seva_id  # Added seva_id to notes instead
            }
        })

        if not order.get("id"):
            return jsonify({"error": "Failed to create order"}), 500

        # Store order ID in session
        session["order_id"] = order["id"]

        print("Razorpay Order Created:", order)  # Debug log
        return jsonify(order)

    except Exception as e:
        print("Error creating order:", str(e))  # Debug log
        return jsonify({"error": str(e)}), 500


# ✅ 4. Verify Payment & Store in `seva_collection`
@user_seva_bp.route("/verify-seva-payment", methods=["POST"])
def verify_seva_payment():
    """Verifies Razorpay payment and stores the seva booking"""
    try:
        print("\n\n*** PAYMENT VERIFICATION STARTED ***")  # Debug log
        data = request.json
        print("Request data:", data)  # Debug log
        
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature")
        
        print(f"Payment ID: {razorpay_payment_id}")  # Debug log
        print(f"Order ID: {razorpay_order_id}")  # Debug log
        print(f"Signature: {razorpay_signature[:10]}...")  # Debug log (partial for security)
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            print("Missing verification data")  # Debug log
            return jsonify({"error": "Missing payment verification data"}), 400
            
        # Get session data immediately
        user_id = session.get("user_id")
        seva_id = session.get("seva_id")
        seva_name = session.get("seva_name")
        seva_price = session.get("seva_price")
        seva_date = session.get("seva_date")
        
        print(f"Session data:")  # Debug log
        print(f"User ID: {user_id}")
        print(f"Seva ID: {seva_id}")
        print(f"Seva Name: {seva_name}")
        print(f"Seva Price: {seva_price}")
        print(f"Seva Date: {seva_date}")
        
        # If session data is missing, create a direct verification of the payment
        if not all([user_id, seva_id, seva_name, seva_price, seva_date]):
            print("Session data missing, attempting to verify payment directly with Razorpay")
            try:
                # Verify the payment directly with Razorpay API
                payment = razorpay_client.payment.fetch(razorpay_payment_id)
                if payment.get('status') == 'captured':
                    # Try to get details from the order
                    order = razorpay_client.order.fetch(razorpay_order_id)
                    notes = order.get('notes', {})
                    
                    # Extract details from order notes
                    if notes:
                        seva_id = notes.get('seva_id')
                        seva_name = notes.get('seva_name')
                        seva_date = notes.get('seva_date')
                        seva_price = float(payment.get('amount', 0)) / 100  # Convert from paise to rupees
                        
                        print(f"Retrieved data from Razorpay:")
                        print(f"Seva ID: {seva_id}")
                        print(f"Seva Name: {seva_name}")
                        print(f"Seva Price: {seva_price}")
                        print(f"Seva Date: {seva_date}")
                    else:
                        return jsonify({"error": "Payment verified but order details missing"}), 400
                else:
                    return jsonify({"error": f"Payment not captured. Status: {payment.get('status')}"}), 400
            except Exception as e:
                print(f"Razorpay direct verification error: {str(e)}")
                return jsonify({"error": f"Payment verification failed: {str(e)}"}), 500
        
        # Verify Razorpay signature
        try:
            key_secret = Config.RAZORPAY_KEY_SECRET
            if not key_secret:
                print("Razorpay key secret not found")  # Debug log
                return jsonify({"error": "Payment verification configuration error"}), 500
                
            print(f"Verifying with key: {key_secret[:3]}...")  # Debug log (partial for security)
            generated_signature = hmac.new(
                key_secret.encode(),
                f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            print(f"Generated signature: {generated_signature[:10]}...")  # Debug log
            print(f"Received signature: {razorpay_signature[:10]}...")  # Debug log
            
            if generated_signature != razorpay_signature:
                print("Signature verification failed")  # Debug log
                return jsonify({"error": "Invalid payment signature"}), 400
                
            print("Signature verified successfully")  # Debug log
        except Exception as e:
            print(f"Signature verification error: {str(e)}")  # Debug log
            return jsonify({"error": f"Payment verification failed: {str(e)}"}), 500
        
        if not user_id:
            print("User not logged in")  # Debug log
            return jsonify({"error": "User not logged in"}), 401

        # Get user details
        try:
            user = user_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                print(f"User not found for ID: {user_id}")  # Debug log
                return jsonify({"error": "User not found"}), 404
                
            print(f"User found: {user.get('name')}")  # Debug log
        except Exception as e:
            print(f"Error finding user: {str(e)}")  # Debug log
            return jsonify({"error": f"Error retrieving user data: {str(e)}"}), 500

        # Store booking in seva_collection
        try:
            # Make a JSON-serializable dictionary for the session
            seva_booking_db = {
                "user_id": ObjectId(user_id),
                "user_name": user.get("name"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_id": ObjectId(seva_id),
                "seva_name": seva_name,
                "seva_price": float(seva_price),
                "seva_date": seva_date,
                "booking_date": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id,
                "status": "Paid"
            }
            
            # Create a session-safe version (without ObjectId)
            seva_booking_session = {
                "user_id": str(user_id),
                "user_name": user.get("name"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_id": str(seva_id),
                "seva_name": seva_name,
                "seva_price": float(seva_price),
                "seva_date": seva_date,
                "booking_date": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id,
                "status": "Paid"
            }
            
            print("Saving booking to database...")  # Debug log
            result = seva_collection.insert_one(seva_booking_db)
            if not result.inserted_id:
                print("Failed to insert booking")  # Debug log
                return jsonify({"error": "Failed to store booking"}), 500
                
            print(f"Booking saved successfully with ID: {result.inserted_id}")  # Debug log
            
            # Store in session for confirmation page & PDF
            session["seva_booking"] = seva_booking_session
            print("JSON-safe booking stored in session")  # Debug log
            
        except Exception as e:
            print(f"Error saving booking: {str(e)}")  # Debug log
            return jsonify({"error": f"Failed to save booking: {str(e)}"}), 500

        # Ensure session is committed
        session.modified = True
        print("Session marked as modified")  # Debug log

        # Clear temporary session data
        session.pop("seva_id", None)
        session.pop("seva_name", None)
        session.pop("seva_price", None)
        session.pop("seva_date", None)
        print("Temporary session data cleared")  # Debug log

        redirect_url = url_for("payment.payment_confirmation_page")
        print(f"Redirecting to: {redirect_url}")  # Debug log
        print("*** PAYMENT VERIFICATION COMPLETED SUCCESSFULLY ***\n\n")  # Debug log
        
        return jsonify({
            "success": True,
            "message": "Seva booking successful!", 
            "redirect_url": redirect_url
        })
    except Exception as e:
        print(f"*** UNEXPECTED ERROR IN VERIFY PAYMENT: {str(e)} ***")  # Debug log
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        return jsonify({"error": str(e)}), 500
