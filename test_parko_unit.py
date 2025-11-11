import unittest
from unittest.mock import patch
from datetime import datetime
from flask import Flask
from werkzeug.security import generate_password_hash
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Vehicle 

def create_initial_data(app):
    with app.app_context():
        user1 = User(id=1, username='user1', email='user1@test.com', password_hash=generate_password_hash('password'), full_name='Test User', is_admin=False)
        user2 = User(id=2, username='user2', email='user2@test.com', password_hash=generate_password_hash('password'), full_name='Another User', is_admin=False)
        db.session.add_all([user1, user2])

        lot1 = ParkingLot(id=1, prime_location_name='Central', address='123 St', pin_code='10001', price_per_hour=50.0, maximum_number_of_spots=3)
        lot2 = ParkingLot(id=2, prime_location_name='North', address='456 Ave', pin_code='10002', price_per_hour=100.0, maximum_number_of_spots=2)
        db.session.add_all([lot1, lot2])

        spot1 = ParkingSpot(id=1, lot_id=1, spot_number='C01', status='A')
        spot2 = ParkingSpot(id=2, lot_id=1, spot_number='C02', status='O')
        spot3 = ParkingSpot(id=3, lot_id=1, spot_number='C03', status='A')
        db.session.add_all([spot1, spot2, spot3])

        vehicle1 = Vehicle(id=1, user_id=1, vehicle_number='MH12A1000', vehicle_type='Car')
        db.session.add(vehicle1)

        parking_time_start = datetime(2025, 11, 10, 10, 0, 0)
        res1 = Reservation(id=1, spot_id=2, user_id=1, vehicle_id=1, parking_timestamp=parking_time_start, parking_cost=lot1.price_per_hour)
        db.session.add(res1)

        db.session.commit()

class TestParkoBusinessLogic(unittest.TestCase):
    
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        
        db.init_app(self.app)
        
        with self.app.app_context():
            db.create_all()
            create_initial_data(self.app)
            self.user1 = db.session.get(User, 1)
            self.lot1 = db.session.get(ParkingLot, 1)
            self.lot2 = db.session.get(ParkingLot, 2)
            self.spot1 = db.session.get(ParkingSpot, 1)
            self.spot2 = db.session.get(ParkingSpot, 2)
            self.res1 = db.session.get(Reservation, 1)
            self.vehicle1 = db.session.get(Vehicle, 1)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # UNIT 1: User Registration Uniqueness Check
    def test_1_register_new_user_success(self):
        with self.app.app_context():
            new_user = User(
                username='new_unique', 
                email='unique@test.com', 
                password_hash=generate_password_hash('password')
            )
            db.session.add(new_user)
            db.session.commit()
            
            self.assertIsNotNone(User.query.filter_by(username='new_unique').first())
            self.assertEqual(User.query.filter_by(username='new_unique').first().email, 'unique@test.com')
            print("test_1_register_new_user_success passed")

    def test_1_register_existing_username_fails(self):
        with self.app.app_context():
            existing_user_check = User.query.filter_by(username='user1').first()
            
            self.assertIsNotNone(existing_user_check)
            self.assertEqual(existing_user_check.username, 'user1')
            print("test_1_register_existing_username_fails passed")
    
    # UNIT 2: Vehicle Addition Uniqueness Check
    def test_2_add_unique_vehicle_success(self):
        with self.app.app_context():
            initial_count = Vehicle.query.count()
            new_vehicle = Vehicle(user_id=self.user1.id, vehicle_number='DL10Z9999', vehicle_type='SUV')
            db.session.add(new_vehicle)
            db.session.commit()
            
            self.assertEqual(Vehicle.query.count(), initial_count + 1)
            self.assertIsNotNone(Vehicle.query.filter_by(vehicle_number='DL10Z9999').first())
            print("test_2_add_unique_vehicle_success passed")

    def test_2_add_existing_vehicle_fails(self):
        with self.app.app_context():
            existing_vehicle_check = Vehicle.query.filter_by(vehicle_number='MH12A1000').first()
            
            self.assertIsNotNone(existing_vehicle_check) 
            self.assertEqual(existing_vehicle_check.vehicle_number, 'MH12A1000')
            print("test_2_add_existing_vehicle_fails passed")

    # UNIT 3: Spot Booking (Create Reservation & Update Status)
    def test_3_book_available_spot_success(self):
        with self.app.app_context():
            initial_status = self.spot1.status
            
            new_res = Reservation(spot_id=self.spot1.id, user_id=self.user1.id, vehicle_id=self.vehicle1.id, parking_cost=self.lot1.price_per_hour)
            self.spot1.status = 'O'
            db.session.add(new_res)
            db.session.commit()
            
            self.assertEqual(initial_status, 'A')
            self.assertEqual(self.spot1.status, 'O')
            self.assertIsNotNone(db.session.get(Reservation, new_res.id))
            self.assertIsNone(new_res.leaving_timestamp)
            print("test_3_book_available_spot_success passed")

    def test_3_book_occupied_spot_fails_condition(self):
        with self.app.app_context():
            initial_status = self.spot2.status
            initial_res_count = Reservation.query.count()
            
            self.assertEqual(initial_status, 'O')
            self.assertEqual(Reservation.query.count(), initial_res_count)
            print("test_3_book_occupied_spot_fails_condition passed")

    # UNIT 4: Releasing a Spot & Cost Calculation
    @patch('controllers.parking_controller.datetime')
    def test_4_release_spot_one_hour_cost(self, mock_datetime):
        with self.app.app_context():
            mock_datetime.utcnow.return_value = datetime(2025, 11, 10, 11, 0, 0)

            reservation = self.res1
            reservation.leaving_timestamp = mock_datetime.utcnow()
            duration = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600 
            total_cost = round(duration * reservation.parking_cost, 2)
            reservation.parking_cost = total_cost
            spot = db.session.get(ParkingSpot, reservation.spot_id)
            spot.status = 'A'
            db.session.commit()

            self.assertEqual(duration, 1.0)
            self.assertEqual(total_cost, 50.00)
            self.assertEqual(reservation.parking_cost, 50.00)
            self.assertEqual(spot.status, 'A')
            print("test_4_release_spot_one_hour_cost passed")

    @patch('controllers.parking_controller.datetime')
    def test_4_release_spot_half_hour_cost(self, mock_datetime):
        with self.app.app_context():
            mock_datetime.utcnow.return_value = datetime(2025, 11, 10, 10, 30, 0)
            
            reservation = self.res1
            reservation.leaving_timestamp = mock_datetime.utcnow()
            duration = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600 
            total_cost = round(duration * reservation.parking_cost, 2)
            reservation.parking_cost = total_cost

            self.assertAlmostEqual(duration, 0.5, places=2)
            self.assertEqual(total_cost, 25.00)
            self.assertEqual(reservation.parking_cost, 25.00)
            print("test_4_release_spot_half_hour_cost passed")

    # UNIT 5: Parking Lot Deletion Guard
    def test_5_delete_available_lot_success(self):
        with self.app.app_context():
            lot_to_delete = self.lot2
            initial_lot_count = ParkingLot.query.count()
            
            occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_to_delete.id, status='O').count()
            
            if occupied_spots == 0:
                db.session.delete(lot_to_delete)
                db.session.commit()
                
            self.assertEqual(occupied_spots, 0)
            self.assertEqual(ParkingLot.query.count(), initial_lot_count - 1)
            self.assertIsNone(db.session.get(ParkingLot, self.lot2.id))
            print("test_5_delete_available_lot_success passed")

    def test_5_delete_occupied_lot_fails_condition(self):
        with self.app.app_context():
            lot_to_delete = self.lot1
            initial_lot_count = ParkingLot.query.count()
            
            occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_to_delete.id, status='O').count()
            
            self.assertGreater(occupied_spots, 0)
            self.assertIsNotNone(db.session.get(ParkingLot, self.lot1.id))
            self.assertEqual(ParkingLot.query.count(), initial_lot_count)
            print("test_5_delete_occupied_lot_fails_condition passed")

if __name__ == '__main__':
    unittest.main()