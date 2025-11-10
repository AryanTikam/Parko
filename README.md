# Parko
It is a multi-user app (one requires an administrator and other users) that manages different parking lots, parking spots and parked 4-wheeler vehicles.
The goal is to streamline the normally tedious process of reserving a parking spot through the means of software and make things more convenient for all parties involved.

## Setup Instructions
1. Install Python 3.7+
2. Install required packages: `pip install flask flask-sqlalchemy werkzeug pytz`
3. Run the application: `python app.py` or `python3 app.py`
4. Access at: http://localhost:5000

## Default Admin Login
- Username: admin
- Password: admin123

## Features
- User registration and secure authentication
- Admin dashboard for lot management
- Real-time spot booking and release
- Cost calculation based on parking duration
- Search and filter functionality
- Summary charts and data export
- Minimal API endpoints for direct interactions

## API Endpoints

| Method | Endpoint                            | Description                                     |
|--------|-------------------------------------|-------------------------------------------------|
| GET    | `/api/spot/<spot_id>`               | Fetch spot details                              |
| GET    | `/api/reservation-details/<res_id>` | Admin gets the reservation cost and timestamps  |    
| POST   | `/book_spot/<spot_id>`              | Book a specific spot                            |
| POST   | `/book_lot/<lot_id>`                | Book the first available spot                   |
| POST   | `/release_spot/<res_id>`            | Release the spot                                |
| POST   | `/admin/delete_lot/<lot_id>`        | Admin deletes a lot if all the spots are free   | 
