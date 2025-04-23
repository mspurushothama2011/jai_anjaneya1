from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import donations_collection, donations_list, user_collection
from bson.objectid import ObjectId
from datetime import datetime
import hashlib
import hmac
from config import Config
from routes.payment import razorpay_client
from utils import get_current_time  # Import from utils instead of app

donations_bp = Blueprint('donations', __name__)

#user donation list page

@donations_bp.route('/donation-list')
def donation_list_view():
    """Display list of donation options"""
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to make a donation", "warning")
        return redirect(url_for('user.login', next=url_for('donations.donation_list_view')))

    try:
        # Fetch all donation options from the database
        donations = list(donations_list.find())

        # Convert ObjectId to string for template
        for donation in donations:
            donation['_id'] = str(donation['_id'])

        # Get user from session
        user = None
        if "user_id" in session:
            user = user_collection.find_one({"_id": ObjectId(session["user_id"])})

        return render_template('user/user_donation.html', donations=donations, user=user)
    except Exception as e:
        flash(f"Error fetching donation options: {str(e)}", "error")
        return redirect(url_for('general.home'))

#user donation booking page

@donations_bp.route('/donation-booking/<donation_id>')
def donation_booking(donation_id):
    """Display donation booking page"""
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to make a donation", "warning")
        return redirect(url_for('user.login', next=url_for('donations.donation_booking', donation_id=donation_id)))

    try:
        # Get user from session
        user = user_collection.find_one({"_id": ObjectId(session["user_id"])})
        if not user:
            flash("User account not found", "error")
            return redirect(url_for('user.login'))

        # Fetch donation details from database
        donation = donations_list.find_one({"_id": ObjectId(donation_id)})

        if not donation:
            flash("Donation option not found", "error")
            return redirect(url_for('donations.donation_list_view'))

        return render_template('user/donation_booking.html',
                              donation=donation,
                              user=user,
                              razorpay_key_id=Config.RAZORPAY_KEY_ID)
    except Exception as e:
        flash(f"Error loading donation booking: {str(e)}", "error")
        return redirect(url_for('donations.donation_list_view'))

#store donation details in session before payment
@donations_bp.route('/store-donation-details', methods=['POST'])
def store_donation_details():
    """Store donation details in session before payment"""
    # Check if user is logged in
    if "user_id" not in session:
        return jsonify({"error": "Login required", "status": "error"}), 401

    try:
        print("Storing donation details in session...")  # Debug log
        data = request.json
        print("Received data:", data)  # Debug log

        # Get user from session
        user = user_collection.find_one({"_id": ObjectId(session["user_id"])})
        if not user:
            return jsonify({"error": "User not found", "status": "error"}), 404

        # Store essential data in session
        session["donation_id"] = data.get("donation_id")
        session["donation_name"] = data.get("donation_name")
        session["amount"] = data.get("amount")

        # Always use logged-in user details
        session["donor_name"] = user.get("name")
        session["donor_email"] = user.get("email")

        # For debugging, check what was stored
        print(f"Stored in session - ID: {session.get('donation_id')}, Name: {session.get('donation_name')}, Amount: {session.get('amount')}")
        print(f"User details - Name: {session.get('donor_name')}, Email: {session.get('donor_email')}")

        # Make sure session is saved
        session.modified = True

        return jsonify({"message": "Donation details stored successfully", "status": "success"})
    except Exception as e:
        print(f"Error storing donation details: {str(e)}")  # Debug log
        return jsonify({"error": str(e), "status": "error"}), 500

#process donation payment and create razorpay order
@donations_bp.route('/donation-payment', methods=['POST'])
def donation_payment():
    """Process donation payment and create Razorpay order"""
    # Check if user is logged in
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    try:
        # Get user from session
        user = user_collection.find_one({"_id": ObjectId(session["user_id"])})
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.json
        donation_id = data.get("donation_id")
        donation_name = data.get("donation_name")
        amount = float(data.get("amount", 0))

        # Always use logged-in user details
        donor_name = user.get("name")
        donor_email = user.get("email")

        if not amount or amount < 100:
            return jsonify({"error": "Minimum donation amount is ₹100"}), 400

        # Store payment type in session
        session["payment_type"] = "donation"
        session["amount"] = amount

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"donation_{get_current_time().strftime('%d-%m-%Y %H:%M')}",  # Short receipt
            "payment_capture": 1,
            "notes": {
                "donation_name": donation_name,
                "donation_id": donation_id,
                "donor_name": donor_name,
                "donor_email": donor_email
            }
        })

        if not order.get("id"):
            return jsonify({"error": "Failed to create order"}), 500

        # Store order ID in session
        session["order_id"] = order["id"]

        print("Razorpay Order Created:", order)  # Debug log
        return jsonify(order)

    except Exception as e:
        print("Error creating donation order:", str(e))  # Debug log
        return jsonify({"error": str(e)}), 500

#verify donation payment and store donation
@donations_bp.route('/verify-donation-payment', methods=['POST'])
def verify_donation_payment():
    """Verifies Razorpay payment and stores the donation"""
    # Check if user is logged in
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    try:
        print("\n\n*** DONATION PAYMENT VERIFICATION STARTED ***")  # Debug log
        data = request.json
        print("Request data:", data)  # Debug log

        # Get user details
        user_id = session.get("user_id")
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            print("User not found")  # Debug log
            return jsonify({"error": "User not found"}), 404

        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature")

        print(f"Payment ID: {razorpay_payment_id}")  # Debug log
        print(f"Order ID: {razorpay_order_id}")  # Debug log
        print(f"Signature: {razorpay_signature[:10]}...")  # Debug log (partial for security)

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            print("Missing verification data")  # Debug log
            return jsonify({"error": "Missing payment verification data"}), 400

        # Get session data
        donation_id = session.get("donation_id")
        donation_name = session.get("donation_name")
        amount = session.get("amount")
        donor_name = user.get("name")  # Always use user data from session
        donor_email = user.get("email")  # Always use user data from session

        print(f"Session data:")  # Debug log
        print(f"User ID: {user_id}")
        print(f"Donation ID: {donation_id}")
        print(f"Donation Name: {donation_name}")
        print(f"Amount: {amount}")

        # If session data is missing, retrieve from Razorpay
        if not all([donation_name, amount]):
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
                        donation_id = notes.get('donation_id')
                        donation_name = notes.get('donation_name')
                        # Still use user data from session for security
                        amount = float(payment.get('amount', 0)) / 100  # Convert from paise to rupees

                        print(f"Retrieved data from Razorpay:")
                        print(f"Donation ID: {donation_id}")
                        print(f"Donation Name: {donation_name}")
                        print(f"Amount: {amount}")
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

        # Create donation record for database
        donation_db = {
            "user_id": ObjectId(user_id),  # Always store authenticated user ID
            "donation_id": ObjectId(donation_id) if donation_id else None,
            "donation_name": donation_name,
            "amount": float(amount),
            "donor_name": donor_name,
            "donor_email": donor_email,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "donation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Paid"
        }

        # Create a session-safe version (without ObjectId)
        donation_session = {
            "user_id": str(user_id),
            "donation_id": str(donation_id) if donation_id else None,
            "donation_name": donation_name,
            "amount": float(amount),
            "donor_name": donor_name,
            "donor_email": donor_email,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "donation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Paid"
        }

        # Save to database
        print("Saving donation to database...")  # Debug log
        result = donations_collection.insert_one(donation_db)
        if not result.inserted_id:
            print("Failed to insert donation")  # Debug log
            return jsonify({"error": "Failed to store donation"}), 500

        print(f"Donation saved successfully with ID: {result.inserted_id}")  # Debug log

        # Store in session for confirmation page & PDF
        session["donation"] = donation_session
        print("JSON-safe donation stored in session")  # Debug log

        # Ensure session is committed
        session.modified = True
        print("Session marked as modified")  # Debug log

        # Clear temporary session data
        session.pop("donation_id", None)
        session.pop("donation_name", None)
        session.pop("amount", None)
        session.pop("donor_name", None)
        session.pop("donor_email", None)
        print("Temporary session data cleared")  # Debug log

        redirect_url = url_for("payment.donation_confirmation_page")
        print(f"Redirecting to: {redirect_url}")  # Debug log
        print("*** DONATION PAYMENT VERIFICATION COMPLETED SUCCESSFULLY ***\n\n")  # Debug log
        
        return jsonify({
            "success": True,
            "message": "Donation successful!",
            "redirect_url": redirect_url
        })
    except Exception as e:
        print(f"*** UNEXPECTED ERROR IN VERIFY DONATION PAYMENT: {str(e)} ***")  # Debug log
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        return jsonify({"error": str(e)}), 500 