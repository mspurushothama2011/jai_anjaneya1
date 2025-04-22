from flask import Blueprint, render_template, request, redirect, url_for, session, make_response

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_CREDENTIALS = {"username": "admin", "password": "admin"}

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin Login Page"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_CREDENTIALS["username"] and password == ADMIN_CREDENTIALS["password"]:
            session["admin"] = True
            return redirect(url_for("general_admin.admin_dashboard"))
        else:
            return render_template("admin/login.html", message="Invalid credentials!")

    # Prevent caching of login page
    response = make_response(render_template("admin/login.html"))
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
