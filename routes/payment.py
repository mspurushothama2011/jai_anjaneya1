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

# Load environment variables
load_dotenv()

payment_bp = Blueprint("payment", __name__)

# Razorpay client setup
razorpay_client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

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

        # Generate a unique receipt ID
        receipt = f"{payment_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

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
        payment_type = session.get("payment_type")
        payment_status = data.get("status", "")  # Get status from Razorpay callback

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
                    "booking_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                    "donation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "booking_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "donation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    """Render the donation confirmation page"""
    try:
        print("Donation confirmation page accessed")  # Debug log
        
        # Get donation data from session
        donation = session.get("donation")
        print(f"Donation data in session: {donation is not None}")  # Debug log
        
        if not donation:
            print("No donation found in session")  # Debug log
            # Instead of redirecting, show the no donation found template
            return render_template("user/donation_confirmation.html", donation=None)

        # Check if donation object has user_id as ObjectId and convert to string if needed
        if "user_id" in donation and isinstance(donation["user_id"], ObjectId):
            donation["user_id"] = str(donation["user_id"])
            
        # Check if donation object has donation_id as ObjectId and convert to string if needed
        if "donation_id" in donation and isinstance(donation["donation_id"], ObjectId):
            donation["donation_id"] = str(donation["donation_id"])
            
        # Ensure is_canceled flag is set based on payment status
        is_canceled = donation.get("status") == "Canceled" or donation.get("payment_id") == "canceled"

        # Optional user details - don't require login
        user = None
        if "user_id" in session:
            try:
                user_id = session.get("user_id")
                user = user_collection.find_one({"_id": ObjectId(user_id)})
                print(f"User found: {user is not None}")  # Debug log
            except Exception as e:
                print(f"Error retrieving user: {str(e)}")
                # Continue without user data
        
        print(f"Rendering confirmation with donation: {donation.get('amount')}")  # Debug log
        return render_template("user/donation_confirmation.html", donation=donation, user=user, is_canceled=is_canceled)
    
    except Exception as e:
        import traceback
        print(f"Exception in donation_confirmation_page: {str(e)}")
        traceback.print_exc()
        
        # Try to get any donation data we have
        donation_data = {}
        try:
            donation_data = session.get("donation", {})
            print(f"Fallback donation data: {donation_data}")
        except:
            print("Could not retrieve session data")
            
        # Return a simple confirmation page with minimal data to avoid 500 error
        return render_template("user/donation_confirmation.html", 
                              donation=donation_data, 
                              user=None,
                              error_message="An error occurred, but your donation was processed successfully.")

@payment_bp.route("/download-receipt/<payment_type>", methods=["GET"])
@payment_bp.route("/download-receipt/<payment_type>/<payment_id>", methods=["GET"])


#generate receipt from history page

def download_receipt(payment_type, payment_id=None):
    """Generate and download receipt PDF from history page or direct URL"""
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to download your receipt", "warning")
        return redirect(url_for('user.login'))
        
    try:
        print(f"Generating {payment_type} receipt PDF for payment_id: {payment_id}")  # Debug log
        
        # Helper function to sanitize strings for PDF (latin-1 encoding)
        def sanitize_for_pdf(text):
            if not text:
                return ""
            # Convert to string if not already
            text = str(text)
            # Replace problematic characters
            text = text.replace('₹', 'Rs.')  # Replace Rupee symbol
            # Try to encode to latin-1, replacing characters that can't be encoded
            return text.encode('latin-1', 'replace').decode('latin-1')
        
        if payment_type == "seva":
            # First try to get data from session (for fresh payments)
            seva_booking = session.get("seva_booking")
            
            # If payment_id is provided or no session data, get from database
            if payment_id or not seva_booking:
                if payment_id:
                    # Convert string ID to ObjectId
                    seva_booking = seva_collection.find_one({"_id": ObjectId(payment_id)})
                    if not seva_booking:
                        flash("Seva booking not found", "error")
                        return redirect(url_for("user.history"))
                    # Convert ObjectId to string for serialization
                    seva_booking["_id"] = str(seva_booking["_id"])
                    if "user_id" in seva_booking and isinstance(seva_booking["user_id"], ObjectId):
                        seva_booking["user_id"] = str(seva_booking["user_id"])
                    if "seva_id" in seva_booking and isinstance(seva_booking["seva_id"], ObjectId):
                        seva_booking["seva_id"] = str(seva_booking["seva_id"])
                else:
                    flash("No seva booking found", "error")
                    return redirect(url_for("general.home"))
            
            # Get user information
            user_name = ""
            if "user_id" in seva_booking:
                user = user_collection.find_one({"_id": ObjectId(seva_booking["user_id"])})
                if user:
                    user_name = user.get("name", "")
            
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            
            # Set font
            pdf.set_font("Arial", "B", 16)
            
            # Title
            pdf.cell(0, 10, "Shri Veeranjaneya Swamy Temple", 0, 1, "C")
            pdf.cell(0, 10, f"{sanitize_for_pdf(seva_booking.get('seva_name', ''))} Seva Receipt", 0, 1, "C")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            # Add some space
            pdf.ln(10)
            
            # Payment details
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Payment Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Common details
            pdf.cell(70, 8, "Transaction ID:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("payment_id", "")), 1, 1)
            
            pdf.cell(70, 8, "Order ID:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("order_id", "")), 1, 1)
            
            pdf.cell(70, 8, "Amount:", 1)
            pdf.cell(0, 8, f"Rs. {seva_booking.get('seva_price', seva_booking.get('amount', 0))}", 1, 1)
            
            pdf.cell(70, 8, "Booking Date:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("booking_date", "")), 1, 1)
            
            pdf.cell(70, 8, "Status:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("status", "")), 1, 1)
            
            # Seva-specific details
            pdf.ln(10)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Seva Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Add user name
            pdf.cell(70, 8, "Devotee Name:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(user_name), 1, 1)
            
            pdf.cell(70, 8, "Seva Name:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("seva_name", "")), 1, 1)
            
            pdf.cell(70, 8, "Seva Type:", 1)
            # Extract seva type from seva_id or use a better categorization
            seva_name = seva_booking.get("seva_name", "")
            if "archana" in seva_name.lower():
                seva_type = "Archana"
            elif "abhishekam" in seva_name.lower():
                seva_type = "Abhishekam"
            elif "homam" in seva_name.lower():
                seva_type = "Homam"
            elif "pooja" in seva_name.lower() or "puja" in seva_name.lower():
                seva_type = "Pooja"
            else:
                # Use directly provided type or fall back to general category
                seva_type = seva_booking.get("seva_type", "General Seva")
            pdf.cell(0, 8, sanitize_for_pdf(seva_type), 1, 1)
            
            pdf.cell(70, 8, "Seva Date:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(seva_booking.get("seva_date", "")), 1, 1)
            
            # Footer
            pdf.ln(20)
            pdf.cell(0, 10, "Thank you for your contribution!", 0, 1, "C")
            pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
            # Generate filename
            filename = f"seva_receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Output PDF to string
            pdf_output = pdf.output(dest="S").encode("latin-1")
            
            # Return file
            response = Response(
                pdf_output,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
            
            return response
            
        elif payment_type == "donation":
            # First try to get data from session (for fresh payments)
            donation = session.get("donation")
            
            # If payment_id is provided or no session data, get from database
            if payment_id or not donation:
                if payment_id:
                    # Convert string ID to ObjectId
                    donation = donations_collection.find_one({"_id": ObjectId(payment_id)})
                    if not donation:
                        flash("Donation not found", "error")
                        return redirect(url_for("user.history"))
                    # Convert ObjectId to string for serialization
                    donation["_id"] = str(donation["_id"])
                    if "user_id" in donation and isinstance(donation["user_id"], ObjectId):
                        donation["user_id"] = str(donation["user_id"])
                else:
                    flash("No donation found", "error")
                    return redirect(url_for("general.home"))
            
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            
            # Set font
            pdf.set_font("Arial", "B", 16)
            
            # Title
            pdf.cell(0, 10, "Shri Veeranjaneya Swamy Temple", 0, 1, "C")
            pdf.cell(0, 10, "Donation Receipt", 0, 1, "C")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            # Add some space
            pdf.ln(10)
            
            # Payment details
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Payment Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Common details
            pdf.cell(70, 8, "Transaction ID:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(donation.get("payment_id", "")), 1, 1)
            
            pdf.cell(70, 8, "Order ID:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(donation.get("order_id", "")), 1, 1)
            
            pdf.cell(70, 8, "Amount:", 1)
            pdf.cell(0, 8, f"Rs. {donation.get('amount', 0)}", 1, 1)
            
            pdf.cell(70, 8, "Donation Date:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(donation.get("donation_date", "")), 1, 1)
            
            pdf.cell(70, 8, "Status:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(donation.get("status", "")), 1, 1)
            
            # Donation-specific details
            pdf.ln(10)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Donation Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            pdf.cell(70, 8, "Donation Name:", 1)
            pdf.cell(0, 8, sanitize_for_pdf(donation.get("donation_name", "")), 1, 1)
            
            pdf.cell(70, 8, "Donor Name:", 1)
            donor_name = donation.get("donor_name", "")
            if not donor_name and "user_id" in donation:
                # If donor name is not stored in donation, try to get from user collection
                user = user_collection.find_one({"_id": ObjectId(donation["user_id"])})
                if user:
                    donor_name = user.get("name", "")
            pdf.cell(0, 8, sanitize_for_pdf(donor_name), 1, 1)
            
            pdf.cell(70, 8, "Donor Email:", 1)
            donor_email = donation.get("donor_email", "")
            if not donor_email and "user_id" in donation:
                # If donor email is not stored in donation, try to get from user collection
                user = user_collection.find_one({"_id": ObjectId(donation["user_id"])})
                if user:
                    donor_email = user.get("email", "")
            pdf.cell(0, 8, sanitize_for_pdf(donor_email), 1, 1)
            
            # Footer
            pdf.ln(20)
            pdf.cell(0, 10, "Thank you for your generous donation!", 0, 1, "C")
            pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
            # Generate filename
            filename = f"donation_receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Output PDF to string
            pdf_output = pdf.output(dest="S").encode("latin-1")
            
            # Return file
            response = Response(
                pdf_output,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
            
            return response
            
        else:
            flash("Invalid payment type", "error")
            return redirect(url_for("general.home"))
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error generating receipt: {str(e)}", "error")
        if payment_type == "seva":
            return redirect(url_for("payment.payment_confirmation_page"))
        else:
            return redirect(url_for("payment.donation_confirmation_page"))
        

#generate receipt from confirmation page

@payment_bp.route("/confirmation-receipt/<payment_type>", methods=["GET"])
def confirmation_receipt(payment_type):
    """Generate and download receipt PDF from confirmation page (using session data)"""
    try:
        print(f"Generating confirmation {payment_type} receipt from session")
        
        # Get data from session
        if payment_type == "seva":
            # Seva still requires login
            if "user_id" not in session:
                flash("Please login to download your receipt", "warning")
                return redirect(url_for('user.login'))
                
            # Get seva booking data from session
            seva_booking = session.get("seva_booking")
            if not seva_booking:
                flash("Seva booking data not found in session", "error")
                return redirect(url_for("general.home"))
                
            # Get user information
            user_name = ""
            if "user_id" in seva_booking:
                user = user_collection.find_one({"_id": ObjectId(seva_booking["user_id"])})
                if user:
                    user_name = user.get("name", "")
            
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            
            # Set font
            pdf.set_font("Arial", "B", 16)
            
            # Title
            pdf.cell(0, 10, "Shri Veeranjaneya Swamy Temple", 0, 1, "C")
            pdf.cell(0, 10, f"{seva_booking.get('seva_name', '')} Seva Receipt", 0, 1, "C")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            # Add some space
            pdf.ln(10)
            
            # Payment details
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Payment Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Common details
            pdf.cell(70, 8, "Transaction ID:", 1)
            pdf.cell(0, 8, seva_booking.get("payment_id", ""), 1, 1)
            
            pdf.cell(70, 8, "Order ID:", 1)
            pdf.cell(0, 8, seva_booking.get("order_id", ""), 1, 1)
            
            pdf.cell(70, 8, "Amount:", 1)
            pdf.cell(0, 8, f"Rs. {seva_booking.get('seva_price', seva_booking.get('amount', 0))}", 1, 1)
            
            pdf.cell(70, 8, "Booking Date:", 1)
            pdf.cell(0, 8, seva_booking.get("booking_date", ""), 1, 1)
            
            pdf.cell(70, 8, "Status:", 1)
            pdf.cell(0, 8, seva_booking.get("status", ""), 1, 1)
            
            # Seva-specific details
            pdf.ln(10)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Seva Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Add user name
            pdf.cell(70, 8, "Devotee Name:", 1)
            pdf.cell(0, 8, user_name, 1, 1)
            
            pdf.cell(70, 8, "Seva Name:", 1)
            pdf.cell(0, 8, seva_booking.get("seva_name", ""), 1, 1)
            
            pdf.cell(70, 8, "Seva Type:", 1)
            # Extract seva type from seva_id or use a better categorization
            seva_name = seva_booking.get("seva_name", "")
            if "archana" in seva_name.lower():
                seva_type = "Archana"
            elif "abhishekam" in seva_name.lower():
                seva_type = "Abhishekam"
            elif "homam" in seva_name.lower():
                seva_type = "Homam"
            elif "pooja" in seva_name.lower() or "puja" in seva_name.lower():
                seva_type = "Pooja"
            else:
                # Use directly provided type or fall back to general category
                seva_type = seva_booking.get("seva_type", "General Seva")
            pdf.cell(0, 8, seva_type, 1, 1)
            
            pdf.cell(70, 8, "Seva Date:", 1)
            pdf.cell(0, 8, seva_booking.get("seva_date", ""), 1, 1)
            
            # Footer
            pdf.ln(20)
            pdf.cell(0, 10, "Thank you for your contribution!", 0, 1, "C")
            pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
            # Generate filename
            filename = f"seva_receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Output PDF to string
            pdf_output = pdf.output(dest="S").encode("latin-1")
            
            # Return file
            response = Response(
                pdf_output,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
            
            return response
            
        elif payment_type == "donation":
            # Get donation data from session - don't require login for donation receipts
            donation = session.get("donation")
            if not donation:
                flash("Donation data not found in session", "error")
                return redirect(url_for("general.home"))
                
            # Create PDF
            pdf = FPDF()
            pdf.add_page()
            
            # Set font
            pdf.set_font("Arial", "B", 16)
            
            # Title
            pdf.cell(0, 10, "Shri Veeranjaneya Swamy Temple", 0, 1, "C")
            pdf.cell(0, 10, "Donation Receipt", 0, 1, "C")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
            # Add some space
            pdf.ln(10)
            
            # Payment details
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Payment Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            
            # Common details
            pdf.cell(70, 8, "Transaction ID:", 1)
            pdf.cell(0, 8, donation.get("payment_id", ""), 1, 1)
            
            pdf.cell(70, 8, "Order ID:", 1)
            pdf.cell(0, 8, donation.get("order_id", ""), 1, 1)
            
            pdf.cell(70, 8, "Amount:", 1)
            pdf.cell(0, 8, f"Rs. {donation.get('amount', 0)}", 1, 1)
            
            pdf.cell(70, 8, "Donation Date:", 1)
            pdf.cell(0, 8, donation.get("donation_date", ""), 1, 1)
            
            pdf.cell(70, 8, "Status:", 1)
            pdf.cell(0, 8, donation.get("status", ""), 1, 1)
            
            # Donation-specific details
            pdf.ln(10)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Donation Details", 0, 1)
            
            pdf.set_font("Arial", "", 12)
            pdf.cell(70, 8, "Donation Name:", 1)
            pdf.cell(0, 8, donation.get("donation_name", ""), 1, 1)
            
            pdf.cell(70, 8, "Donor Name:", 1)
            donor_name = donation.get("donor_name", "")
            if not donor_name and "user_id" in donation and donation["user_id"]:
                # If donor name is not stored in donation, try to get from user collection
                try:
                    user = user_collection.find_one({"_id": ObjectId(donation["user_id"])})
                    if user:
                        donor_name = user.get("name", "")
                except Exception as e:
                    print(f"Error getting donor name: {str(e)}")
            pdf.cell(0, 8, donor_name, 1, 1)
            
            pdf.cell(70, 8, "Donor Email:", 1)
            donor_email = donation.get("donor_email", "")
            if not donor_email and "user_id" in donation and donation["user_id"]:
                # If donor email is not stored in donation, try to get from user collection
                try:
                    user = user_collection.find_one({"_id": ObjectId(donation["user_id"])})
                    if user:
                        donor_email = user.get("email", "")
                except Exception as e:
                    print(f"Error getting donor email: {str(e)}")
            pdf.cell(0, 8, donor_email, 1, 1)
            
            # Footer
            pdf.ln(20)
            pdf.cell(0, 10, "Thank you for your generous donation!", 0, 1, "C")
            pdf.cell(0, 10, "This is a computer-generated receipt and does not require a signature.", 0, 1, "C")
            
            # Generate filename
            filename = f"donation_receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            
            # Output PDF to string
            pdf_output = pdf.output(dest="S").encode("latin-1")
            
            # Return file
            response = Response(
                pdf_output,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
            
            return response
        else:
            flash("Invalid receipt type", "error")
            return redirect(url_for("general.home"))
            
    except Exception as e:
        import traceback
        print(f"Error generating confirmation receipt: {str(e)}")
        traceback.print_exc()
        flash("An error occurred while generating the receipt", "error")
        return redirect(url_for("general.home")) 