from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app as app, jsonify
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import bcrypt
import secrets
from werkzeug.security import generate_password_hash
from database import user_collection, seva_collection, donations_collection
import random  
from bson.objectid import ObjectId
from utils import get_current_time
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
import time


user_bp = Blueprint("user", __name__, url_prefix="/user")

mail = Mail()
serializer = URLSafeTimedSerializer("SECRET_KEY")  # Replace with actual secret key

# Brute force protection settings for user login
USER_MAX_LOGIN_ATTEMPTS = 5
USER_LOCKOUT_DURATION = 300  # 5 minutes in seconds
USER_LOGIN_ATTEMPTS_KEY = "user_login_attempts"
USER_LOCKOUT_UNTIL_KEY = "user_lockout_until"

class UserLoginForm(FlaskForm):
    """User Login Form with CSRF protection"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# ----------------------------------
#  USER REGISTRATION (Email Verification)
# ----------------------------------

@user_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            # Get form data
            name = request.form["name"]
            email = request.form["email"]
            phone = request.form["phone"]
            dob = request.form["dob"]
            address = request.form["address"]
            password = request.form["password"]
            
            print(f"Received registration form data: {name}, {email}, {phone}")

            # Check if email or phone already exists
            if user_collection.find_one({"email": email}):
                flash("Email is already registered!", "danger")
                return redirect(url_for("user.register"))
            if user_collection.find_one({"phone": phone}):
                flash("Phone number is already registered!", "danger")
                return redirect(url_for("user.register"))

            # Hash the password using bcrypt
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            # Generate email verification token
            token = serializer.dumps(email, salt="email-confirm")

            # Save user as unverified in DB
            user_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "dob": dob,
                "address": address,
                "password": hashed_password,
                "verified": False,
                "token": token,
                "joined_on": get_current_time().strftime("%d-%m-%Y")
            }
            
            # Insert user data into database
            result = user_collection.insert_one(user_data)
            print(f"User inserted with ID: {result.inserted_id}")

            # Send verification email
            try:
                send_verification_email(email, token)
            except Exception as email_error:
                print(f"Error sending verification email: {email_error}")
                # Continue with registration even if email fails
                flash("Registration successful but there was an issue sending the verification email. Please contact support.", "warning")
                return redirect(url_for("user.login"))

            flash("Registration successful! Please check your email to verify your account.", "success")
            return redirect(url_for("user.login"))
            
        except Exception as e:
            print(f"Error during registration: {e}")
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("user.register"))

    return render_template("user/register.html")


@user_bp.route("/verify/<token>")
def verify_email(token):
    try:
        email = serializer.loads(token, salt="email-confirm", max_age=3600)
        user = user_collection.find_one({"email": email})

        if user:
            user_collection.update_one({"email": email}, {"$set": {"verified": True}, "$unset": {"token": ""}})
            flash("Email verified successfully! You can now log in.", "success")
            return redirect(url_for("user.login"))

    except:
        flash("Invalid or expired token!", "danger")

    return redirect(url_for("user.register"))

# send verification email when user registers

def send_verification_email(email, token):
    verification_link = url_for("user.verify_email", token=token, _external=True)
    subject = "Verify Your Email"

    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Email Verification</title>
        <style>
            body {{
                background-color: #f6f6f6;
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background-color: #ffffff;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background-color: #FF6B00;
                color: white;
                text-align: center;
                padding: 20px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px;
                text-align: center;
            }}
            .content p {{
                font-size: 16px;
                color: #333;
                line-height: 1.6;
            }}
            .verify-btn {{
                display: inline-block;
                padding: 12px 25px;
                margin: 25px 0;
                background-color: #FF6B00;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }}
            .footer {{
                font-size: 12px;
                color: #777;
                text-align: center;
                padding: 20px;
                background-color: #f1f1f1;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Verify Your Email</h1>
            </div>
            <div class="content">
                <p>Dear Devotee,</p>
                <p>Thank you for registering. To activate your account, please click the button below to verify your email address:</p>
                <a href="{verification_link}" class="verify-btn">Verify Email</a>
                <p>If you did not register, please ignore this email.</p>
            </div>
            <div class="footer">
                &copy; Sri Veeranjaneya Swamy<br/>
                This is an automated email, please do not reply.
            </div>
        </div>
    </body>
    </html>
    '''

    msg = Message(subject, sender=app.config["MAIL_DEFAULT_SENDER"], recipients=[email])
    msg.body = f"Click the link to verify your email: {verification_link}"  # Fallback text version
    msg.html = html_content

    try:
        mail.send(msg)
        print("Verification email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")



# ----------------------------------
#  LOGIN
# ----------------------------------

@user_bp.route("/login", methods=["GET", "POST"])
def login():
    """User Login with CSRF and Brute Force Protection"""
    current_time = time.time()
    form = UserLoginForm()
    
    # Debug: Print session info at start
    print(f"DEBUG START: Session ID: {id(session)}")
    print(f"DEBUG START: Session data: {dict(session)}")
    print(f"DEBUG START: Lockout until: {session.get(USER_LOCKOUT_UNTIL_KEY, 0)}")
    print(f"DEBUG START: Login attempts: {session.get(USER_LOGIN_ATTEMPTS_KEY, 0)}")
    
    # Check if account is locked out
    lockout_until = session.get(USER_LOCKOUT_UNTIL_KEY, 0)
    if current_time < lockout_until:
        remaining_time = int(lockout_until - current_time)
        flash(f"Account temporarily locked. Try again in {remaining_time} seconds.", "danger")
        return render_template('429.html'), 429
    
    if form.validate_on_submit():
        # Reset lockout only if it was set and has expired
        if lockout_until and current_time >= lockout_until:
            session.pop(USER_LOCKOUT_UNTIL_KEY, None)
            session.pop(USER_LOGIN_ATTEMPTS_KEY, None)
            session.modified = True
        
        email = form.email.data
        password = form.password.data

        # Fetch user from MongoDB
        user = user_collection.find_one({"email": email})

        if user:
            hashed_password = user.get("password")
            verified = user.get("verified", False)

            if not hashed_password:
                # Increment attempts for invalid password storage
                attempts = session.get(USER_LOGIN_ATTEMPTS_KEY, 0) + 1
                session[USER_LOGIN_ATTEMPTS_KEY] = attempts
                session.modified = True
                
                if attempts >= USER_MAX_LOGIN_ATTEMPTS:
                    session[USER_LOCKOUT_UNTIL_KEY] = current_time + USER_LOCKOUT_DURATION
                    session.modified = True
                    flash(f"Too many failed attempts. Account locked for {USER_LOCKOUT_DURATION//60} minutes.", "danger")
                    return render_template("user/login.html", form=form, locked=True), 429
                else:
                    remaining_attempts = USER_MAX_LOGIN_ATTEMPTS - attempts
                    flash(f"Invalid password stored! {remaining_attempts} attempts remaining.", "danger")
                return render_template("user/login.html", form=form)

            if not verified:
                # Increment attempts for unverified account
                attempts = session.get(USER_LOGIN_ATTEMPTS_KEY, 0) + 1
                session[USER_LOGIN_ATTEMPTS_KEY] = attempts
                session.modified = True
                
                if attempts >= USER_MAX_LOGIN_ATTEMPTS:
                    session[USER_LOCKOUT_UNTIL_KEY] = current_time + USER_LOCKOUT_DURATION
                    session.modified = True
                    flash(f"Too many failed attempts. Account locked for {USER_LOCKOUT_DURATION//60} minutes.", "danger")
                    return render_template("user/login.html", form=form, locked=True), 429
                else:
                    remaining_attempts = USER_MAX_LOGIN_ATTEMPTS - attempts
                    flash(f"Please verify your email before logging in. {remaining_attempts} attempts remaining.", "warning")
                return render_template("user/login.html", form=form)

            # Validate hashed password using bcrypt
            if bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8")):
                # Successful login - reset attempts
                session.pop(USER_LOGIN_ATTEMPTS_KEY, None)
                session.pop(USER_LOCKOUT_UNTIL_KEY, None)
                session["user_id"] = str(user["_id"])  # Store user ID in session
                flash("Login successful!", "success")
                return redirect(url_for("general.home"))
            else:
                # Failed login - increment attempts
                attempts = int(session.get(USER_LOGIN_ATTEMPTS_KEY, 0)) + 1
                session[USER_LOGIN_ATTEMPTS_KEY] = attempts
                session.modified = True
                
                if attempts >= USER_MAX_LOGIN_ATTEMPTS:
                    # Lock account
                    session[USER_LOCKOUT_UNTIL_KEY] = current_time + USER_LOCKOUT_DURATION
                    flash(f"Too many failed attempts. Account locked for {USER_LOCKOUT_DURATION//60} minutes.", "danger")
                    return render_template('429.html'), 429
                else:
                    remaining_attempts = USER_MAX_LOGIN_ATTEMPTS - attempts
                    flash(f"Incorrect password! {remaining_attempts} attempts remaining.", "danger")
        else:
            # Email not found - increment attempts
            attempts = int(session.get(USER_LOGIN_ATTEMPTS_KEY, 0)) + 1
            session[USER_LOGIN_ATTEMPTS_KEY] = attempts
            
            # Mark session as modified to ensure it's saved
            session.modified = True
            
            # Debug logging
            print(f"DEBUG: Session ID: {id(session)}")
            print(f"DEBUG: Current attempts: {attempts}")
            print(f"DEBUG: Session data: {dict(session)}")
            print(f"DEBUG: Session modified: {session.modified}")
            
            if attempts >= USER_MAX_LOGIN_ATTEMPTS:
                # Lock account
                session[USER_LOCKOUT_UNTIL_KEY] = current_time + USER_LOCKOUT_DURATION
                session.modified = True  # Mark as modified again
                flash(f"Too many failed attempts. Account locked for {USER_LOCKOUT_DURATION//60} minutes.", "danger")
                return render_template("user/login.html", form=form, locked=True), 429
            else:
                remaining_attempts = USER_MAX_LOGIN_ATTEMPTS - attempts
                flash(f"Email not found! {remaining_attempts} attempts remaining.", "danger")

    # Debug: Print session info at end
    print(f"DEBUG END: Session ID: {id(session)}")
    print(f"DEBUG END: Session data: {dict(session)}")
    print(f"DEBUG END: Lockout until: {session.get(USER_LOCKOUT_UNTIL_KEY, 0)}")
    print(f"DEBUG END: Login attempts: {session.get(USER_LOGIN_ATTEMPTS_KEY, 0)}")
    
    return render_template("user/login.html", form=form)


@user_bp.route("/logout")
def logout():
    # Clear all session data
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("user.login"))


# ----------------------------------
#  FORGOT PASSWORD (OTP-Based)
# ----------------------------------

@user_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        user = user_collection.find_one({"email": email})

        if user:
            # Generate a 6-digit numeric OTP instead of hex
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user_collection.update_one({"email": email}, {"$set": {"reset_otp": otp}})
            send_otp_email(email, otp)

            session["email"] = email
            flash("An OTP has been sent to your email.", "info")
            return redirect(url_for("user.verify_otp"))

        flash("Email not found!", "danger")

    return render_template("user/forgot_password.html")


def send_otp_email(email, otp):
    subject = "Your Password Reset OTP"
    
    # Format the OTP with spaces for better readability
    formatted_otp = ' '.join(otp)
    
    # HTML email template
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset OTP</title>
        <style>
            body {{
                font-family: 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background-color: #FF6B00;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px;
                text-align: center;
            }}
            .otp-box {{
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                font-size: 32px;
                letter-spacing: 6px;
                font-weight: bold;
                color: #333;
                border: 1px dashed #ccc;
                display: inline-block;
            }}
            .note {{
                font-size: 14px;
                color: #777;
                margin-top: 20px;
            }}
            .footer {{
                background-color: #f5f5f5;
                padding: 15px;
                text-align: center;
                font-size: 12px;
                color: #999;
            }}
            @media only screen and (max-width: 600px) {{
                .container {{
                    margin: 0;
                    border-radius: 0;
                }}
                .otp-box {{
                    font-size: 24px;
                    letter-spacing: 4px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Temple Password Reset</h1>
            </div>
            <div class="content">
                <p>Dear Devotee,</p>
                <p>We received a request to reset your password. Please use the verification code below to complete your password reset:</p>
                
                <div class="otp-box">{otp}</div>
                
                <p>This code is valid for 10 minutes only.</p>
                
                <p class="note">If you didn't request this password reset, please ignore this email or contact support if you have concerns.</p>
            </div>
            <div class="footer">
                <p>This is an automated message, please do not reply to this email.</p>
                <p>&copy; Sri Veeranjaneya Swamy</p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    # Plain text version for email clients that don't support HTML
    text_content = f"Your OTP for password reset is: {otp}. It expires in 10 minutes."

    msg = Message(subject, sender=app.config["MAIL_DEFAULT_SENDER"], recipients=[email])
    msg.body = text_content
    msg.html = html_content

    try:
        mail.send(msg)
        print("OTP email sent successfully!")
    except Exception as e:
        print(f"Error sending OTP email: {e}")


# ----------------------------------
#  VERIFY OTP
# ----------------------------------

@user_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        otp = request.form.get("otp").strip()
        email = session.get("email")

        if not email:
            flash("Session expired. Please try again.", "danger")
            return redirect(url_for("user.forgot_password"))

        user = user_collection.find_one({"email": email})

        if not user:
            flash("User not found!", "danger")
            return redirect(url_for("user.forgot_password"))

        stored_otp = str(user.get("reset_otp", "")).strip()

        if otp != stored_otp:
            flash("Invalid OTP. Please try again.", "danger")
            return redirect(url_for("user.verify_otp"))

        flash("OTP verified successfully. Set your new password.", "success")
        return redirect(url_for("user.reset_password"))

    return render_template("user/verify_otp.html")


@user_bp.route("/resend_otp")
def resend_otp():
    email = session.get("email")
    
    if not email:
        flash("Session expired. Please try again.", "danger")
        return redirect(url_for("user.forgot_password"))
    
    user = user_collection.find_one({"email": email})
    
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("user.forgot_password"))
    
    # Generate a new 6-digit numeric OTP
    otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    user_collection.update_one({"email": email}, {"$set": {"reset_otp": otp}})
    
    # Send the new OTP
    send_otp_email(email, otp)
    
    flash("A new OTP has been sent to your email.", "info")
    return redirect(url_for("user.verify_otp"))


# ----------------------------------
#  RESET PASSWORD
# ----------------------------------

@user_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        new_password = request.form.get("password").strip()
        confirm_password = request.form.get("confirm_password").strip()

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("user.reset_password"))

        email = session.get("email")
        if not email:
            flash("Session expired. Try again.", "danger")
            return redirect(url_for("user.forgot_password"))

        # Hash new password using bcrypt
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password in MongoDB
        user_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})

        # Clear session email after reset
        session.pop("email", None)

        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("user.login"))

    return render_template("user/reset_password.html")



@user_bp.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("user.login"))
    
    # Fetch user data from database
    user_id = session.get("user_id")
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        flash("User not found", "error")
        return redirect(url_for("user.login"))
    
    return render_template("user/profile.html", user=user)


@user_bp.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        flash("Please login to access this page.", "warning")
        return redirect(url_for("user.login"))
    
    # Get form data
    name = request.form.get("name")
    dob = request.form.get("dob")
    phone = request.form.get("phone")
    address = request.form.get("address")
    
    # Basic validation
    if not name or not dob or not phone or not address:
        flash("All fields are required", "danger")
        return redirect(url_for("user.profile"))
    
    # Update user data
    user_collection.update_one(
        {"_id": ObjectId(session["user_id"])},
        {"$set": {
            "name": name,
            "dob": dob,
            "phone": phone,
            "address": address
        }}
    )
    
    flash("Profile updated successfully", "success")
    return redirect(url_for("user.profile"))


@user_bp.route("/send-email-verification", methods=["POST"])
def send_email_verification():
    if "user_id" not in session:
        return redirect(url_for("user.login"))
    
    user_id = session.get("user_id")
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        flash("User not found", "error")
        return redirect(url_for("user.login"))
    
    # Get new email from form
    new_email = request.form.get("new_email")
    
    if not new_email:
        flash("New email is required", "error")
        return redirect(url_for("user.profile", tab="email-settings"))
    
    # Check if email is already in use
    existing_user = user_collection.find_one({"email": new_email})
    if existing_user and str(existing_user["_id"]) != user_id:
        flash("Email is already in use by another account", "error")
        return redirect(url_for("user.profile", tab="email-settings"))
    
    # Generate OTP for email verification
    email_otp = secrets.token_hex(3)
    
    # Store OTP and new email in database
    user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "email_change_otp": email_otp,
            "new_email": new_email
        }}
    )
    
    # Send OTP to the new email
    send_email_change_otp(new_email, email_otp)
    
    # Set session flag for OTP sent
    session["otp_sent"] = True
    
    flash(f"An OTP has been sent to {new_email}. Please verify to complete the email change.", "info")
    return redirect(url_for("user.profile", tab="email-settings"))


def send_email_change_otp(email, otp):
    subject = "Email Change Verification"
    message_body = f"Your OTP for email change verification is: {otp}. It expires in 10 minutes."

    msg = Message(subject, sender=app.config["MAIL_DEFAULT_SENDER"], recipients=[email])
    msg.body = message_body

    try:
        mail.send(msg)
        print("Email change OTP sent successfully!")
    except Exception as e:
        print(f"Error sending email change OTP: {e}")


@user_bp.route("/verify-email-change", methods=["POST"])
def verify_email_change():
    if "user_id" not in session:
        return redirect(url_for("user.login"))
    
    user_id = session.get("user_id")
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        flash("User not found", "error")
        return redirect(url_for("user.login"))
    
    # Get OTP from form
    email_otp = request.form.get("email_otp")
    
    if not email_otp:
        flash("OTP is required", "error")
        return redirect(url_for("user.profile", tab="email-settings"))
    
    # Check if OTP matches
    stored_otp = user.get("email_change_otp")
    new_email = user.get("new_email")
    
    if not stored_otp or not new_email:
        flash("No email change request found", "error")
        return redirect(url_for("user.profile", tab="email-settings"))
    
    if email_otp != stored_otp:
        flash("Invalid OTP", "error")
        return redirect(url_for("user.profile", tab="email-settings"))
    
    # Update email
    user_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"email": new_email},
         "$unset": {"email_change_otp": "", "new_email": ""}}
    )
    
    # Clear session flag
    session.pop("otp_sent", None)
    
    flash("Email changed successfully", "success")
    return redirect(url_for("user.profile", tab="email-settings"))


@user_bp.route("/history", methods=["GET"])
def history():
    """Display user's seva and donation history with dynamic filters."""
    if "user_id" not in session:
        flash("Please log in to view your history.", "warning")
        return redirect(url_for("user.login"))

    user_id = ObjectId(session["user_id"])
    
    def safe_date_parser(date_val):
        """Safely parse date, handling both datetime objects and strings."""
        if isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, str):
            try:
                # First, try to parse the format with time
                return datetime.strptime(date_val, "%d-%m-%Y (%H:%M:%S)")
            except ValueError:
                try:
                    # Fallback to parsing just the date
                    return datetime.strptime(date_val, "%d-%m-%Y")
                except ValueError:
                    return None  # Return None if parsing fails
        return None

    # Get user's seva bookings and donations
    seva_bookings = list(seva_collection.find({"user_id": user_id}))
    donations = list(donations_collection.find({"user_id": user_id}))

    # Combine and prepare for sorting
    all_history = []
    for booking in seva_bookings:
        booking["type"] = booking.get("seva_name", "Seva") 
        booking["sort_date"] = safe_date_parser(booking.get("booking_date"))
        all_history.append(booking)
        
    for donation in donations:
        donation["type"] = "Donation"
        donation["sort_date"] = safe_date_parser(donation.get("donation_date"))
        all_history.append(donation)

    # Filter out items with no valid date and sort
    all_history = [item for item in all_history if item["sort_date"]]
    all_history.sort(key=lambda x: x["sort_date"], reverse=True)
    
    # Define a static list of seva names for the filter buttons
    seva_filters = ["Vadamala", "Abhisheka", "Alankara", "Pooja/Vratha"]
    
    return render_template("user/history.html", history=all_history, seva_filters=seva_filters)


@user_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("user.login"))
    
    # Fetch user data from database
    user_id = session.get("user_id")
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        flash("User not found", "error")
        return redirect(url_for("user.login"))
    
    # Fetch user stats
    total_sevas = seva_collection.count_documents({"user_id": ObjectId(user_id)})
    total_donations = donations_collection.count_documents({"user_id": ObjectId(user_id)})
    
    # Calculate total amount contributed
    donation_pipeline = [
        {"$match": {"user_id": ObjectId(user_id)}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    amount_result = list(donations_collection.aggregate(donation_pipeline))
    amount_contributed = amount_result[0]["total"] if amount_result else 0
    
    # Get upcoming sevas (future dates)
    today = get_current_time()
    upcoming_sevas = seva_collection.count_documents({
        "user_id": ObjectId(user_id),
        "seva_date": {"$gt": today.strftime("%d-%m-%Y")}
    })
    
    # Compile user stats
    user_stats = {
        "total_sevas": total_sevas,
        "total_donations": total_donations,
        "amount_contributed": amount_contributed,
        "upcoming_sevas": upcoming_sevas
    }
    
    # Get recent activities (limit to 5)
    recent_sevas = list(seva_collection.find(
        {"user_id": ObjectId(user_id)}
    ).sort("booking_date", -1).limit(3))
    
    recent_donations = list(donations_collection.find(
        {"user_id": ObjectId(user_id)}
    ).sort("donation_date", -1).limit(3))
    
    # Combine and sort recent activities
    recent_activities = []

    def safe_date_parser_dashboard(date_val):
        from datetime import datetime
        if isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, str):
            for fmt in ["%d-%m-%Y (%H:%M:%S)", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(date_val, fmt)
                except Exception:
                    continue
        return datetime(1900, 1, 1)  # fallback for invalid/missing dates

    for seva in recent_sevas:
        recent_activities.append({
            "date": safe_date_parser_dashboard(seva.get("booking_date")),
            "type": "Seva",
            "description": seva.get("seva_name", "Unknown Seva"),
            "amount": seva.get("amount", 0)
        })

    for donation in recent_donations:
        recent_activities.append({
            "date": safe_date_parser_dashboard(donation.get("donation_date")),
            "type": "Donation",
            "description": donation.get("donation_purpose", "General Donation"),
            "amount": donation.get("amount", 0)
        })

    # Sort by date descending and limit to 5
    recent_activities.sort(key=lambda x: x["date"], reverse=True)
    recent_activities = recent_activities[:5]
    
    return render_template("user/dashboard.html", user=user, user_stats=user_stats, recent_activities=recent_activities)
