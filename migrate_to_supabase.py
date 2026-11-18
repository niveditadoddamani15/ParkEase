import os
import sqlite3
from datetime import datetime

import psycopg
from dotenv import load_dotenv

load_dotenv()

SQLITE_DATABASE = "parking.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def migrate():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing from .env")

    # Read existing local records
    sqlite_connection = sqlite3.connect(SQLITE_DATABASE)
    sqlite_connection.row_factory = sqlite3.Row

    slots = sqlite_connection.execute(
        "SELECT id, slot_number, status FROM parking_slots ORDER BY id"
    ).fetchall()

    bookings = sqlite_connection.execute(
        """
        SELECT id, slot_number, customer_name,
               vehicle_number, booking_time, status
        FROM bookings ORDER BY id
        """
    ).fetchall()

    print(f"Local parking slots found: {len(slots)}")
    print(f"Local bookings found: {len(bookings)}")

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=15) as pg:
            with pg.cursor() as cursor:

                # Transfer parking slots
                for slot in slots:
                    cursor.execute(
                        """
                        INSERT INTO parking_slots
                        (id, slot_number, status)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (slot_number)
                        DO UPDATE SET status = EXCLUDED.status
                        """,
                        (
                            slot["id"],
                            slot["slot_number"],
                            slot["status"]
                        )
                    )

                # Transfer customer bookings
                for booking in bookings:
                    booking_time = booking["booking_time"]

                    if isinstance(booking_time, str):
                        booking_time = datetime.fromisoformat(
                            booking_time
                        )

                    cursor.execute(
                        """
                        INSERT INTO bookings
                        (id, slot_number, customer_name,
                         vehicle_number, booking_time, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id)
                        DO UPDATE SET
                            slot_number = EXCLUDED.slot_number,
                            customer_name = EXCLUDED.customer_name,
                            vehicle_number = EXCLUDED.vehicle_number,
                            booking_time = EXCLUDED.booking_time,
                            status = EXCLUDED.status
                        """,
                        (
                            booking["id"],
                            booking["slot_number"],
                            booking["customer_name"],
                            booking["vehicle_number"],
                            booking_time,
                            booking["status"]
                        )
                    )

                # Synchronize ID sequences
                cursor.execute("""
                    SELECT setval(
                        pg_get_serial_sequence('parking_slots', 'id'),
                        COALESCE((SELECT MAX(id) FROM parking_slots), 1),
                        EXISTS(SELECT 1 FROM parking_slots)
                    )
                """)

                cursor.execute("""
                    SELECT setval(
                        pg_get_serial_sequence('bookings', 'id'),
                        COALESCE((SELECT MAX(id) FROM bookings), 1),
                        EXISTS(SELECT 1 FROM bookings)
                    )
                """)

                # Verify transferred record counts
                cursor.execute(
                    "SELECT COUNT(*) FROM parking_slots"
                )
                remote_slots = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM bookings"
                )
                remote_bookings = cursor.fetchone()[0]

                if remote_slots < len(slots):
                    raise RuntimeError("Parking slot count verification failed.")

                if remote_bookings < len(bookings):
                    raise RuntimeError("Booking count verification failed.")

        print("\nMigration completed successfully!")
        print(f"Parking slots in Supabase: {remote_slots}")
        print(f"Bookings in Supabase: {remote_bookings}")

    finally:
        sqlite_connection.close()


if __name__ == "__main__":
    migrate()