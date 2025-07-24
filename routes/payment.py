from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, send_file, Response
from database import client, seva_collection, donations_collection, user_collection
from datetime import datetime
from fpdf import FPDF
import razorpay
import hashlib
import hmac
import io
import os
from bson.objectid import ObjectId
from dotenv import load_dotenv
from config import Config
from utils import get_current_time  # Import from utils instead of app

# Load environment variables
load_dotenv()

payment_bp = Blueprint("payment", __name__)

# Razorpay client setup
razorpay_client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

@payment_bp.route("/process", methods=["GET"])
def process_payment():
    """
    Generic payment processing page that reads context from the session.
    """
    if 'user_id' not in session:
        flash('Please log in to proceed with the payment.', 'warning')
        return redirect(url_for('user.login'))

    payment_context = session.get('payment_context')
    if not payment_context:
        flash('No payment information found. Please start the booking process again.', 'danger')
        return redirect(url_for('general.home')) # Or a more appropriate page

    return render_template(
        'user/process_payment.html',
        payment_context=payment_context,
        razorpay_key=Config.RAZORPAY_KEY_ID
    )

@payment_bp.route("/create_generic_order", methods=["POST"])
def create_generic_order():
    """
    Creates a Razorpay order using the amount from the session's payment_context.
    """
    if 'user_id' not in session:
        return jsonify({"error": "User not logged in"}), 401

    payment_context = session.get('payment_context')
    if not payment_context or 'amount' not in payment_context:
        return jsonify({"error": "Invalid payment context"}), 400

    amount = payment_context['amount']
    description = payment_context.get('description', 'Temple Seva/Donation')

    try:
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Amount in paise
            "currency": "INR",
            "receipt": f"receipt_{get_current_time().timestamp()}",
            "notes": {
                "description": description
            }
        })
        # Store order_id to verify payment later
        session['razorpay_order_id'] = order['id']
        return jsonify(order)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@payment_bp.route("/verify_generic_payment", methods=["POST"])
def verify_generic_payment():
    """
    Verifies a Razorpay payment using the session's payment_context,
    and saves the record to the appropriate collection.
    """
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "User not logged in"}), 401

    payment_context = session.get('payment_context')
    if not payment_context:
        return jsonify({"status": "error", "message": "Invalid payment context"}), 400

    data = request.json
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    # Verify signature
    try:
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError as e:
        return jsonify({"status": "error", "message": "Payment signature verification failed"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {e}"}), 500

    # Process based on payment type from context
    payment_type = payment_context.get('type')

    if payment_type == 'seva':
        try:
            user_id = ObjectId(session['user_id'])
            user = user_collection.find_one({"_id": user_id})

            seva_booking = {
                "user_id": user_id,
                "user_name": user.get("username"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_id": payment_context.get('seva_id'),
                "seva_name": payment_context.get('seva_name'),
                "seva_price": payment_context.get('amount'),
                "booking_date": datetime.strptime(payment_context.get('booking_date'), '%Y-%m-%d'),
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id,
                "status": "Booked",
                "booked_at": get_current_time(),
                "type": "seva"
            }
            seva_collection.insert_one(seva_booking)

            # Clean up session
            session.pop('payment_context', None)
            session.pop('razorpay_order_id', None)

            return jsonify({
                "status": "success",
                "message": "Seva booked successfully!",
                "redirect_url": url_for("user_seva.history") # Redirect to history page
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to save booking: {e}"}), 500

    # Add logic for 'donation' type if needed later
    # elif payment_type == 'donation':
    #     ...

    return jsonify({"status": "error", "message": "Invalid payment type in context"}), 400


#create order

@payment_bp.route("/create-order", methods=["POST"])
def create_order():
    """Create a Razorpay order for both seva and donation payments"""
    try:
        data = request.json
        amount = data.get("amount", 0)
        currency = data.get("currency", "INR")
        payment_type = data.get("payment_type")  # "seva" or "donation"

        if not amount or amount <= 0:
            return jsonify({"error": "Invalid amount"}), 400

        if not payment_type:
            return jsonify({"error": "Payment type is required"}), 400

        # Use user's timezone from session if available
        user_timezone = session.get("user_timezone", "Asia/Kolkata")
        
        # Generate a unique receipt ID with user's local time
        current_time = get_current_time(user_timezone)
        receipt = f"{payment_type}_{current_time.strftime('%Y%m%d%H%M%S')}"

        # Create Razorpay order
        order = razorpay_client.order.create({
            "amount": int(amount * 100),  # Convert to paise
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1
        })

        # Store payment details in session
        session["payment_type"] = payment_type
        session["amount"] = amount
        session["order_id"] = order["id"]
        session["receipt"] = receipt

        return jsonify({
            "success": True,
            "order": order
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#payment page

@payment_bp.route("/payment", methods=["GET"])
def payment_page():
    """Render payment page with Razorpay UI"""
    order_id = session.get("order_id")
    payment_type = session.get("payment_type")
    
    if not order_id or not payment_type:
        flash("Invalid payment session", "error")
        return redirect(url_for("general.home"))

    return render_template("user/payment.html", 
                         order_id=order_id,
                         payment_type=payment_type)


#verify payment

@payment_bp.route("/verify-payment", methods=["POST"])
def verify_payment():
    """Verify Razorpay payment and store in appropriate collection"""
    try:
        data = request.json
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")
        
        # This is the new logic to handle direct Abhisheka bookings
        if data.get("seva_name") == "Abhisheka":
            # Verify signature first
            key_secret = Config.RAZORPAY_KEY_SECRET
            if not key_secret:
                 return jsonify({"status": "error", "message": "Payment verification configuration error"}), 500
            
            generated_signature = hmac.new(
                key_secret.encode(),
                f"{order_id}|{payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()

            if generated_signature != signature:
                return jsonify({"status": "error", "message": "Invalid signature"}), 400

            # Fetch user details from the database
            user_id = ObjectId(session.get("user_id"))
            user = user_collection.find_one({"_id": user_id})
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            # Create seva booking record directly from request data
            abhisheka_booking = {
                "user_id": user_id,
                "user_name": user.get("username"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "seva_name": data.get("seva_name"),
                "seva_type": data.get("seva_type"),
                "seva_price": float(data.get("seva_price")),
                "seva_date": data.get("seva_date"),
                "booking_date": data.get("booking_date"),
                "payment_id": payment_id,
                "order_id": order_id,
                "status": data.get("status", "Not Collected")
            }
            seva_collection.insert_one(abhisheka_booking)
            return jsonify({"status": "success"})

        # Existing logic for other payment types
        payment_type = session.get("payment_type")
        payment_status = data.get("status", "")

        if not all([order_id, payment_id, signature, payment_type]):
            return jsonify({"error": "Missing payment details"}), 400

        # Check if payment was canceled
        if payment_status == "failed" or "error" in data or "razorpay_payment_id" not in data:
            # Handle canceled or failed payment
            if payment_type == "seva":
                seva_booking = {
                    "user_id": ObjectId(session.get("user_id")),
                    "seva_id": ObjectId(session.get("seva_id")),
                    "seva_name": session.get("seva_name"),
                    "seva_type": session.get("seva_type", "General Seva"),
                    "seva_price": float(session.get("amount", 0)),
                    "amount": float(session.get("amount", 0)),
                    "seva_date": session.get("seva_date"),
                    "order_id": order_id,
                    "payment_id": payment_id or "canceled",
                    "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
                    "status": "Canceled"
                }
                # Store in session for confirmation page
                session["seva_booking"] = seva_booking
                
                # Store in database (optional)
                seva_collection.insert_one(seva_booking)
                
            elif payment_type == "donation":
                donation = {
                    "user_id": ObjectId(session.get("user_id")) if session.get("user_id") else None,
                    "amount": float(session.get("amount", 0)),
                    "donation_name": session.get("donation_name"),
                    "donor_name": session.get("donor_name"),
                    "donor_email": session.get("donor_email"),
                    "order_id": order_id,
                    "payment_id": payment_id or "canceled",
                    "donation_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
                    "status": "Canceled"
                }
                # Store in session for confirmation page
                session["donation"] = donation
                
                # Store in database (optional)
                donations_collection.insert_one(donation)
                
            return jsonify({
                "success": False,
                "message": "Payment was canceled or failed",
                "redirect_url": url_for("payment.payment_confirmation_page")
            })

        # Verify Razorpay signature for successful payments
        key_secret = Config.RAZORPAY_KEY_SECRET
        if not key_secret:
            return jsonify({"error": "Payment verification configuration error"}), 500

        try:
            generated_signature = hmac.new(
                key_secret.encode(),
                f"{order_id}|{payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()
        except Exception as e:
            return jsonify({"error": "Payment verification failed"}), 500

        if generated_signature != signature:
            return jsonify({"error": "Invalid signature"}), 400

        # Handle different payment types
        if payment_type == "seva":
            return handle_seva_payment(order_id, payment_id)
        elif payment_type == "donation":
            return handle_donation_payment(order_id, payment_id)
        else:
            return jsonify({"error": "Invalid payment type"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#handle seva payment

def handle_seva_payment(order_id, payment_id):
    """Handle seva payment verification and storage"""
    try:
        user_id = session.get("user_id")
        seva_id = session.get("seva_id")
        seva_name = session.get("seva_name")
        amount = session.get("amount")
        seva_date = session.get("seva_date")
        
        # Determine a proper seva type based on the seva name
        if not session.get("seva_type"):
            if seva_name:
                seva_name_lower = seva_name.lower()
                if "archana" in seva_name_lower:
                    seva_type = "Archana"
                elif "abhishekam" in seva_name_lower:
                    seva_type = "Abhishekam"
                elif "homam" in seva_name_lower:
                    seva_type = "Homam"
                elif "pooja" in seva_name_lower or "puja" in seva_name_lower:
                    seva_type = "Pooja"
                else:
                    seva_type = "General Seva"
            else:
                seva_type = "General Seva"
        else:
            seva_type = session.get("seva_type")

        if not all([user_id, seva_id, seva_name, amount, seva_date]):
            return jsonify({"error": "Missing seva details"}), 400

        # Create seva booking
        seva_booking = {
            "user_id": ObjectId(user_id),
            "seva_id": ObjectId(seva_id),
            "seva_name": seva_name,
            "seva_type": seva_type,
            "seva_price": float(amount),  # Store as seva_price for consistency
            "amount": float(amount),      # Keep amount for backward compatibility
            "seva_date": seva_date,
            "order_id": order_id,
            "payment_id": payment_id,
            "booking_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
            "status": "Paid"
        }

        # Store in database
        result = seva_collection.insert_one(seva_booking)
        if not result.inserted_id:
            return jsonify({"error": "Failed to store seva booking"}), 500

        # Store in session for confirmation page
        session["seva_booking"] = seva_booking

        # Clear temporary session data
        for key in ["seva_id", "seva_name", "seva_type", "amount", "seva_date", "order_id", "payment_id", "payment_type"]:
            session.pop(key, None)

        return jsonify({
            "success": True,
            "message": "Seva booking successful",
            "redirect_url": url_for("payment.payment_confirmation_page")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#handle donation payment

def handle_donation_payment(order_id, payment_id):
    """Handle donation payment verification and storage"""
    try:
        user_id = session.get("user_id")
        amount = session.get("amount")
        donation_name = session.get("donation_name")
        donor_name = session.get("donor_name")
        donor_email = session.get("donor_email")

        if not all([amount, donation_name]):
            return jsonify({"error": "Missing donation details"}), 400

        # Create donation record
        donation = {
            "user_id": ObjectId(user_id) if user_id else None,
            "amount": float(amount),
            "donation_name": donation_name,
            "donor_name": donor_name,
            "donor_email": donor_email,
            "order_id": order_id,
            "payment_id": payment_id,
            "donation_date": get_current_time().strftime("%d-%m-%Y (%H:%M:%S)"),
            "status": "Paid"
        }

        # Store in database
        result = donations_collection.insert_one(donation)
        if not result.inserted_id:
            return jsonify({"error": "Failed to store donation"}), 500

        # Store in session for confirmation page
        session["donation"] = donation

        # Clear temporary session data
        for key in ["amount", "donation_name", "donor_name", "donor_email", "order_id", "payment_id", "payment_type"]:
            session.pop(key, None)

        return jsonify({
            "success": True,
            "message": "Donation successful",
            "redirect_url": url_for("payment.donation_confirmation_page")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#payment confirmation page

@payment_bp.route("/payment-confirmation", methods=["GET"])
def payment_confirmation_page():
    """Render payment confirmation page"""
    # Get payment details from session
    print("Payment confirmation page accessed")  # Debug log
    
    seva_booking = session.get("seva_booking")
    donation = session.get("donation")
    
    print(f"Session data - Seva booking: {seva_booking is not None}, Donation: {donation is not None}")  # Debug log
    
    if seva_booking:
        print(f"Rendering confirmation with seva booking: {seva_booking.get('seva_name')}")  # Debug log
        # Check if payment was canceled
        if seva_booking.get("status") == "Canceled":
            return render_template("user/payment_confirmation.html", seva_booking=seva_booking, is_canceled=True)
        return render_template("user/payment_confirmation.html", seva_booking=seva_booking)
    elif donation:
        print(f"Rendering confirmation with donation: {donation.get('amount')}")  # Debug log
        # Check if payment was canceled
        if donation.get("status") == "Canceled":
            return render_template("user/donation_confirmation.html", donation=donation, is_canceled=True)
        return render_template("user/donation_confirmation.html", donation=donation)
    else:
        print("No payment data found in session")  # Debug log
        flash("No payment found", "error")
        return redirect(url_for("general.home"))
    

#donation confirmation page

@payment_bp.route("/donation-confirmation")
def donation_confirmation_page():
    """Renders the donation confirmation page after a successful donation."""
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to view donation confirmation", "warning")
        return redirect(url_for('user.login'))
        
    print("Donation confirmation page accessed")  # Debug log
    
    donation = session.get("donation")
    print(f"Donation data in session: {donation is not None}")  # Debug log
    
    if not donation:
        flash("Donation data not found in session", "error")
        return redirect(url_for("general.home"))
        
    user = user_collection.find_one({"_id": ObjectId(session["user_id"])})
    return render_template("user/donation_confirmation.html", donation=donation, user=user)


def generate_seva_receipt_pdf(booking_data):
    """Generates a PDF receipt for a seva booking with a specific design."""
    pdf = FPDF()
    pdf.add_page()
            
    # Helper to sanitize text
    def sanitize_for_pdf(text):
        if text is None:
            return ""
        # Replace non-Latin characters with a placeholder
        return "".join(c if ord(c) < 256 else "?" for c in str(text))

    # --- Header ---
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Sri Veeranjaneya Swamy Temple", 0, 1, "C")
    seva_name_header = sanitize_for_pdf(booking_data.get('seva_name', 'Seva'))
    pdf.cell(0, 10, f"{seva_name_header} Receipt", 0, 1, "C")
    pdf.line(pdf.get_x() + 10, pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(15)

    # --- Payment Details ---
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Payment Details", 0, 1, "L")
    pdf.set_font("helvetica", "", 12)
    
    col_width1 = 40
    line_height = 8

    pdf.cell(col_width1, line_height, "Transaction ID:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("payment_id")), border=1, ln=1)
    
    pdf.cell(col_width1, line_height, "Order ID:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("order_id")), border=1, ln=1)

    amount = f"Rs. {booking_data.get('seva_price', 0):.1f}"
    pdf.cell(col_width1, line_height, "Amount:", border=1)
    pdf.cell(0, line_height, amount, border=1, ln=1)

    pdf.cell(col_width1, line_height, "Booking Date:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("booking_date")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Status:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("status")), border=1, ln=1)
    
    pdf.ln(10)

    # --- Booking Details ---
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Booking Details", 0, 1, "L")
    pdf.set_font("helvetica", "", 12)

    pdf.cell(col_width1, line_height, "Devotee Name:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("user_name")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Booking Name:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("seva_name")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Booking Type:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("seva_type")), border=1, ln=1)
    
    pdf.cell(col_width1, line_height, "Seva Date:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("seva_date")), border=1, ln=1)
    
    pdf.ln(20)

    # --- Footer ---
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 10, "Note: For the timings of Abhisheka and Vadamala sevas, please refer to the Pooja Timings page on the temple website.", 0, 1, "C")
    pdf.ln(2)
    pdf.set_font("helvetica", "I", 12)
    pdf.cell(0, 10, "Thank you for your contribution!", 0, 1, "C")
    pdf.ln(5)
    pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin-1')
    buffer.write(pdf_output)
    buffer.seek(0)
    
    return buffer


def generate_donation_receipt_pdf(booking_data):
    """Generates a PDF receipt for a donation with a specific design."""
    pdf = FPDF()
    pdf.add_page()
            
    # Helper to sanitize text
    def sanitize_for_pdf(text):
        if text is None: return ""
        return "".join(c if ord(c) < 256 else "?" for c in str(text))

    # --- Header ---
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Sri Veeranjaneya Swamy Temple", 0, 1, "C")
    pdf.cell(0, 10, "Donation Receipt", 0, 1, "C")
    pdf.line(pdf.get_x() + 10, pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(15)

    # --- Payment Details ---
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Payment Details", 0, 1, "L")
    pdf.set_font("helvetica", "", 12)
    
    col_width1 = 40
    line_height = 8

    pdf.cell(col_width1, line_height, "Transaction ID:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("payment_id")), border=1, ln=1)
    
    pdf.cell(col_width1, line_height, "Order ID:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("order_id")), border=1, ln=1)

    amount = f"Rs. {booking_data.get('amount', 0):.1f}"
    pdf.cell(col_width1, line_height, "Amount:", border=1)
    pdf.cell(0, line_height, amount, border=1, ln=1)

    pdf.cell(col_width1, line_height, "Donation Date:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("donation_date")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Status:", border=1)
    pdf.cell(0, line_height, "Paid", border=1, ln=1)
    
    pdf.ln(10)
            
    # --- Donation Details ---
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Donation Details", 0, 1, "L")
    pdf.set_font("helvetica", "", 12)

    pdf.cell(col_width1, line_height, "Donation Name:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("donation_name")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Donor Name:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("donor_name")), border=1, ln=1)

    pdf.cell(col_width1, line_height, "Donor Email:", border=1)
    pdf.cell(0, line_height, sanitize_for_pdf(booking_data.get("donor_email")), border=1, ln=1)
    
    pdf.ln(20)

    # --- Footer ---
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 10, "Note: Donations to the temple are not eligible for 80G tax exemption.", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "I", 12)
    pdf.cell(0, 10, "Thank you for your generous donation!", 0, 1, "C")
    pdf.ln(5)
    pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin-1')
    buffer.write(pdf_output)
    buffer.seek(0)
    
    return buffer


@payment_bp.route("/download-receipt/<payment_type>/<payment_id>", methods=["GET"])
def download_receipt(payment_type, payment_id=None):
    """Generate and download a PDF receipt for a specific payment from the history page"""
    if not payment_id:
        flash("No payment ID provided for the receipt.", "error")
        return redirect(url_for("user.history"))

    if payment_type.lower() == "seva":
        booking_data = seva_collection.find_one({"payment_id": payment_id})
        if not booking_data:
            flash("Could not find a booking for the specified payment ID.", "error")
            return redirect(url_for("user.history"))

        # Use the new PDF generation function for sevas
        buffer = generate_seva_receipt_pdf(booking_data)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"receipt_{payment_id}.pdf",
            mimetype="application/pdf"
        )
    
    elif payment_type.lower() == "donation":
        booking_data = donations_collection.find_one({"payment_id": payment_id})
        if not booking_data:
            flash("Could not find a donation for the specified payment ID.", "error")
            return redirect(url_for("user.history"))

        # Use the new PDF generation function for donations
        buffer = generate_donation_receipt_pdf(booking_data)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"donation_receipt_{payment_id}.pdf",
            mimetype="application/pdf"
        )

    flash("Invalid receipt type.", "error")
    return redirect(url_for("user.history"))


# PDF receipt from confirmation page
@payment_bp.route("/confirmation-receipt/<payment_type>/<order_id>", methods=["GET"])
def confirmation_receipt(payment_type, order_id):
    """Generate and download a PDF receipt after payment confirmation"""
    if not order_id:
        flash("No booking found for this receipt.", "error")
        return redirect(url_for("general.home"))
        
    if payment_type == "seva":
        booking_data = seva_collection.find_one({"order_id": order_id})
        if not booking_data:
            flash("Could not find the specified booking.", "error")
            return redirect(url_for("general.home"))

        # Use the new PDF generation function for sevas
        buffer = generate_seva_receipt_pdf(booking_data)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"receipt_{order_id}.pdf",
            mimetype="application/pdf"
        )

    elif payment_type == "donation":
        booking_data = donations_collection.find_one({"order_id": order_id})
        if not booking_data:
            flash("Could not find the specified donation.", "error")
            return redirect(url_for("general.home"))
        
        # Use the new PDF generation function for donations
        buffer = generate_donation_receipt_pdf(booking_data)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"donation_receipt_{order_id}.pdf",
            mimetype="application/pdf"
        )
    
    flash("Invalid receipt type.", "error")
    return redirect(url_for("general.home"))


@payment_bp.route("/get-all-payments", methods=["GET"])
def get_all_payments():
    try:
        # This function is not fully implemented in the provided file,
        # so it will return a placeholder response.
        return jsonify({"message": "get_all_payments endpoint is not fully implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@payment_bp.route("/get-all-donations", methods=["GET"])
def get_all_donations():
    try:
        # This function is not fully implemented in the provided file,
        # so it will return a placeholder response.
        return jsonify({"message": "get_all_donations endpoint is not fully implemented"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

# Razorpay Webhook Handler
@payment_bp.route('/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
    import json
    from flask import request
    webhook_secret = Config.RAZORPAY_WEBHOOK_SECRET  # Set this in your .env and Razorpay dashboard
    payload = request.data
    received_signature = request.headers.get('X-Razorpay-Signature')

    # Verify webhook signature
    import hmac
    import hashlib
    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, received_signature):
        return 'Invalid signature', 400

    event = json.loads(payload)
    event_type = event.get('event')
    payload_data = event.get('payload', {})

    # Handle payment.captured event
    if event_type == 'payment.captured':
        payment_entity = payload_data.get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')
        status = payment_entity.get('status')
        amount = payment_entity.get('amount') / 100 if payment_entity.get('amount') else 0
        email = payment_entity.get('email')
        contact = payment_entity.get('contact')
        notes = payment_entity.get('notes', {})
        # Try to find the order in your DB
        # For seva
        seva = seva_collection.find_one({'order_id': order_id})
        if seva and seva.get('status') != 'Paid':
            seva_collection.update_one({'_id': seva['_id']}, {'$set': {'status': 'Paid', 'payment_id': payment_id}})
        # For donation
        donation = donations_collection.find_one({'order_id': order_id})
        if donation and donation.get('status') != 'Paid':
            donations_collection.update_one({'_id': donation['_id']}, {'$set': {'status': 'Paid', 'payment_id': payment_id}})
        # Optionally, log or notify admin
        print(f"[Webhook] Payment captured: {payment_id} for order {order_id}")
    # You can handle other event types as needed
    return 'OK', 200 