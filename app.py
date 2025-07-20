from flask import Flask, session, request, jsonify
from flask_mail import Mail
from config import Config
from routes.user import user_bp  # Import user routes
from routes.admin import admin_bp
from routes.donations import donations_bp
from routes.donation_management import donation_management_bp
from routes.events import events_bp
from routes.general_admin import general_admin_bp
from routes.general import general_bp
from routes.payment import payment_bp
from routes.seva import sevas_bp
from routes.user_seva import user_seva_bp  # Ensure correct import
from routes.abhisheka import abhisheka_bp  # Import abhisheka routes
from routes.vadamala import vadamala_bp # Import vadamala routes
from database import client  # Ensure MongoDB is initialized
import os
import datetime
from utils import get_current_time, format_time_in_timezone  # Import both functions

app = Flask(__name__)

# ✅ Load Configurations
app.config.from_object(Config)

# Make timezone functions available to all templates
app.jinja_env.globals.update(get_current_time=get_current_time)
app.jinja_env.globals.update(format_time_in_timezone=format_time_in_timezone)

# Configure session to use filesystem
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_USE_SIGNER'] = True

# Ensure CSRF is properly configured
app.config['WTF_CSRF_ENABLED'] = False  # Disabled for Razorpay callbacks

# ✅ Initialize Flask-Mail
mail = Mail(app)

# Add route to set user timezone
@app.route('/set-timezone', methods=['POST'])
def set_timezone():
    try:
        # Get timezone from request JSON or headers
        data = request.json
        timezone = data.get('timezone') if data else None
        
        # If not in JSON, try request headers
        if not timezone:
            timezone = request.headers.get('X-User-Timezone')
            
        # Still nothing? Try cookies
        if not timezone:
            timezone = request.cookies.get('userTimezone')
            
        # Default to IST
        if not timezone:
            timezone = 'Asia/Kolkata'
            
        # Store in session
        session['user_timezone'] = timezone
        
        return jsonify({'success': True, 'timezone': timezone})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Middleware to handle timezone for each request
@app.before_request
def check_timezone():
    # Try to get timezone from request headers, fall back to session or cookie
    timezone = request.headers.get('X-User-Timezone')
    if not timezone:
        timezone = request.cookies.get('userTimezone')
    if timezone:
        session['user_timezone'] = timezone
    elif 'user_timezone' not in session:
        # Default to IST if no timezone is set
        session['user_timezone'] = 'Asia/Kolkata'

# ✅ Register Blueprints
app.register_blueprint(general_bp)
app.register_blueprint(general_admin_bp, url_prefix="/admin/general")  
app.register_blueprint(events_bp, url_prefix="/admin")
app.register_blueprint(user_seva_bp, url_prefix="/seva")
app.register_blueprint(sevas_bp, url_prefix="/sevas")
app.register_blueprint(admin_bp, url_prefix="/admin")  
app.register_blueprint(user_bp, url_prefix="/user")
app.register_blueprint(donation_management_bp, url_prefix="/donations")
app.register_blueprint(donations_bp, url_prefix="/donation")
app.register_blueprint(payment_bp, url_prefix="/payment")
app.register_blueprint(abhisheka_bp, url_prefix="/abhisheka")  # Register abhisheka blueprint
app.register_blueprint(vadamala_bp, url_prefix="/vadamala") # Register vadamala blueprint

# Register Alankara blueprint
from routes.alankara import alankara_bp
app.register_blueprint(alankara_bp, url_prefix="/alankara")

# Make sessions permanent by default and refresh on each request
@app.before_request
def make_session_permanent():
    session.permanent = True  # Use the permanent session lifetime defined above

# Register error handlers
@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404

@app.errorhandler(500)
def internal_server_error(e):
    return "Internal server error: " + str(e), 500

# ✅ Run the Application
if __name__ == "__main__":
    app.run(debug=True)
