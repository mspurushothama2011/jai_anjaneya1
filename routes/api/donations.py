"""
Mobile API – Donations
GET /api/v1/donations/   → list of all donation types from donations_list collection
"""

from flask import Blueprint, jsonify
from database import donations_list

api_donations_bp = Blueprint("api_donations", __name__)


@api_donations_bp.route("/", methods=["GET"])
def get_donations():
    """Returns all donation options from the database."""
    try:
        raw = list(donations_list.find())
        donations = []
        for d in raw:
            donations.append({
                "id": str(d["_id"]),
                "name": d.get("name", "Donation"),
                "description": d.get("description", ""),
                # Donations use user-entered amount; min is always ₹100
                "min_amount": float(d.get("min_amount", d.get("amount", 100))),
            })
        return jsonify({"success": True, "donations": donations})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
