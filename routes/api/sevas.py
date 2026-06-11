"""
Mobile API – Sevas
GET /api/v1/sevas/          → all seva categories with their types from DB
GET /api/v1/sevas/abhisheka → active abhisheka types
GET /api/v1/sevas/alankara  → active alankara types
GET /api/v1/sevas/vadamala  → active vadamala types
GET /api/v1/sevas/pooja     → upcoming pooja/vratha sevas from seva_list
"""

from flask import Blueprint, jsonify
from database import abhisheka_types, alankara_types, vadamala_types, seva_list, seva_collection
from datetime import datetime, timedelta, date
from utils import get_current_time

api_sevas_bp = Blueprint("api_sevas", __name__)


def _fmt_type(doc, category_name, category_id):
    """Convert a seva-type DB document to a clean JSON-safe dict."""
    return {
        "id": str(doc["_id"]),
        "category_id": category_id,
        "category_name": category_name,
        "name": doc.get("seva_type", "Seva"),
        "price": float(doc.get("price", 0)),
        "description": doc.get("description", ""),
        "is_active": doc.get("is_active", True),
    }


def to_naive(dt):
    """Remove timezone info from datetime."""
    if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


# ── All categories summary ────────────────────────────────────────────────────
@api_sevas_bp.route("/", methods=["GET"])
def get_all_sevas():
    """Returns all seva categories with their items fetched from the DB."""
    try:
        abhisheka = [_fmt_type(d, "Abhisheka", "abhisheka")
                     for d in abhisheka_types.find({"is_active": True})]
        alankara  = [_fmt_type(d, "Alankara",  "alankara")
                     for d in alankara_types.find({"is_active": True})]
        vadamala  = [_fmt_type(d, "Vadamala",  "vadamala")
                     for d in vadamala_types.find({"is_active": True})]

        # Pooja/Vratha – only future dated sevas
        today = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
        today = to_naive(today)
        pooja_raw = list(seva_list.find({"seva_name": "Pooja/Vratha"}))
        pooja = []
        for d in pooja_raw:
            raw_date = d.get("seva_date", "")
            seva_date = None
            if isinstance(raw_date, datetime):
                seva_date = raw_date
            elif isinstance(raw_date, str):
                for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        seva_date = datetime.strptime(raw_date, fmt)
                        break
                    except ValueError:
                        pass
            
            if seva_date:
                seva_date = to_naive(seva_date)
                if seva_date >= today:
                    pooja.append({
                    "id": str(d["_id"]),
                    "category_id": "pooja_vratha",
                    "category_name": "Pooja & Vratha",
                    "name": d.get("seva_sub_name", d.get("seva_title", "Pooja")),
                    "price": float(d.get("seva_price", d.get("price", 0))),
                    "description": d.get("seva_description", d.get("description", "")),
                    "date_display": seva_date.strftime("%d %b %Y"),
                    "is_active": True,
                })

        categories = [
            {"id": "abhisheka",   "name": "Abhisheka",     "items": abhisheka},
            {"id": "alankara",    "name": "Alankara",      "items": alankara},
            {"id": "vadamala",    "name": "Vadamala",      "items": vadamala},
            {"id": "pooja_vratha","name": "Pooja & Vratha","items": pooja},
        ]

        return jsonify({"success": True, "categories": categories})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ── Individual category endpoints ─────────────────────────────────────────────
@api_sevas_bp.route("/abhisheka", methods=["GET"])
def get_abhisheka():
    try:
        items = [_fmt_type(d, "Abhisheka", "abhisheka")
                 for d in abhisheka_types.find({"is_active": True})]
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_sevas_bp.route("/alankara", methods=["GET"])
def get_alankara():
    try:
        items = [_fmt_type(d, "Alankara", "alankara")
                 for d in alankara_types.find({"is_active": True})]
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_sevas_bp.route("/vadamala", methods=["GET"])
def get_vadamala():
    try:
        items = [_fmt_type(d, "Vadamala", "vadamala")
                 for d in vadamala_types.find({"is_active": True})]
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_sevas_bp.route("/dates/<category>", methods=["GET"])
def get_available_dates(category):
    """
    Returns a list of available date strings (YYYY-MM-DD) for a specific seva category.
    """
    try:
        today = get_current_time()
        start_date = today.date() + timedelta(days=1) # Always start from tomorrow
        available_dates = []

        if category == "abhisheka":
            # Abhisheka is available on any day starting tomorrow (let's provide 60 days)
            for i in range(60):
                current_date = start_date + timedelta(days=i)
                available_dates.append(current_date.strftime("%Y-%m-%d"))

        elif category == "alankara":
            # Alankara: Tuesdays (1) and Thursdays (3). Exclude booked dates.
            end_date_dt = today + timedelta(days=60)
            
            # Fetch already booked dates for Alankara
            booked_records = seva_collection.find(
                {
                    "seva_name": "Alankara", 
                    "seva_date": {
                        "$gte": today.replace(hour=0, minute=0, second=0, microsecond=0),
                        "$lte": end_date_dt
                    }
                },
                {"seva_date": 1, "_id": 0}
            )
            booked_dates = set()
            for record in booked_records:
                sd = record.get("seva_date")
                if isinstance(sd, (datetime, date)):
                    booked_dates.add(sd.strftime("%Y-%m-%d"))
                elif isinstance(sd, str):
                    try:
                        dt = datetime.strptime(sd, "%d-%m-%Y")
                        booked_dates.add(dt.strftime("%Y-%m-%d"))
                    except Exception:
                        booked_dates.add(sd)

            for i in range(60):
                current_date = start_date + timedelta(days=i)
                if current_date.weekday() in [1, 3]:
                    date_str = current_date.strftime("%Y-%m-%d")
                    if date_str not in booked_dates:
                        available_dates.append(date_str)

        elif category == "vadamala":
            # Vadamala: Saturdays (5), max 3 slots per day
            end_date_dt = today + timedelta(days=60)
            
            pipeline = [
                {"$match": {
                    "seva_name": "Vadamala",
                    "seva_date": {"$gte": today.replace(hour=0, minute=0, second=0, microsecond=0), "$lte": end_date_dt}
                }},
                {"$group": {
                    "_id": "$seva_date",
                    "count": {"$sum": 1}
                }},
                {"$match": {
                    "count": {"$gte": 3}
                }}
            ]
            
            fully_booked = set()
            for item in seva_collection.aggregate(pipeline):
                sd = item['_id']
                if isinstance(sd, (datetime, date)):
                    fully_booked.add(sd.strftime("%Y-%m-%d"))
                elif isinstance(sd, str):
                    try:
                        dt = datetime.strptime(sd, "%d-%m-%Y")
                        fully_booked.add(dt.strftime("%Y-%m-%d"))
                    except Exception:
                        fully_booked.add(sd)

            for i in range(60):
                current_date = start_date + timedelta(days=i)
                if current_date.weekday() == 5:
                    date_str = current_date.strftime("%Y-%m-%d")
                    if date_str not in fully_booked:
                        available_dates.append(date_str)

        else:
            return jsonify({"success": False, "message": "Unknown category for dates"}), 400

        return jsonify({"success": True, "dates": available_dates})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
