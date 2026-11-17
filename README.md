ParkEase – Smart Parking Management System

ParkEase is a web-based smart parking management application designed to simplify parking slot booking and administration.

It allows customers to view available parking slots, reserve parking spaces, manage bookings, and cancel reservations. Administrators can monitor parking activity and manage parking slots through a secure dashboard.

Features

Customer Module

- View 20 parking slots (P01–P20).
- Check parking slot availability.
- Book available parking slots.
- Prevent duplicate bookings for occupied slots.
- View booking history.
- Cancel confirmed bookings.

Admin Module

- Secure administrator login.
- Dashboard with parking statistics.
- View total, available, and occupied slots.
- Manage parking slot status.
- View customer booking records.
- Search bookings by customer name or vehicle number.
- Filter bookings by status.
- Secure logout.

Technologies Used

- Frontend: HTML, CSS, JavaScript
- Backend: Python, Flask
- Database: SQLite
- Testing: Pytest
- Version Control: Git and GitHub

Project Structure

smart-parking-cdd/
│
├── app.py
├── database.py
├── requirements.txt
├── test_app.py
├── .gitignore
├── .env
│
├── templates/
│   ├── index.html
│   ├── bookings.html
│   ├── admin_login.html
│   └── admin.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
└── parking.db

Note: ".env", "parking.db", and the virtual environment are excluded from Git.

Installation and Setup

1. Clone the Repository

git clone YOUR_GITHUB_REPOSITORY_URL
cd smart-parking-cdd

2. Create a Virtual Environment

python -m venv venv

3. Activate the Virtual Environment

For Windows PowerShell:

.\venv\Scripts\Activate.ps1

4. Install Dependencies

pip install -r requirements.txt

5. Configure Environment Variables

Create a ".env" file in the project root.

Add your own private values:

FLASK_SECRET_KEY=your_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_private_password

Never upload your ".env" file to GitHub.

6. Run the Application

python app.py

Open your browser and visit:

http://127.0.0.1:5000

Admin login:

http://127.0.0.1:5000/admin/login

Use the administrator credentials configured in your ".env" file.

Testing

Run the automated tests using:

pytest -v

The tests cover:

- Homepage loading.
- Booking history page.
- Admin login page.
- Admin authentication protection.
- Successful parking booking.
- Duplicate booking prevention.
- Booking cancellation.

Database

ParkEase uses SQLite to store parking slot details and customer bookings.

The database initializes 20 parking slots automatically.

Security

- Administrator credentials are stored in environment variables.
- Sensitive ".env" files are excluded from Git.
- Database files and virtual environments are excluded from Git.
- Administrator dashboard routes require authentication.

Project Objective

To develop a user-friendly parking management system that improves parking space utilization, simplifies booking operations, and provides efficient administrative control.

---

Project Name: ParkEase
Project Type: Web-Based Smart Parking Management System