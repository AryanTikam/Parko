from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Vehicle, to_ist_str
from datetime import datetime
import io, csv

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
def dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    lots = ParkingLot.query.all()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = total_spots - occupied_spots
    total_users = User.query.filter_by(is_admin=False).count()
    search = request.args.get('search', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    availability = request.args.get('availability', '')
    query = ParkingLot.query
    if search:
        query = query.filter(
            (ParkingLot.prime_location_name.contains(search)) |
            (ParkingLot.address.contains(search)) |
            (ParkingLot.pin_code.contains(search))
        )
    if min_price:
        query = query.filter(ParkingLot.price_per_hour >= min_price)
    if max_price:
        query = query.filter(ParkingLot.price_per_hour <= max_price)
    lots = query.all()
    if availability == 'available':
        lots = [lot for lot in lots if any(spot.status == 'A' for spot in lot.spots)]
    elif availability == 'full':
        lots = [lot for lot in lots if all(spot.status == 'O' for spot in lot.spots)]
    return render_template('admin_dashboard.html',
        lots=lots,
        total_spots=total_spots,
        occupied_spots=occupied_spots,
        available_spots=available_spots,
        total_users=total_users,
        filters={
            'search': search,
            'min_price': min_price,
            'max_price': max_price,
            'availability': availability
        })

@admin_bp.route('/users')
def users():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    query = User.query.filter_by(is_admin=False)
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.email.contains(search)) |
            (User.full_name.contains(search))
        )
    users = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin_users.html', users=users, search=search)

@admin_bp.route('/vehicles')
def vehicles():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    query = Vehicle.query.join(User).filter(User.is_admin == False)
    if search:
        query = query.filter(
            (Vehicle.vehicle_number.contains(search)) |
            (Vehicle.vehicle_type.contains(search)) |
            (User.username.contains(search))
        )
    vehicles = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin_vehicles.html', vehicles=vehicles, search=search)

@admin_bp.route('/summary')
def summary():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    lots = ParkingLot.query.all()
    total_revenue = db.session.query(db.func.sum(Reservation.parking_cost)).filter(
        Reservation.leaving_timestamp != None
    ).scalar() or 0
    monthly_revenue = db.session.query(
        db.func.strftime('%Y-%m', Reservation.parking_timestamp).label('month'),
        db.func.sum(Reservation.parking_cost).label('revenue')
    ).filter(
        Reservation.leaving_timestamp != None
    ).group_by(
        db.func.strftime('%Y-%m', Reservation.parking_timestamp)
    ).all()
    lot_performance = db.session.query(
        ParkingLot.prime_location_name,
        db.func.count(Reservation.id).label('bookings'),
        db.func.sum(Reservation.parking_cost).label('revenue')
    ).select_from(ParkingLot).join(
        ParkingSpot, ParkingLot.id == ParkingSpot.lot_id
    ).join(
        Reservation, ParkingSpot.id == Reservation.spot_id
    ).filter(
        Reservation.leaving_timestamp != None
    ).group_by(ParkingLot.id).all()
    lot_data = []
    for lot in lots:
        occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        total_spots = ParkingSpot.query.filter_by(lot_id=lot.id).count()
        lot_data.append({
            'name': lot.prime_location_name,
            'occupied_spots': occupied_spots,
            'total_spots': total_spots
        })
    return render_template('admin_summary.html',
        lots=lots,
        total_revenue=total_revenue,
        monthly_revenue=monthly_revenue,
        lot_performance=lot_performance,
        lot_data=lot_data)

@admin_bp.route('/export_summary')
def export_summary():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Parko - Statistical Summary'])
    writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    writer.writerow(['Overall Statistics'])
    writer.writerow(['Total Parking Lots', ParkingLot.query.count()])
    writer.writerow(['Total Parking Spots', ParkingSpot.query.count()])
    writer.writerow(['Total Users', User.query.filter_by(is_admin=False).count()])
    writer.writerow(['Total Reservations', Reservation.query.count()])
    writer.writerow([])
    writer.writerow(['Lot-wise Statistics'])
    writer.writerow(['Location Name', 'Address', 'Pin Code', 'Price/Hour', 'Total Spots', 'Occupied Spots', 'Available Spots'])
    for lot in ParkingLot.query.all():
        total_spots = ParkingSpot.query.filter_by(lot_id=lot.id).count()
        occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available_spots = total_spots - occupied_spots
        writer.writerow([
            lot.prime_location_name,
            lot.address,
            lot.pin_code,
            lot.price_per_hour,
            total_spots,
            occupied_spots,
            available_spots
        ])
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=parko_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return response

@admin_bp.route('/create_lot', methods=['GET', 'POST'])
def create_lot():
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price = float(request.form['price'])
        spots = int(request.form['spots'])
        lot = ParkingLot(
            prime_location_name=name,
            address=address,
            pin_code=pin_code,
            price_per_hour=price,
            maximum_number_of_spots=spots
        )
        db.session.add(lot)
        db.session.commit()
        for i in range(1, spots + 1):
            spot = ParkingSpot(
                lot_id=lot.id,
                spot_number=f'{name[:1]}{i:02d}',
                status='A'
            )
            db.session.add(spot)
        db.session.commit()
        flash('Parking lot created successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('create_lot.html')

@admin_bp.route('/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if not session.get('is_admin'):
        return redirect(url_for('user.login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        lot.prime_location_name = request.form['name']
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        lot.price_per_hour = float(request.form['price'])
        new_spots = int(request.form.get('new_spots', 0))
        # Remove selected spots
        spots_to_remove = request.form.getlist('spots_to_remove')
        for spot_id in spots_to_remove:
            spot = ParkingSpot.query.get(int(spot_id))
            if spot and spot.status == 'A':
                db.session.delete(spot)
        # Add new spots
        for i in range(lot.maximum_number_of_spots + 1, lot.maximum_number_of_spots + new_spots + 1):
            spot = ParkingSpot(
                lot_id=lot.id,
                spot_number=f'{lot.prime_location_name[:1]}{i:02d}',
                status='A'
            )
            db.session.add(spot)
        lot.maximum_number_of_spots += new_spots
        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('edit_lot.html', lot=lot)

@admin_bp.route('/delete_lot/<int:lot_id>', methods=['POST'])
def delete_lot(lot_id):
    if not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'})
    lot = ParkingLot.query.get_or_404(lot_id)
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied_spots > 0:
        return jsonify({'success': False, 'error': 'Cannot delete lot with occupied spots'})
    db.session.delete(lot)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Parking lot deleted successfully'})