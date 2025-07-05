from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, send_file
from database import seva_collection, events_collection, donations_collection, donations_list, seva_list, user_collection
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from functools import wraps
import csv
import io
import pandas as pd
from dateutil import parser
import json
from pymongo import MongoClient

general_admin_bp = Blueprint("general_admin", __name__, url_prefix="/admin/general")  

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please login as admin to access this page.", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function

@general_admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    """Admin Dashboard with dynamic statistics"""
    # Get events statistics
    events = list(events_collection.find())
    events_count = len(events)
    current_date = datetime.now()
    upcoming_events_count = sum(1 for event in events if 
                               isinstance(event.get('date'), datetime) and 
                               event.get('date') > current_date)
    
    # Get seva statistics
    seva_types = list(seva_list.find())
    seva_types_count = len(seva_types)
    seva_bookings = list(seva_collection.find())
    seva_bookings_count = len(seva_bookings)
    
    # Get donation statistics
    donations = list(donations_collection.find())
    donations_count = len(donations)
    donation_amount = sum(float(donation.get('amount', 0)) for donation in donations)
    donation_amount = round(donation_amount, 2)
    
    # Get user statistics
    users = list(user_collection.find())
    users_count = len(users)
    verified_users_count = sum(1 for user in users if user.get('verified', False))
    
    return render_template(
        "admin/admin_dashboard.html",
        events_count=events_count,
        upcoming_events_count=upcoming_events_count,
        seva_types_count=seva_types_count,
        seva_bookings_count=seva_bookings_count,
        donations_count=donations_count,
        donation_amount=donation_amount,
        users_count=users_count,
        verified_users_count=verified_users_count
    )

@general_admin_bp.route("/manage_sevas")
@admin_required
def manage_sevas():
    """Admin view to manage sevas"""
    sevas = list(seva_list.find())  
    return render_template("admin/admin_seva_table.html", sevas=sevas)

@general_admin_bp.route("/manage_events")
@admin_required
def manage_events():
    """Admin view to manage events - redirects to the events blueprint"""
    return redirect(url_for("events.events"))

@general_admin_bp.route("/manage_donations")
@admin_required
def manage_donations():
    
    """Admin view to manage donations"""
    donations = list(donations_list.find())  
    return render_template("admin/admin_donation_list.html", donations=donations)

# ✅ Route for adding new sevas

@general_admin_bp.route("/manage_users")
@admin_required
def manage_users():
    """Admin view to manage users"""
    search_query = request.args.get('search', '')
    filter_option = request.args.get('filter', 'all')
    
    query = {}
    
    if search_query:
        query['$or'] = [
            {'name': {'$regex': search_query, '$options': 'i'}},
            {'email': {'$regex': search_query, '$options': 'i'}}
        ]

    if filter_option == 'verified':
        query['verified'] = True
    elif filter_option == 'unverified':
        query['verified'] = False

    users = list(user_collection.find(query))
    
    for user in users:
        user['_id'] = str(user['_id'])
    
    all_users = list(user_collection.find())
    total_users = len(all_users)
    verified_users = sum(1 for user in all_users if user.get('verified', False))
    unverified_users = total_users - verified_users
    
    return render_template("admin/manage_users.html", 
                           users=users, 
                           total_users=total_users,
                           verified_users=verified_users,
                           unverified_users=unverified_users)

@general_admin_bp.route("/view_user/<user_id>")
@admin_required
def view_user(user_id):
    """View a single user's details"""
    try:
        user = user_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])  # Convert ObjectId to string for template
            return render_template("admin/view_user.html", user=user)
        else:
            flash("User not found!", "danger")
            return redirect(url_for("general_admin.manage_users"))
    except Exception as e:
        flash(f"Error viewing user: {str(e)}", "danger")
        return redirect(url_for("general_admin.manage_users"))

@general_admin_bp.route("/delete_user/<user_id>")
@admin_required
def delete_user(user_id):
    """Delete a user"""
    try:
        result = user_collection.delete_one({'_id': ObjectId(user_id)})
        if result.deleted_count > 0:
            flash("User deleted successfully!", "success")
        else:
            flash("User not found!", "danger")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "danger")
    
    return redirect(url_for("general_admin.manage_users"))

@general_admin_bp.route("/reports")
@admin_required
def reports():
    """Admin view to see all seva bookings and donations"""
    report_type = request.args.get('type', 'seva')  # Default to seva if not specified
    
    if report_type == 'seva':
        # Get all seva bookings with joined data from related collections
        bookings = list(seva_collection.find())
        
        # Process the bookings to ensure all have seva_date in a comparable format
        enhanced_bookings = []
        for booking in bookings:
            booking['_id'] = str(booking['_id'])
            
            # For debugging
            print(f"Booking date value: {booking.get('booking_date')}, Type: {type(booking.get('booking_date'))}")
            
            # Format booking date - handle all possible formats
            booking_date = booking.get('booking_date')
            try:
                if isinstance(booking_date, datetime):
                    booking['formatted_date'] = booking_date.strftime('%d-%m-%Y %H:%M')
                elif isinstance(booking_date, str):
                    # Try different common date formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"]:
                        try:
                            date_obj = datetime.strptime(booking_date, fmt)
                            booking['formatted_date'] = date_obj.strftime('%d-%m-%Y %H:%M')
                            break
                        except ValueError:
                            continue
                    else:  # If no format matched
                        booking['formatted_date'] = booking_date  # Use as is
                else:
                    booking['formatted_date'] = 'N/A'
            except Exception as e:
                print(f"Error formatting booking date: {e}")
                booking['formatted_date'] = str(booking_date) if booking_date else 'N/A'
            
            # Process seva_date for sorting and display
            seva_date = booking.get('seva_date')
            try:
                if not seva_date:
                    booking['seva_date'] = 'N/A'
                    booking['seva_date_for_sort'] = datetime(1900, 1, 1)  # Default old date for sorting
                elif isinstance(seva_date, datetime):
                    booking['formatted_seva_date'] = seva_date.strftime('%d-%m-%Y')
                    booking['seva_date_for_sort'] = seva_date
                elif isinstance(seva_date, str):
                    # Try different common date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d-%m-%Y %H:%M:%S"]:
                        try:
                            date_obj = datetime.strptime(seva_date, fmt)
                            booking['formatted_seva_date'] = date_obj.strftime('%d-%m-%Y')
                            booking['seva_date_for_sort'] = date_obj
                            break
                        except ValueError:
                            continue
                    else:  # If no format matched
                        booking['formatted_seva_date'] = seva_date  # Use as is
                        booking['seva_date_for_sort'] = datetime(1900, 1, 1)
                else:
                    booking['formatted_seva_date'] = str(seva_date)
                    booking['seva_date_for_sort'] = datetime(1900, 1, 1)
            except Exception as e:
                print(f"Error formatting seva date: {e}")
                booking['formatted_seva_date'] = str(seva_date) if seva_date else 'N/A'
                booking['seva_date_for_sort'] = datetime(1900, 1, 1)
            
            # Get seva details from seva_list
            if booking.get('seva_id'):
                try:
                    seva_id = booking['seva_id']
                    if isinstance(seva_id, str) and len(seva_id) == 24:
                        seva_id = ObjectId(seva_id)
                    
                    seva_details = seva_list.find_one({'_id': seva_id})
                    if seva_details:
                        booking['seva_type'] = seva_details.get('seva_type', booking.get('seva_type', 'Unknown'))
                        booking['seva_name'] = seva_details.get('seva_name', booking.get('seva_name', 'Unknown'))
                        if not booking.get('seva_price') and seva_details.get('seva_price'):
                            booking['seva_price'] = seva_details.get('seva_price')
                except:
                    # Keep existing values if lookup fails
                    pass
            
            # Get user details from user_collection
            if booking.get('user_id'):
                try:
                    user_id = booking['user_id']
                    if isinstance(user_id, str) and len(user_id) == 24:
                        user_id = ObjectId(user_id)
                    
                    user = user_collection.find_one({'_id': user_id})
                    if user:
                        booking['user_name'] = user.get('name', booking.get('user_name', 'Unknown'))
                        booking['user_email'] = user.get('email', booking.get('email', 'Unknown'))
                        booking['user_phone'] = user.get('phone', booking.get('phone', 'Unknown'))
                    else:
                        booking['user_name'] = booking.get('user_name', booking.get('name', 'Unknown'))
                        booking['user_email'] = booking.get('email', 'Unknown')
                        booking['user_phone'] = booking.get('phone', 'Unknown')
                except:
                    booking['user_name'] = booking.get('user_name', booking.get('name', 'Unknown'))
                    booking['user_email'] = booking.get('email', 'Unknown')
                    booking['user_phone'] = booking.get('phone', 'Unknown')
            else:
                booking['user_name'] = booking.get('user_name', booking.get('name', 'Unknown'))
                booking['user_email'] = booking.get('email', 'Unknown')
                booking['user_phone'] = booking.get('phone', 'Unknown')
            
            enhanced_bookings.append(booking)
        
        # Apply date filter if provided
        date_filter = request.args.get('date_filter')
        filtered_bookings = enhanced_bookings
        if date_filter:
            try:
                # Convert the input date string to a datetime object
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d')
                
                # Filter bookings to only include those matching the selected date
                filtered_bookings = []
                for booking in enhanced_bookings:
                    if isinstance(booking.get('seva_date_for_sort'), datetime):
                        # Compare only year, month and day (ignore time)
                        booking_date = booking['seva_date_for_sort']
                        if (booking_date.year == filter_date.year and 
                            booking_date.month == filter_date.month and 
                            booking_date.day == filter_date.day):
                            filtered_bookings.append(booking)
                
                # If no bookings found after filtering, add a flash message
                if not filtered_bookings:
                    flash(f"No seva bookings found for date: {filter_date.strftime('%d-%m-%Y')}", "info")
            except ValueError:
                # If date parsing fails, show error message
                flash("Invalid date format. Please use the date picker to select a valid date.", "error")
                filtered_bookings = enhanced_bookings  # Fallback to unfiltered list
        
        # Sort bookings by seva_date_for_sort in descending order (newest to oldest)
        filtered_bookings.sort(key=lambda x: x['seva_date_for_sort'] if isinstance(x.get('seva_date_for_sort'), datetime) else datetime(1900, 1, 1), reverse=True)
        
        return render_template("admin/admin_reports.html", 
                              report_type='seva',
                              bookings=filtered_bookings)
    else:
        # Get all donations with joined data from related collections
        donations = list(donations_collection.find().sort('donation_date', -1))
        enhanced_donations = []
        
        for donation in donations:
            donation['_id'] = str(donation['_id'])
            
            # For debugging
            print(f"Donation date value: {donation.get('donation_date')}, Type: {type(donation.get('donation_date'))}")
            
            # Format donation date - handle all possible formats
            donation_date = donation.get('donation_date')
            try:
                if isinstance(donation_date, datetime):
                    donation['formatted_date'] = donation_date.strftime('%d-%m-%Y %H:%M')
                elif isinstance(donation_date, str):
                    # Try different common date formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"]:
                        try:
                            date_obj = datetime.strptime(donation_date, fmt)
                            donation['formatted_date'] = date_obj.strftime('%d-%m-%Y %H:%M')
                            break
                        except ValueError:
                            continue
                    else:  # If no format matched
                        donation['formatted_date'] = donation_date  # Use as is
                else:
                    donation['formatted_date'] = 'N/A'
            except Exception as e:
                print(f"Error formatting donation date: {e}")
                donation['formatted_date'] = str(donation_date) if donation_date else 'N/A'
            
            # Get donation name from donations_list
            if donation.get('donation_id'):
                try:
                    donation_id = donation['donation_id']
                    if isinstance(donation_id, str) and len(donation_id) == 24:
                        donation_id = ObjectId(donation_id)
                    
                    donation_details = donations_list.find_one({'_id': donation_id})
                    if donation_details:
                        donation['donation_name'] = donation_details.get('name', 'Unknown')
                    else:
                        donation['donation_name'] = donation.get('donation_name', 'Unknown')
                except:
                    donation['donation_name'] = donation.get('donation_name', 'Unknown')
            else:
                donation['donation_name'] = donation.get('donation_name', 'Unknown')
            
            # Get user details from user_collection
            if donation.get('user_id'):
                try:
                    user_id = donation['user_id']
                    if isinstance(user_id, str) and len(user_id) == 24:
                        user_id = ObjectId(user_id)
                    
                    user = user_collection.find_one({'_id': user_id})
                    if user:
                        donation['user_name'] = user.get('name', 'Unknown')
                        donation['user_email'] = user.get('email', 'Unknown')
                        donation['user_phone'] = user.get('phone', 'Unknown')
                    else:
                        donation['user_name'] = donation.get('donor_name', 'Unknown')
                        donation['user_email'] = donation.get('donor_email', 'Unknown')
                        donation['user_phone'] = 'Unknown'
                except:
                    donation['user_name'] = donation.get('donor_name', 'Unknown')
                    donation['user_email'] = donation.get('donor_email', 'Unknown')
                    donation['user_phone'] = 'Unknown'
            else:
                donation['user_name'] = donation.get('donor_name', 'Unknown')
                donation['user_email'] = donation.get('donor_email', 'Unknown')
                donation['user_phone'] = 'Unknown'
            
            enhanced_donations.append(donation)
        
        return render_template("admin/admin_reports.html", 
                              report_type='donation',
                              donations=enhanced_donations)

@general_admin_bp.route("/update_seva_status", methods=["POST"])
@admin_required
def update_seva_status():
    """Update the collection status of a seva booking"""
    booking_id = request.form.get('booking_id')
    date_filter = request.form.get('date_filter')
    
    if not booking_id:
        flash("Booking ID is required", "error")
        return redirect(url_for('general_admin.reports', type='seva'))
    
    try:
        # Convert to ObjectId
        booking_id = ObjectId(booking_id)
        
        # Update the booking status to Collected
        result = seva_collection.update_one(
            {'_id': booking_id},
            {'$set': {'status': 'Collected'}}
        )
        
        if result.modified_count > 0:
            flash("Seva status updated to Collected successfully", "success")
        else:
            flash("No booking found with the provided ID", "error")
            
    except Exception as e:
        flash(f"Error updating status: {str(e)}", "error")
    
    # Redirect back to the reports page with date filter preserved
    return redirect(url_for('general_admin.reports', type='seva', date_filter=date_filter))
