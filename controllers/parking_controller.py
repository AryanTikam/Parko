from flask import Blueprint, render_template, request, session, jsonify
from models.models import db, ParkingLot, ParkingSpot, Reservation, User, Vehicle, to_ist_str
from datetime import datetime

parking_bp = Blueprint('parking', __name__)

@parking_bp.route('/lot/<int:lot_id>')
def view_lot(lot_id):
    if not session.get('user_id'):
        return render_template('login.html')
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    if search:
        spots = [spot for spot in spots if search.lower() in spot.spot_number.lower()]
    if status in ['A', 'O']:
        spots = [spot for spot in spots if spot.status == status]
    user_vehicles = Vehicle.query.filter_by(user_id=session['user_id']).all()
    return render_template('view_lot.html', lot=lot, spots=spots, spot_filters={'search': search, 'status': status}, user_vehicles=user_vehicles)

@parking_bp.route('/api/spot/<int:spot_id>')
def get_spot_details(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot = spot.lot
    current_reservation = None
    if spot.status == 'O':
        current_reservation = Reservation.query.filter_by(
            spot_id=spot.id,
            leaving_timestamp=None
        ).first()
    vehicle_number = None
    user_name = None
    start_time = None
    if current_reservation:
        vehicle = Vehicle.query.get(current_reservation.vehicle_id)
        vehicle_number = vehicle.vehicle_number if vehicle else None
        user_name = current_reservation.user.username if current_reservation.user else None
        start_time = to_ist_str(current_reservation.parking_timestamp)
    return jsonify({
        'spot': {
            'id': spot.id,
            'number': spot.spot_number,
            'status': spot.status
        },
        'lot': {
            'name': lot.prime_location_name,
            'price_per_hour': lot.price_per_hour,
            'address': lot.address
        },
        'current_reservation': {
            'vehicle_number': vehicle_number,
            'user': user_name,
            'start_time': start_time
        } if current_reservation else None
    })

@parking_bp.route('/api/reservation-details/<int:spot_id>')
def get_reservation_details(spot_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    spot = ParkingSpot.query.get_or_404(spot_id)
    reservation = Reservation.query.filter_by(
        spot_id=spot_id,
        leaving_timestamp=None
    ).first()
    if not reservation:
        return jsonify({'error': 'No active reservation'}), 404
    parking_time = reservation.parking_timestamp
    current_time = datetime.utcnow()
    elapsed_seconds = (current_time - parking_time).total_seconds()
    elapsed_hours = elapsed_seconds / 3600
    current_cost = round(elapsed_hours * spot.lot.price_per_hour, 2)
    hours = int(elapsed_hours)
    minutes = int((elapsed_hours - hours) * 60)
    elapsed_time_formatted = f"{hours} hours, {minutes} minutes"
    user = User.query.get(reservation.user_id)
    vehicle = Vehicle.query.get(reservation.vehicle_id)
    return jsonify({
        'spot_id': spot.id,
        'spot_number': spot.spot_number,
        'user_id': user.id if user else None,
        'username': user.username if user else 'Unknown',
        'user_full_name': user.full_name if user else 'Unknown',
        'vehicle_number': vehicle.vehicle_number if vehicle else 'Unknown',
        'vehicle_type': vehicle.vehicle_type if vehicle else '',
        'parking_time': to_ist_str(reservation.parking_timestamp),
        'cost_per_hour': spot.lot.price_per_hour,
        'current_cost': current_cost,
        'elapsed_time': elapsed_time_formatted,
        'reservation_id': reservation.id
    })

@parking_bp.route('/book_spot/<int:spot_id>', methods=['POST'])
def book_spot(spot_id):
    if not session.get('user_id') or session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    spot = ParkingSpot.query.get_or_404(spot_id)
    if spot.status == 'O':
        return jsonify({'success': False, 'error': 'Spot already occupied'}), 400
    vehicle_id = request.json.get('vehicle_id')
    if not vehicle_id:
        return jsonify({'success': False, 'error': 'Vehicle selection required'}), 400
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle or vehicle.user_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Invalid vehicle'}), 400
    reservation = Reservation(
        spot_id=spot_id,
        user_id=session['user_id'],
        vehicle_id=vehicle_id,
        parking_cost=spot.lot.price_per_hour
    )
    spot.status = 'O'
    db.session.add(reservation)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Spot booked successfully!',
        'reservation_id': reservation.id
    })

@parking_bp.route('/book_lot/<int:lot_id>', methods=['POST'])
def book_lot(lot_id):
    if not session.get('user_id') or session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    lot = ParkingLot.query.get_or_404(lot_id)
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').order_by(ParkingSpot.id).first()
    if not spot:
        return jsonify({'success': False, 'error': 'No available spots'}), 400
    vehicle_id = request.json.get('vehicle_id')
    if not vehicle_id:
        return jsonify({'success': False, 'error': 'Vehicle selection required'}), 400
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle or vehicle.user_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Invalid vehicle'}), 400
    reservation = Reservation(
        spot_id=spot.id,
        user_id=session['user_id'],
        vehicle_id=vehicle_id,
        parking_cost=lot.price_per_hour
    )
    spot.status = 'O'
    db.session.add(reservation)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Spot {spot.spot_number} booked successfully!',
        'reservation_id': reservation.id,
        'spot_number': spot.spot_number
    })

@parking_bp.route('/release_spot/<int:reservation_id>', methods=['POST'])
def release_spot(reservation_id):
    if not session.get('user_id') or session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.leaving_timestamp is not None:
        return jsonify({'success': False, 'error': 'Spot already released'}), 400
    reservation.leaving_timestamp = datetime.utcnow()
    duration = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600
    total_cost = round(duration * reservation.parking_cost, 2)
    reservation.parking_cost = total_cost
    spot = ParkingSpot.query.get(reservation.spot_id)
    spot.status = 'A'
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Spot released successfully! Total cost: Rs. {total_cost}',
        'total_cost': total_cost
    })