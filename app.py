from flask import Flask, session, request, jsonify, render_template
from config import Config
from extensions import mail, csrf
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
from whitenoise import WhiteNoise

app = Flask(__name__)

# Configure WhiteNoise to serve static files in production
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

# ✅ Load Configurations
app.config.from_object(Config)

# Make timezone functions available to all templates
app.jinja_env.globals.update(get_current_time=get_current_time)
app.jinja_env.globals.update(format_time_in_timezone=format_time_in_timezone)

@app.context_processor
def inject_year():
    return {'year': datetime.datetime.now().year}

# Configure session with secure defaults
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Ensure CSRF is properly configured
app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF protection
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour token validity

# ✅ Initialize Flask-Mail and CSRF
mail.init_app(app)
csrf.init_app(app)

# ✅ Initialize JWT
from extensions import jwt, limiter
jwt.init_app(app)

# ✅ Initialize Limiter
limiter.init_app(app)

# Add route to set user timezone
@app.route('/set-timezone', methods=['POST'])
@csrf.exempt  # Exempt this route from CSRF protection as it's an API endpoint called via AJAX
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

# Middleware to handle timezone and session configuration for each request
@app.before_request
def before_request():
    # Make sessions permanent by default
    session.permanent = True
    
    # Handle timezone
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

# ✅ Register API Blueprints (For Mobile App)
from routes.api.auth import api_auth_bp
from routes.api.sevas import api_sevas_bp
from routes.api.user import api_user_bp
from routes.api.payment import api_payment_bp
from routes.api.events import api_events_bp
from routes.api.donations import api_donations_bp
from routes.api.general import api_general_bp

app.register_blueprint(api_auth_bp, url_prefix="/api/v1/auth")
app.register_blueprint(api_sevas_bp, url_prefix="/api/v1/sevas")
app.register_blueprint(api_user_bp, url_prefix="/api/v1/user")
app.register_blueprint(api_payment_bp, url_prefix="/api/v1/payment")
app.register_blueprint(api_events_bp, url_prefix="/api/v1/events")
app.register_blueprint(api_donations_bp, url_prefix="/api/v1/donations")
app.register_blueprint(api_general_bp, url_prefix="/api/v1/general")

# Exempt mobile API routes from CSRF (they use JWT instead)
csrf.exempt(api_auth_bp)
csrf.exempt(api_sevas_bp)
csrf.exempt(api_user_bp)
csrf.exempt(api_payment_bp)
csrf.exempt(api_events_bp)
csrf.exempt(api_donations_bp)
csrf.exempt(api_general_bp)

# Register error handlers
@app.errorhandler(404)
def page_not_found(e):
    return "Page not found", 404

@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401

@app.errorhandler(429)
def too_many_requests(e):
    return render_template('429.html'), 429

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# ✅ Run the Application
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
