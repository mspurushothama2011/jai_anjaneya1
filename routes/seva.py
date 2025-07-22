from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import seva_list
from bson.objectid import ObjectId
from admin_required import admin_required
from datetime import datetime  # Imported for date conversion

sevas_bp = Blueprint("sevas", __name__)

@sevas_bp.route("/admin/admin_seva_table")
@admin_required
def seva():
    """Fetch and display all Sevas"""
    seva_data = list(seva_list.find())  # Fetch all sevas from DB
    for seva in seva_data:
        seva["_id"] = str(seva["_id"])  # Convert ObjectId to string for HTML rendering
    return render_template("admin/admin_seva_table.html", sevas=seva_data)

@sevas_bp.route("/admin/add_seva", methods=["POST"])
@admin_required
def add_seva():
    """Add a new Pooja/Vratha seva to the database"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    try:
        # Convert the date to dd-mm-yyyy format
        date_obj = datetime.strptime(request.form["seva_date"], "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d-%m-%Y")

        # Construct new seva entry
        new_seva = {
            "seva_id": request.form["seva_id"],
            "seva_name": "Pooja/Vratha",
            "seva_type": request.form["seva_name"],
            "amount": float(request.form["amount"]),
            "description": request.form["description"],
            "seva_date": formatted_date
        }

        # Check if a seva with this ID already exists
        if seva_list.find_one({"seva_id": new_seva["seva_id"]}):
            flash(f"A seva with the ID '{new_seva['seva_id']}' already exists. Please use a different Seva ID.", "danger")
        else:
            seva_list.insert_one(new_seva)
            flash("New Pooja/Vratha seva added successfully!", "success")

    except Exception as e:
        flash(f"Error adding seva: {str(e)}", "danger")

    return redirect(url_for("general_admin.manage_sevas"))

@sevas_bp.route("/admin/delete-seva/<_id>", methods=["POST"])
@admin_required
def delete_seva(_id):
    """Delete a Pooja/Vratha seva from the database"""
    if "admin" not in session:
        return redirect(url_for("admin.login"))  # Ensure only admins can delete

    try:
        # Get the seva to verify it's a Pooja/Vratha type
        object_id = ObjectId(_id)
        seva = seva_list.find_one({"_id": object_id})
        
        if not seva:
            flash("Seva not found!", "danger")
            return redirect(url_for("general_admin.manage_sevas"))
            
        if seva.get("seva_name") != "Pooja/Vratha":
            flash("You can only delete Pooja/Vratha sevas from this interface!", "danger")
            return redirect(url_for("general_admin.manage_sevas"))
        
        # Delete the seva
        result = seva_list.delete_one({"_id": object_id})
        if result.deleted_count > 0:
            flash("Pooja/Vratha seva deleted successfully!", "success")
        else:
            flash("Failed to delete seva!", "danger")
            
    except Exception as e:
        flash(f"Error deleting seva: {str(e)}", "danger")

    return redirect(url_for("general_admin.manage_sevas"))
