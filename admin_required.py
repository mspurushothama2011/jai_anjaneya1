from flask import session, redirect, url_for, flash
from functools import wraps

def admin_required(f):
    """
    Decorator to ensure the user is logged in as an admin.
    Redirects to admin login page if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please login as admin to access this page", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function 