from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash
from pytz import timezone, utc

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    full_name = db.Column(db.String(100))
    address = db.Column(db.Text)
    pincode = db.Column(db.String(10))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(utc))
    reservations = db.relationship('Reservation', backref='user', lazy=True)
    vehicles = db.relationship('Vehicle', backref='owner', lazy=True)

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    maximum_number_of_spots = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(utc))
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade='all, delete-orphan')

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(1), default='A')
    reservations = db.relationship('Reservation', backref='spot', lazy=True, cascade="all, delete-orphan")

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(utc))
    reservations = db.relationship('Reservation', backref='vehicle', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    parking_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(utc))
    leaving_timestamp = db.Column(db.DateTime)
    parking_cost = db.Column(db.Float)
    payment_status = db.Column(db.String(20), default='pending')
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))

def create_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@park.com',
            password_hash=generate_password_hash('admin123'),
            full_name='System Administrator',
            address='Admin Office, City Center',
            pincode='400001',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

def create_sample_data():
    from .models import ParkingLot, ParkingSpot
    if ParkingLot.query.count() == 0:
        lots_data = [
            {
                'name': 'Central Mall',
                'address': '123 Main Street, City Center',
                'pin_code': '400001',
                'price': 50.0,
                'spots': 20
            },
            {
                'name': 'Airport Terminal',
                'address': '456 Airport Road, International Airport',
                'pin_code': '400099',
                'price': 100.0,
                'spots': 50
            },
            {
                'name': 'Beach Plaza',
                'address': '789 Beach Road, Coastal Area',
                'pin_code': '400005',
                'price': 30.0,
                'spots': 15
            }
        ]
        for lot_data in lots_data:
            lot = ParkingLot(
                prime_location_name=lot_data['name'],
                address=lot_data['address'],
                pin_code=lot_data['pin_code'],
                price_per_hour=lot_data['price'],
                maximum_number_of_spots=lot_data['spots']
            )
            db.session.add(lot)
            db.session.commit()
            for i in range(1, lot_data['spots'] + 1):
                spot = ParkingSpot(
                    lot_id=lot.id,
                    spot_number=f'{lot_data["name"][:1]}{i:02d}',
                    status='A'
                )
                db.session.add(spot)
        db.session.commit()

def to_ist_str(dt, fmt='%Y-%m-%d %H:%M'):
    if not dt:
        return ''
    ist = timezone('Asia/Kolkata')
    if dt.tzinfo is None:
        dt = utc.localize(dt)
    return dt.astimezone(ist).strftime(fmt)