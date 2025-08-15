from flask import Blueprint, render_template, request, redirect, url_for, session, make_response
from database import seva_collection, seva_list, abhisheka_types, alankara_types, vadamala_types
from datetime import datetime, timezone
from flask import flash
from bson import ObjectId
import os
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import time
from flask import current_app

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Helper to get admin credentials from config/env at runtime

def get_admin_credentials():
	username = current_app.config.get("ADMIN_USERNAME") or os.getenv("ADMIN_USERNAME")
	password = current_app.config.get("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
	return {"username": username, "password": password}

# Brute force protection settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes in seconds
LOGIN_ATTEMPTS_KEY = "admin_login_attempts"
LOCKOUT_UNTIL_KEY = "admin_lockout_until"

class AdminLoginForm(FlaskForm):
	"""Admin Login Form with CSRF protection"""
	username = StringField('Username', validators=[DataRequired()])
	password = PasswordField('Password', validators=[DataRequired()])
	submit = SubmitField('Login')

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
	"""Admin Login Page with CSRF and Brute Force Protection"""
	current_time = time.time()
	form = AdminLoginForm()
	
	# Check if account is locked out
	lockout_until = session.get(LOCKOUT_UNTIL_KEY, 0)
	if current_time < lockout_until:
		remaining_time = int(lockout_until - current_time)
		return render_template("admin/login.html", 
							 form=form,
							 message=f"Account temporarily locked. Try again in {remaining_time} seconds.",
							 locked=True), 429
	
	if form.validate_on_submit():
		# Reset lockout if time has passed
		if current_time >= lockout_until:
			session.pop(LOCKOUT_UNTIL_KEY, None)
			session.pop(LOGIN_ATTEMPTS_KEY, None)
		
		username = form.username.data
		password = form.password.data

		creds = get_admin_credentials()

		# Check credentials
		if username == creds.get("username") and password == creds.get("password"):
			# Successful login - reset attempts
			session.pop(LOGIN_ATTEMPTS_KEY, None)
			session.pop(LOCKOUT_UNTIL_KEY, None)
			session["admin"] = True
			return redirect(url_for("general_admin.admin_dashboard"))
		else:
			# Failed login - increment attempts
			attempts = session.get(LOGIN_ATTEMPTS_KEY, 0) + 1
			session[LOGIN_ATTEMPTS_KEY] = attempts
			
			if attempts >= MAX_LOGIN_ATTEMPTS:
				# Lock account
				session[LOCKOUT_UNTIL_KEY] = current_time + LOCKOUT_DURATION
				return render_template("admin/login.html", 
								 form=form,
								 message=f"Too many failed attempts. Account locked for {LOCKOUT_DURATION//60} minutes.",
								 locked=True), 429
			else:
				remaining_attempts = MAX_LOGIN_ATTEMPTS - attempts
				return render_template("admin/login.html", 
								 form=form,
								 message=f"Invalid credentials! {remaining_attempts} attempts remaining.")

	# Prevent caching of login page
	response = make_response(render_template("admin/login.html", form=form))
	response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	response.headers["Pragma"] = "no-cache"
	response.headers["Expires"] = "0"
	return response

@admin_bp.route("/logout")
def logout():
	"""Admin Logout"""
	# Clear all session data
	session.clear()

	# Prevent caching after logout
	response = make_response(redirect(url_for("admin.login")))
	response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	response.headers["Pragma"] = "no-cache"
	response.headers["Expires"] = "0"
	return response

@admin_bp.route("/dashboard")
def dashboard():
    """Admin Dashboard"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    # Redirect to the dashboard in general_admin which has all the statistics
    return redirect(url_for("general_admin.admin_dashboard"))

@admin_bp.route("/booking", methods=["GET", "POST"])
def manual_booking():
    """Admin page to manually add a seva booking (offline entry)"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    seva_names = ["Abhisheka", "Alankara", "Vadamala", "Pooja/Vratha"]
    def serialize_types(types):
        result = []
        for t in types:
            t = dict(t)
            if '_id' in t and isinstance(t['_id'], ObjectId):
                t['_id'] = str(t['_id'])
            result.append(t)
        return result
    seva_types = {
        "Abhisheka": serialize_types(abhisheka_types.find()),
        "Alankara": serialize_types(alankara_types.find()),
        "Vadamala": serialize_types(vadamala_types.find()),
        "Pooja/Vratha": serialize_types(seva_list.find({"seva_type": "Pooja/Vratha"}))
    }

    if request.method == "POST":
        user_name = request.form.get("user_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        seva_name = request.form.get("seva_name")
        seva_type_id = request.form.get("seva_type_id")
        seva_date = request.form.get("seva_date")
        # For Vadamala, Alankara, Abhisheka, and Pooja/Vratha, store seva_date as a datetime object in UTC
        if seva_name in ["Vadamala", "Alankara", "Abhisheka", "Pooja/Vratha"]:
            try:
                seva_date_obj = datetime.strptime(seva_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                seva_date_obj = seva_date  # fallback to string if parsing fails
        else:
            seva_date_obj = seva_date
        seva_price = float(request.form.get("seva_price", 0))
        selected_type = next((t for t in seva_types[seva_name] if str(t.get('_id')) == seva_type_id), None)
        seva_type = selected_type.get("seva_type") if selected_type else ""
        seva_id = str(selected_type.get("_id")) if selected_type else None
        seva_type_name = selected_type.get("seva_name") if selected_type else ""

        booking = {
            "user_id": None,
            "user_name": user_name,
            "email": email,
            "phone": phone,
            "seva_id": seva_id,
            "seva_name": seva_name,
            "seva_type": seva_type_name or seva_type,
            "seva_price": seva_price,
            "booking_date": datetime.now().strftime("%d-%m-%Y (%H:%M:%S)"),
            "seva_date": seva_date_obj,
            "payment_id": None,
            "order_id": None,
            "status": "Not Collected"
        }
        seva_collection.insert_one(booking)
        flash("Booking added successfully!", "success")
        return redirect(url_for("admin.manual_booking"))

    return render_template("admin/booking.html", seva_names=seva_names, seva_types=seva_types)
