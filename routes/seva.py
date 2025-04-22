from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import seva_list
from bson.objectid import ObjectId  # Import ObjectId
from admin_required import admin_required

sevas_bp = Blueprint("sevas", __name__)


@sevas_bp.route("/admin/admin_seva_table")
@admin_required
def seva():
    """Fetch and display all Sevas"""
    seva_data = list(seva_list.find())  # Fetch all sevas from DB
    for seva in seva_data:
        seva["_id"] = str(seva["_id"])  # Convert ObjectId to string for HTML rendering

    return render_template("admin/admin_seva_table.html", sevas=seva_data)  # Correct template path


@sevas_bp.route("/admin/add_seva", methods=["POST"])
@admin_required
def add_seva():
    """Add a new seva to the database"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))  # Ensure only admins can add events

    new_seva = {
        "seva_id": request.form["seva_id"],
        "seva_type": request.form["seva_type"],
        "seva_name": request.form["seva_name"],
        "seva_price": request.form["seva_price"],
        "seva_description": request.form["seva_description"],
    }
    seva_list.insert_one(new_seva)  # Insert new seva into database

    return redirect(url_for("sevas.seva"))  # Redirect back to admin_seva_table



@sevas_bp.route("/admin/delete-seva/<_id>", methods=["POST"])
@admin_required
def delete_seva(_id):
    """Delete a seva from the database"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))  # Ensure only admins can delete

    try:
        object_id = ObjectId(_id)  # Convert _id to ObjectId
        result = seva_list.delete_one({"_id": object_id})  # Delete seva
        print(f"Delete result: {result.deleted_count}")  # Debug output
    except Exception as e:
        print(f"Error deleting seva: {e}")  # Print error details

    return redirect(url_for("sevas.seva"))  # Redirect back to admin_seva_table
