
import sqlite3

DATABASE = "parking.db"


def get_connection():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            vehicle_number TEXT NOT NULL,
            booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'Confirmed'
        )
    """)

    # Add status column to an existing bookings table if needed.
    columns = [
        column["name"]
        for column in cursor.execute("PRAGMA table_info(bookings)").fetchall()
    ]

    if "status" not in columns:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN status TEXT NOT NULL DEFAULT 'Confirmed'
        """)

    for number in range(1, 21):
        slot = f"P{number:02d}"

        cursor.execute("""
            INSERT OR IGNORE INTO parking_slots
            (slot_number, status)
            VALUES (?, 'Available')
        """, (slot,))

    connection.commit()
    connection.close()

    print("Database initialized successfully!")
    print("20 parking slots are ready.")


def book_slot(slot_number, customer_name, vehicle_number):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE parking_slots
            SET status = 'Occupied'
            WHERE slot_number = ? AND status = 'Available'
        """, (slot_number,))

        if cursor.rowcount == 0:
            connection.rollback()
            return False

        cursor.execute("""
            INSERT INTO bookings
            (slot_number, customer_name, vehicle_number)
            VALUES (?, ?, ?)
        """, (slot_number, customer_name, vehicle_number))

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def cancel_booking(booking_id):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        booking = connection.execute("""
            SELECT slot_number, status
            FROM bookings
            WHERE id = ?
        """, (booking_id,)).fetchone()

        if booking is None or booking["status"] != "Confirmed":
            connection.rollback()
            return False

        connection.execute("""
            UPDATE parking_slots
            SET status = 'Available'
            WHERE slot_number = ?
        """, (booking["slot_number"],))

        connection.execute("""
            UPDATE bookings
            SET status = 'Cancelled'
            WHERE id = ?
        """, (booking_id,))

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()