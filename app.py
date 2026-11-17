import os
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from functools import wraps
from dotenv import load_dotenv

from database import (
    initialize_database,
    get_connection,
    book_slot,
    cancel_booking
)

# Load private environment variables
load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not app.secret_key or not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise RuntimeError("Missing required settings in .env file.")

initialize_database()


# ADMIN LOGIN PROTECTION
def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as administrator.", "error")
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapper


# CUSTOMER HOME PAGE
@app.route('/')
def home():
    connection = get_connection()

    slots = connection.execute(
        "SELECT * FROM parking_slots ORDER BY id"
    ).fetchall()

    connection.close()

    return render_template('index.html', slots=slots)


# CUSTOMER BOOKING
@app.route('/book', methods=['POST'])
def book():
    slot_number = request.form.get('slot_number', '').strip()
    customer_name = request.form.get('customer_name', '').strip()
    vehicle_number = request.form.get('vehicle_number', '').strip().upper()

    if not slot_number or not customer_name or not vehicle_number:
        flash("Please fill in all booking details.", "error")
        return redirect(url_for('home'))

    if len(customer_name) > 100 or len(vehicle_number) > 20:
        flash("Please enter valid customer and vehicle details.", "error")
        return redirect(url_for('home'))

    try:
        success = book_slot(slot_number, customer_name, vehicle_number)

        if success:
            flash(
                f"Booking confirmed! Slot {slot_number} is reserved for {customer_name}.",
                "success"
            )
        else:
            flash(
                f"Sorry! Slot {slot_number} is no longer available.",
                "error"
            )

    except Exception:
        app.logger.exception("Booking failed")
        flash("Something went wrong. Please try again.", "error")

    return redirect(url_for('home'))


# CUSTOMER BOOKING HISTORY
@app.route('/bookings')
def bookings():
    connection = get_connection()

    all_bookings = connection.execute("""
        SELECT * FROM bookings
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        'bookings.html',
        bookings=all_bookings
    )


# CUSTOMER CANCELLATION
@app.route('/cancel/<int:booking_id>', methods=['POST'])
def cancel(booking_id):
    try:
        success = cancel_booking(booking_id)

        if success:
            flash(
                f"Booking #{booking_id} cancelled successfully. The slot is available again.",
                "success"
            )
        else:
            flash(
                "This booking could not be cancelled. It may already be cancelled.",
                "error"
            )

    except Exception:
        app.logger.exception("Cancellation failed")
        flash("Something went wrong while cancelling.", "error")

    return redirect(url_for('bookings'))


# ADMIN LOGIN PAGE
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash("Welcome to the ParkEase Admin Dashboard!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Incorrect username or password.", "error")

    return render_template('admin_login.html')


# ADMIN DASHBOARD
@app.route('/admin')
@admin_required
def admin_dashboard():
    connection = get_connection()

    total_slots = connection.execute(
        "SELECT COUNT(*) FROM parking_slots"
    ).fetchone()[0]

    available_slots = connection.execute("""
        SELECT COUNT(*) FROM parking_slots
        WHERE status = 'Available'
    """).fetchone()[0]

    occupied_slots = connection.execute("""
        SELECT COUNT(*) FROM parking_slots
        WHERE status = 'Occupied'
    """).fetchone()[0]

    all_slots = connection.execute("""
        SELECT * FROM parking_slots
        ORDER BY id
    """).fetchall()

    all_bookings = connection.execute("""
        SELECT * FROM bookings
        ORDER BY id DESC
    """).fetchall()

    total_bookings = connection.execute(
        "SELECT COUNT(*) FROM bookings"
    ).fetchone()[0]

    connection.close()

    return render_template(
        'admin.html',
        total_slots=total_slots,
        available_slots=available_slots,
        occupied_slots=occupied_slots,
        all_slots=all_slots,
        all_bookings=all_bookings,
        total_bookings=total_bookings
    )


# ADMIN PARKING SLOT MANAGEMENT
@app.route('/admin/slot/<int:slot_id>/status', methods=['POST'])
@admin_required
def update_slot_status(slot_id):

    new_status = request.form.get('status', '').strip()

    if new_status not in ['Available', 'Occupied']:
        flash("Invalid parking slot status.", "error")
        return redirect(url_for('admin_dashboard'))

    connection = get_connection()

    try:
        slot = connection.execute("""
            SELECT slot_number FROM parking_slots
            WHERE id = ?
        """, (slot_id,)).fetchone()

        if slot is None:
            flash("Parking slot not found.", "error")
            return redirect(url_for('admin_dashboard'))

        active_booking = connection.execute("""
            SELECT id FROM bookings
            WHERE slot_number = ? AND status = 'Confirmed'
        """, (slot['slot_number'],)).fetchone()

        if new_status == 'Available' and active_booking:
            flash(
                "This slot has an active customer booking. Cancel the booking first.",
                "error"
            )
            return redirect(url_for('admin_dashboard'))

        connection.execute("""
            UPDATE parking_slots
            SET status = ?
            WHERE id = ?
        """, (new_status, slot_id))

        connection.commit()

        flash(
            f"Slot {slot['slot_number']} updated to {new_status}.",
            "success"
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Slot update failed")
        flash("Unable to update parking slot.", "error")

    finally:
        connection.close()

    return redirect(url_for('admin_dashboard'))


# ADMIN LOGOUT
@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("You have logged out successfully.", "success")
    return redirect(url_for('admin_login'))


if __name__ == '__main__':
    app.run(debug=True)