from flask import Blueprint, jsonify
from database import events_collection
from datetime import datetime
from utils import get_current_time

api_events_bp = Blueprint('api_events', __name__)


def to_naive(dt):
    """Remove timezone info from datetime."""
    if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


@api_events_bp.route('/', methods=['GET'])
def get_events():
    """Return all events split into upcoming and past."""
    try:
        current_date = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
        current_date = to_naive(current_date)

        all_events = list(events_collection.find())

        upcoming = []
        past = []

        for event in all_events:
            # Normalise the date field to a naive datetime
            raw_date = event.get('date')
            if not isinstance(raw_date, datetime):
                try:
                    if isinstance(raw_date, str):
                        raw_date = datetime.strptime(raw_date, '%Y-%m-%d')
                    else:
                        raw_date = current_date
                except (ValueError, TypeError):
                    raw_date = current_date

            event_date = to_naive(raw_date)

            # Build a clean serialisable dict
            clean = {
                'id': str(event['_id']),
                'title': event.get('title', 'Temple Event'),
                'venue': event.get('venue', 'Temple Premises'),
                'description': event.get('description', ''),
                # Format: "15 Aug 2025"
                'date_display': event_date.strftime('%d %b %Y'),
                # Separate day / month for the card badge
                'day': event_date.strftime('%d'),
                'month': event_date.strftime('%b').upper(),
                'is_past': event_date < current_date,
            }

            if event_date >= current_date:
                upcoming.append(clean)
            else:
                past.append(clean)

        # Sort upcoming ascending, past descending
        upcoming.sort(key=lambda x: x['date_display'])
        past.sort(key=lambda x: x['date_display'], reverse=True)

        return jsonify({
            'success': True,
            'upcoming': upcoming,
            'past': past,
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
