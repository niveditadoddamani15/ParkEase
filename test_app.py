import pytest
import database
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_database = tmp_path / "test_parking.db"

    monkeypatch.setattr(
        database,
        "DATABASE",
        str(test_database)
    )

    database.initialize_database()

    app.config["TESTING"] = True

    return app.test_client()


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200


def test_booking_history_page(client):
    response = client.get("/bookings")
    assert response.status_code == 200


def test_admin_login_page(client):
    response = client.get("/admin/login")
    assert response.status_code == 200


def test_admin_requires_login(client):
    response = client.get("/admin")
    assert response.status_code == 302


def test_successful_booking(client):
    client.post("/book", data={
        "slot_number": "P01",
        "customer_name": "Test Customer",
        "vehicle_number": "KA01AB1234"
    })

    connection = database.get_connection()

    booking = connection.execute(
        "SELECT * FROM bookings WHERE vehicle_number = ?",
        ("KA01AB1234",)
    ).fetchone()

    slot = connection.execute(
        "SELECT status FROM parking_slots WHERE slot_number = ?",
        ("P01",)
    ).fetchone()

    connection.close()

    assert booking is not None
    assert booking["status"] == "Confirmed"
    assert slot["status"] == "Occupied"


def test_duplicate_booking_prevention(client):
    client.post("/book", data={
        "slot_number": "P02",
        "customer_name": "Customer One",
        "vehicle_number": "KA02AB1111"
    })

    client.post("/book", data={
        "slot_number": "P02",
        "customer_name": "Customer Two",
        "vehicle_number": "KA03AB2222"
    })

    connection = database.get_connection()

    count = connection.execute(
        "SELECT COUNT(*) FROM bookings WHERE slot_number = ?",
        ("P02",)
    ).fetchone()[0]

    connection.close()

    assert count == 1


def test_booking_cancellation(client):
    client.post("/book", data={
        "slot_number": "P03",
        "customer_name": "Cancellation Test",
        "vehicle_number": "KA04AB3333"
    })

    connection = database.get_connection()

    booking = connection.execute(
        "SELECT id FROM bookings WHERE vehicle_number = ?",
        ("KA04AB3333",)
    ).fetchone()

    connection.close()

    response = client.post(f"/cancel/{booking['id']}")
    assert response.status_code == 302

    connection = database.get_connection()

    booking_status = connection.execute(
        "SELECT status FROM bookings WHERE id = ?",
        (booking["id"],)
    ).fetchone()

    slot_status = connection.execute(
        "SELECT status FROM parking_slots WHERE slot_number = ?",
        ("P03",)
    ).fetchone()

    connection.close()

    assert booking_status["status"] == "Cancelled"
    assert slot_status["status"] == "Available"