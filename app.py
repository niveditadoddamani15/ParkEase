import os
import io
import base64
from functools import wraps

import qrcode

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, jsonify
)
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    initialize_database,
    get_connection,
    book_slot,
    cancel_booking,
    create_customer,
    get_customer_by_email,
    get_customer_bookings,
    get_customer_activity,
    get_booking_by_qr_token,
    check_in_booking
)

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

IS_PRODUCTION = os.getenv(
    "FLASK_ENV", "development"
).lower() == "production"

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION
)

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


# CUSTOMER LOGIN PROTECTION
def customer_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("customer_id"):
            flash("Please log in to access your account.", "error")
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# CUSTOMER REGISTRATION
@app.route('/register', methods=['GET', 'POST'])
def register():

    if session.get("customer_id"):
        return redirect(url_for("customer_dashboard"))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not email or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if len(full_name) > 100 or len(email) > 254:
            flash("Please enter valid details.", "error")
            return redirect(url_for("register"))

        if '@' not in email or '.' not in email.split('@')[-1]:
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        try:
            existing_customer = get_customer_by_email(email)

            if existing_customer:
                flash("An account with this email already exists.", "error")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)
            create_customer(full_name, email, password_hash)

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))

        except Exception:
            app.logger.exception("Customer registration failed")
            flash("Unable to create your account. Please try again.", "error")

    return render_template('register.html')


# CUSTOMER LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():

    if session.get("customer_id"):
        return redirect(url_for("customer_dashboard"))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return redirect(url_for("login"))

        try:
            customer = get_customer_by_email(email)

            if customer and check_password_hash(
                customer["password_hash"], password
            ):
                session.clear()
                session["customer_id"] = customer["id"]
                session["customer_name"] = customer["full_name"]

                flash(
                    f"Welcome to ParkEase, {customer['full_name']}!",
                    "success"
                )
                return redirect(url_for("customer_dashboard"))

            flash("Incorrect email or password.", "error")

        except Exception:
            app.logger.exception("Customer login failed")
            flash("Unable to log in. Please try again.", "error")

    return render_template('login.html')


# CUSTOMER LOGOUT
@app.route('/customer/logout')
@customer_required
def customer_logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("home"))


# CUSTOMER HOME PAGE
@app.route('/')
def home():
    connection = get_connection()

    try:
        slots = connection.execute(
            "SELECT * FROM parking_slots ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    return render_template('index.html', slots=slots)


# CUSTOMER DASHBOARD
@app.route('/dashboard')
@customer_required
def customer_dashboard():

    customer_id = session["customer_id"]

    customer_bookings = get_customer_bookings(customer_id)
    recent_activity = get_customer_activity(customer_id)

    return render_template(
        'customer_dashboard.html',
        customer_name=session.get("customer_name"),
        bookings=customer_bookings,
        activities=recent_activity
    )


# CUSTOMER BOOKING
@app.route('/book', methods=['POST'])
@customer_required
def book():

    slot_number = request.form.get('slot_number', '').strip()
    customer_name = session.get("customer_name", "").strip()
    vehicle_number = request.form.get('vehicle_number', '').strip().upper()

    if not slot_number or not customer_name or not vehicle_number:
        flash("Please fill in all booking details.", "error")
        return redirect(url_for('home'))

    if len(vehicle_number) > 20:
        flash("Please enter a valid vehicle number.", "error")
        return redirect(url_for('home'))

    try:
        success = book_slot(
            slot_number,
            customer_name,
            vehicle_number,
            session["customer_id"]
        )

        if success:
            flash(
                f"Booking confirmed! Slot {slot_number} is reserved for you.",
                "success"
            )
            return redirect(url_for("customer_dashboard"))

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
@customer_required
def bookings():

    all_bookings = get_customer_bookings(session["customer_id"])

    return render_template(
        'bookings.html',
        bookings=all_bookings
    )


# CUSTOMER CANCELLATION
@app.route('/cancel/<int:booking_id>', methods=['POST'])
@customer_required
def cancel(booking_id):

    try:
        success = cancel_booking(
            booking_id,
            session["customer_id"]
        )

        if success:
            flash(
                f"Booking #{booking_id} cancelled successfully.",
                "success"
            )
        else:
            flash(
                "This booking could not be cancelled.",
                "error"
            )

    except Exception:
        app.logger.exception("Cancellation failed")
        flash("Something went wrong while cancelling.", "error")

    return redirect(url_for('customer_dashboard'))


# GENERATE QR CODE IMAGE
def generate_qr_image(qr_token):

    verification_url = url_for(
        "admin_verify",
        token=qr_token,
        _external=True
    )

    verification_url = verification_url.replace(
        "127.0.0.1",
        "10.10.22.192"
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )

    qr.add_data(verification_url)
    qr.make(fit=True)

    qr_image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    image_bytes = io.BytesIO()
    qr_image.save(image_bytes, format="PNG")

    return base64.b64encode(
        image_bytes.getvalue()
    ).decode("utf-8")


# CUSTOMER VIEW BOOKING QR CODE
@app.route('/booking/qr/<int:booking_id>')
@customer_required
def booking_qr(booking_id):

    connection = get_connection()

    try:
        booking = connection.execute("""
            SELECT *
            FROM bookings
            WHERE id = ? AND customer_id = ?
        """, (
            booking_id,
            session["customer_id"]
        )).fetchone()

    finally:
        connection.close()

    if booking is None:
        flash("Booking not found.", "error")
        return redirect(url_for("customer_dashboard"))

    if booking["status"] != "Confirmed":
        flash("QR code is unavailable for this booking.", "error")
        return redirect(url_for("customer_dashboard"))

    if not booking["qr_token"]:
        flash(
            "This is an older booking without a QR code. Please make a new booking.",
            "error"
        )
        return redirect(url_for("customer_dashboard"))

    qr_image = generate_qr_image(booking["qr_token"])

    return render_template(
        "booking_qr.html",
        booking=booking,
        qr_image=qr_image
    )


# ADMIN VERIFY QR CODE - MANUAL VERIFICATION PAGE
@app.route('/admin/verify', methods=['GET', 'POST'])
@admin_required
def admin_verify():

    booking = None
    verification_message = None
    is_valid = False

    token = request.args.get("token", "").strip()

    if request.method == "POST":
        token = request.form.get("token", "").strip()

    if token:
        try:
            booking = get_booking_by_qr_token(token)

            if booking is None:
                verification_message = "Invalid QR code. Booking not found."

            elif booking["status"] != "Confirmed":
                verification_message = "Invalid booking. This reservation is cancelled."

            elif booking["checked_in_at"] is not None:
                verification_message = "This booking has already been checked in."

            else:
                is_valid = True
                verification_message = "Valid booking! Parking access can be approved."

        except Exception:
            app.logger.exception("QR verification failed")
            verification_message = "Unable to verify QR code. Please try again."

    return render_template(
        "verify_booking.html",
        booking=booking,
        verification_message=verification_message,
        is_valid=is_valid
    )


# ADMIN QR SCANNER PAGE
@app.route('/admin/qr-scanner')
@admin_required
def admin_qr_scanner():
    return render_template("qr_scanner.html")


# VERIFY SCANNED QR CODE
@app.route('/admin/api/verify-qr', methods=['POST'])
@admin_required
def api_verify_qr():

    data = request.get_json(silent=True) or {}
    token = data.get("token", "").strip()

    if not token:
        return jsonify({
            "success": False,
            "message": "QR token is missing."
        }), 400

    try:
        booking = get_booking_by_qr_token(token)

        if booking is None:
            return jsonify({
                "success": False,
                "message": "Invalid QR code. Booking not found."
            }), 404

        if booking["status"] != "Confirmed":
            return jsonify({
                "success": False,
                "message": "This booking has been cancelled."
            }), 400

        if booking["checked_in_at"] is not None:
            return jsonify({
                "success": False,
                "message": "This booking has already been checked in."
            }), 409

        return jsonify({
            "success": True,
            "message": "Valid booking! Entry can be approved.",
            "booking": {
                "id": booking["id"],
                "customer_name": booking["customer_name"],
                "vehicle_number": booking["vehicle_number"],
                "slot_number": booking["slot_number"],
                "booking_time": str(booking["booking_time"]),
                "status": booking["status"]
            }
        })

    except Exception:
        app.logger.exception("QR API verification failed")

        return jsonify({
            "success": False,
            "message": "Unable to verify QR code."
        }), 500


# ADMIN APPROVES PARKING ENTRY
@app.route('/admin/api/check-in/<int:booking_id>', methods=['POST'])
@admin_required
def api_check_in(booking_id):

    try:
        result = check_in_booking(
            booking_id,
            session.get("admin_username", ADMIN_USERNAME)
        )

        if result == "not_found":
            return jsonify({
                "success": False,
                "message": "Booking not found."
            }), 404

        if result == "cancelled":
            return jsonify({
                "success": False,
                "message": "Cancelled bookings cannot be approved."
            }), 400

        if result == "already_checked_in":
            return jsonify({
                "success": False,
                "message": "This booking has already been checked in."
            }), 409

        return jsonify({
            "success": True,
            "message": "Vehicle entry approved successfully!"
        })

    except Exception:
        app.logger.exception("Parking check-in failed")

        return jsonify({
            "success": False,
            "message": "Unable to approve entry. Please try again."
        }), 500


# ADMIN LOGIN PAGE
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = ADMIN_USERNAME

            flash(
                "Welcome to the ParkEase Admin Dashboard!",
                "success"
            )
            return redirect(url_for("admin_dashboard"))

        flash("Incorrect username or password.", "error")

    return render_template('admin_login.html')


# ADMIN DASHBOARD
@app.route('/admin')
@admin_required
def admin_dashboard():

    connection = get_connection()

    try:
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

        recent_activities = connection.execute("""
            SELECT
                activity.id,
                activity.activity_type,
                activity.description,
                activity.created_at,
                customers.full_name AS customer_name
            FROM customer_activity AS activity
            LEFT JOIN customers
                ON customers.id = activity.customer_id
            ORDER BY activity.id DESC
            LIMIT 20
        """).fetchall()

    finally:
        connection.close()

    return render_template(
        'admin.html',
        total_slots=total_slots,
        available_slots=available_slots,
        occupied_slots=occupied_slots,
        all_slots=all_slots,
        all_bookings=all_bookings,
        total_bookings=total_bookings,
        recent_activities=recent_activities
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
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("admin_login"))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)