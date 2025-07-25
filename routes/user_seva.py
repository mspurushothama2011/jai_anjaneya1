from flask import flash, Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import seva_list, seva_collection, user_collection
import requests
import os
from routes.payment import razorpay_client
from bson.objectid import ObjectId
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from config import Config
from utils import get_current_time  # Import from utils instead of app
from seva_config import get_all_fixed_sevas, get_seva_by_id, get_abhisheka_sevas  # Import the hard-coded sevas

user_seva_bp = Blueprint("user_seva", __name__)

# ✅ 1. Display Seva Categories Page
@user_seva_bp.route("/seva-list")
def seva_categories_view():
    """Render the main seva categories page."""
    return render_template("user/user_seva_list.html")


# ✅ New route for displaying Pooja/Vratha sevas
@user_seva_bp.route("/pooja-vratha-list")
def pooja_vratha_list():
    """Fetch and display available Pooja/Vratha sevas"""
    current_date = get_current_time().strftime("%d-%m-%Y")
    all_sevas = list(seva_list.find({"seva_name": "Pooja/Vratha"}))
    filtered_sevas = []
    for seva in all_sevas:
        seva_date_val = seva.get("seva_date", "")
        curr_date = get_current_time().date()
        seva_date = None
        # Expect string in YYYY-MM-DD, but handle legacy formats
        if isinstance(seva_date_val, str):
            try:
                seva_date = datetime.strptime(seva_date_val, "%Y-%m-%d").date()
            except Exception:
                try:
                    seva_date = datetime.fromisoformat(seva_date_val).date()
                except Exception:
                    try:
                        seva_date = datetime.strptime(seva_date_val, "%d-%m-%Y").date()
                    except Exception:
                        seva_date = None
        elif hasattr(seva_date_val, 'date'):
            seva_date = seva_date_val.date()
        if seva_date and seva_date >= curr_date:
            seva["_id"] = str(seva["_id"])
            filtered_sevas.append(seva)

    return render_template("user/pooja_vratha_list.html", 
                          sevas=filtered_sevas, 
                          current_date=current_date)


# ✅ 2. Seva Booking Page (remains the same for Pooja/Vratha)
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

        # Check if this is a hard-coded seva or database seva
        seva = None
        is_fixed_seva = False
        
        # First check if it's a hard-coded seva
        if seva_id.startswith(('abhisheka_', 'alankara_', 'vadamala_')):
            seva = get_seva_by_id(seva_id)
            is_fixed_seva = True
        
        # If not found in hard-coded sevas, check database
        if not seva:
            try:
                object_id = ObjectId(seva_id)
                seva = seva_list.find_one({"_id": object_id})
                if seva:
                    seva["_id"] = str(seva["_id"])
                    seva["id"] = seva["_id"]  # Add id field for consistency
            except:
                pass
        
        if not seva:
            flash("Seva not found.", "error")
            return redirect(url_for("user_seva.seva_categories_view"))

        # Get current date for min date in template
        current_date = get_current_time().strftime("%d-%m-%Y")
        current_date_formatted = current_date
        seva_date_formatted = ""
        if seva and seva.get("seva_date"):
            seva_date_formatted = seva.get("seva_date")

        return render_template("user/pooja_vratha_booking.html", 
            seva=seva,
            user=user,
            current_date=current_date,
            current_date_formatted=current_date_formatted,
            seva_date_formatted=seva_date_formatted,
            is_fixed_seva=is_fixed_seva
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
        
        # Get the seva date and type
        seva_date = data.get("seva_date")
        seva_type = data.get("seva_type", "General Seva")
        seva_id = data.get("seva_id")
        
        # For Pooja/Vratha sevas, use the date from the database
        if seva_type == "Pooja/Vratha" and seva_id:
            try:
                # Check if it's a database seva
                if not seva_id.startswith(('abhisheka_', 'alankara_', 'vadamala_')):
                    # Get the seva from database
                    object_id = ObjectId(seva_id)
                    seva = seva_list.find_one({"_id": object_id})
                    if seva and seva.get("seva_date"):
                        seva_date_val = seva["seva_date"]
                        if hasattr(seva_date_val, 'isoformat'):
                            seva_date = seva_date_val.isoformat()
                        else:
                            seva_date = str(seva_date_val)
            except Exception as e:
                print(f"Error getting seva date from database: {str(e)}")
                # Use the date from the request if there's an error
        
        # Store essential data in session
        session["seva_id"] = seva_id
        session["seva_name"] = data.get("seva_name")
        session["seva_price"] = data.get("amount")
        session["seva_date"] = seva_date
        session["seva_type"] = seva_type
        session["payment_type"] = "seva"
        
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
        seva_date = data.get("seva_date")
        
        # --- SECURITY FIX: Get price and details from the database ---
        seva_details = None
        if ObjectId.is_valid(seva_id):
            seva_details = seva_list.find_one({"_id": ObjectId(seva_id)})
        
        if not seva_details:
            # Check hard-coded sevas if not in DB
            seva_details = get_seva_by_id(seva_id)
            if not seva_details:
                return jsonify({"error": "Invalid Seva ID"}), 400

        amount = float(seva_details.get("amount", seva_details.get("seva_price", 0)))
        if amount <= 0:
            return jsonify({"error": "Invalid price for the selected seva."}), 400
        
        # Use authoritative data from the database/config
        seva_name = seva_details.get("seva_name")
        seva_type = seva_details.get("seva_type")

        # For Pooja/Vratha, the date is fixed and from the database
        if seva_name == "Pooja/Vratha":
            final_seva_date = seva_details.get("seva_date")
        else:
            final_seva_date = seva_date

        if not all([seva_id, seva_name, seva_type, final_seva_date]):
            return jsonify({"error": "Missing required fields"}), 400

        # Store details in session for verification after payment
        session["payment_type"] = "seva"
        session["seva_id"] = seva_id
        session["seva_name"] = seva_name
        session["seva_price"] = amount
        session["seva_date"] = final_seva_date
        session["seva_type"] = seva_type

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"seva_{get_current_time().strftime('%d-%m-%Y %H:%M')}",  # Shortened receipt
            "payment_capture": 1,
            "notes": {
                "seva_name": seva_name,
                "seva_date": final_seva_date,
                "seva_id": seva_id,
                "seva_type": seva_type
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
            flash("Payment verification failed due to missing data. Please try again.", "danger")
            return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})
            
        # Get session data immediately
        user_id = session.get("user_id")
        seva_id = session.get("seva_id")
        order_id = session.get("order_id")
        
        # Security: Verify that the Razorpay order ID from the client matches the one in the session
        if razorpay_order_id != order_id:
            print("Order ID mismatch")  # Debug log
            flash("Payment could not be verified due to a security issue (Order ID mismatch).", "danger")
            return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})

        # Verify signature
        try:
            key_secret = Config.RAZORPAY_KEY_SECRET
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                key_secret.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            if generated_signature != razorpay_signature:
                print("Signature mismatch")
                flash("Payment verification failed (Invalid Signature). If payment was debited, please contact support.", "danger")
                return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})
        except Exception as e:
            print(f"Error during signature verification: {str(e)}")
            flash("A critical error occurred during payment verification. Please contact support.", "danger")
            return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})
        
        print("Signature verified successfully")  # Debug log
        
        # Retrieve authoritative details from session
        user_id = session.get("user_id")
        seva_id = session.get("seva_id")
        seva_name = session.get("seva_name")
        seva_price = session.get("seva_price")
        seva_date = session.get("seva_date")
        seva_type = session.get("seva_type")
        
        # Debugging: Print retrieved session data
        print("Retrieved from session:")
        print(f"  User ID: {user_id}")
        print(f"  Seva ID: {seva_id}")
        print(f"  Seva Name: {seva_name}")
        print(f"  Seva Price: {seva_price}")
        print(f"  Seva Date: {seva_date}")
        print(f"  Seva Type: {seva_type}")

        if not all([user_id, seva_id, seva_name, seva_price, seva_date, seva_type]):
            print("Missing session data for booking")  # Debug log
            flash("Your session has expired. Please try booking again.", "warning")
            return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})
            
        # Check if user exists
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            print("User not found in DB")  # Debug log
            flash("Your user account could not be found. Please log in again.", "danger")
            return jsonify({"success": False, "redirect_url": url_for('user.login')})
            
        # Check for duplicate payment
        existing_booking = seva_collection.find_one({
            "order_id": razorpay_order_id,
            "status": "confirmed" # Assuming 'confirmed' means it's a successful payment
        })

        if existing_booking:
            print("Duplicate payment detected")  # Debug log
            # Redirect to a confirmation page with a message
            return jsonify({
                "success": True, 
                "redirect_url": url_for(
                    "user_seva.payment_confirmation", 
                    order_id=order_id,
                    message="This payment has already been recorded."
                )
            })

        # Create booking record
        # For Pooja/Vratha, convert seva_date from string to datetime object in UTC before storing
        if seva_name == "Pooja/Vratha":
            try:
                seva_date_obj = datetime.strptime(seva_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                seva_date_obj = seva_date
        else:
            seva_date_obj = seva_date

        booking = {
            "user_id": ObjectId(user_id),
            "user_name": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "seva_id": seva_id,
            "seva_name": seva_name,
            "seva_price": seva_price,
            "seva_date": seva_date_obj,
            "seva_type": seva_type,
            "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
            "payment_id": razorpay_payment_id,
            "order_id": order_id,
            "status": "Not Collected",
        }

        # Convert seva_id to ObjectId if it's from the database
        if ObjectId.is_valid(seva_id):
            booking["seva_id"] = ObjectId(seva_id)
        
        print("Inserting booking:", booking)  # Debug log

        # Insert booking into database
        seva_collection.insert_one(booking)
        
        print("Booking successful!")  # Debug log

        # Clear session data after successful booking
        session.pop("payment_type", None)
        session.pop("seva_id", None)
        session.pop("seva_name", None)
        session.pop("seva_price", None)
        session.pop("seva_date", None)
        session.pop("seva_type", None)
        session.pop("order_id", None)
        
        print("*** PAYMENT VERIFICATION COMPLETED ***\n\n")  # Debug log

        # Return success response with redirect URL
        return jsonify({
            "success": True,
            "redirect_url": url_for("user_seva.payment_confirmation", order_id=order_id)
        })
        
    except Exception as e:
        print(f"Error in verify_seva_payment: {str(e)}")  # Debug log
        flash("An unexpected error occurred while verifying your payment. Please contact support.", "danger")
        return jsonify({"success": False, "redirect_url": url_for('user_seva.seva_categories_view')})


# ✅ 5. Payment Confirmation Page
@user_seva_bp.route("/payment-confirmation/<order_id>")
def payment_confirmation(order_id):
    """Displays the payment confirmation page."""
    booking = seva_collection.find_one({"order_id": order_id})
    
    is_canceled = booking and booking.get("payment_id") == "canceled"

    return render_template(
        "user/payment_confirmation.html", 
        seva_booking=booking,
        is_canceled=is_canceled
    )
