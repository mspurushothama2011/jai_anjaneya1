"""
seva_config.py

Purpose:
    - Contains hard-coded configuration for Abhisheka, Alankara, and Vadamala sevas.
    - Provides helper functions to access these sevas by type or ID.
    - Used by booking logic and initialization scripts.

Note:
    - This file is required if you want to keep fixed (hard-coded) sevas in your system.
    - If all sevas are moved to admin/database management, this file can be removed.
"""

from datetime import timedelta
from utils import get_current_time

# Get current date for default dates
current_date = get_current_time().strftime("%d-%m-%Y")
next_week = (get_current_time() + timedelta(days=7)).strftime("%d-%m-%Y")
next_month = (get_current_time() + timedelta(days=30)).strftime("%d-%m-%Y")

# Abhisheka Sevas (fixed, not managed through admin)
ABHISHEKA_SEVAS = [
    {
        "id": "abhisheka_001",
        "seva_type": "Abhishekas",
        "seva_name": "Milk Abhisheka",
        "seva_price": 501,
        "seva_description": "Sacred milk offering to the deity.",
        "seva_date": current_date
    },
    {
        "id": "abhisheka_002",
        "seva_type": "Abhishekas",
        "seva_name": "Panchamruta Abhisheka",
        "seva_price": 1001,
        "seva_description": "Offering with five sacred ingredients: milk, curd, honey, sugar, and ghee.",
        "seva_date": next_week
    },
    {
        "id": "abhisheka_003",
        "seva_type": "Abhishekas",
        "seva_name": "Chandana Abhisheka",
        "seva_price": 751,
        "seva_description": "Sacred sandalwood offering to the deity.",
        "seva_date": next_month
    }
]

# Alankara Sevas (fixed, not managed through admin)
ALANKARA_SEVAS = [
    {
        "id": "alankara_001",
        "seva_type": "Alankar",
        "seva_name": "Flower Decoration",
        "seva_price": 1501,
        "seva_description": "Beautiful floral decoration for the deity.",
        "seva_date": current_date
    },
    {
        "id": "alankara_002",
        "seva_type": "Alankar",
        "seva_name": "Special Alankara",
        "seva_price": 2501,
        "seva_description": "Special decoration for the deity on auspicious occasions.",
        "seva_date": next_week
    }
]

# Vadamala Sevas (fixed, not managed through admin)
VADAMALA_SEVAS = [
    {
        "id": "vadamala_001",
        "seva_type": "Vadamala",
        "seva_name": "Regular Vadamala",
        "seva_price": 501,
        "seva_description": "Traditional garland offering to the deity.",
        "seva_date": current_date
    },
    {
        "id": "vadamala_002",
        "seva_type": "Vadamala",
        "seva_name": "Special Vadamala",
        "seva_price": 1001,
        "seva_description": "Special garland offering for important occasions.",
        "seva_date": next_month
    }
]

# Helper functions to access the sevas

def get_abhisheka_sevas():
    """Return all Abhisheka sevas"""
    return ABHISHEKA_SEVAS

def get_alankara_sevas():
    """Return all Alankara sevas"""
    return ALANKARA_SEVAS

def get_vadamala_sevas():
    """Return all Vadamala sevas"""
    return VADAMALA_SEVAS

def get_all_fixed_sevas():
    """Return all fixed sevas (Abhisheka, Alankara, Vadamala)"""
    return ABHISHEKA_SEVAS + ALANKARA_SEVAS + VADAMALA_SEVAS

def get_seva_by_id(seva_id):
    """Get a specific seva by ID"""
    for seva in get_all_fixed_sevas():
        if seva["id"] == seva_id:
            return seva
    return None 