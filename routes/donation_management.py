from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import donations_list
from bson.objectid import ObjectId
from functools import wraps

donation_management_bp = Blueprint("donation_management", __name__, url_prefix="/admin/donations")

#admin required to use admin side pages

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please login as admin to access this page.", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function


#admin manage donations page

@donation_management_bp.route("/", methods=["GET", "POST"])
@admin_required
def manage_donations():
    """Admin page to manage donations"""
    if request.method == "POST":
        donation_id = request.form.get("id")
        donation_name = request.form.get("name")
        donation_description = request.form.get("description")

        if not donation_name or not donation_description:
            flash("Please fill out all fields.", "error")
            return redirect(url_for("donation_management.manage_donations"))

        donation_data = {
            "name": donation_name,
            "id": donation_id,
            "description": donation_description
        }
        result = donations_list.insert_one(donation_data)
        print("Inserted Donation ID:", result.inserted_id)  # Debugging

        
        return redirect(url_for("donation_management.manage_donations"))

    # ✅ Fetch donations and print them for debugging
    donations = list(donations_list.find())
    print("Fetched Donations:", donations)  # Debugging

    return render_template("admin/admin_donation_list.html", donations=donations)


#admin delete donations page

@donation_management_bp.route("/delete/<donation_id>", methods=["POST"])
@admin_required
def delete_donation(donation_id):
    """Delete a donation"""
    try:
        donations_list.delete_one({"_id": ObjectId(donation_id)})
        flash("Donation deleted successfully!", "success")
    except:
        flash("Failed to delete donation. Please try again.", "error")

    return redirect(url_for("donation_management.manage_donations"))  # ✅ Correct redirect
