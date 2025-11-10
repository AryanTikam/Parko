from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.models import db, User, Reservation, ParkingLot, ParkingSpot, Vehicle, to_ist_str

user_bp = Blueprint('user', __name__)

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('user.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        full_name = request.form.get('full_name', '')
        address = request.form.get('address', '')
        pincode = request.form.get('pincode', '')
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('register.html')
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            phone=phone,
            full_name=full_name,
            address=address,
            pincode=pincode
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('user.login'))
    return render_template('register.html')

@user_bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if not session.get('user_id'):
        return redirect(url_for('user.login'))
    user = User.query.get_or_404(session['user_id'])
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form.get('phone', '')
        full_name = request.form.get('full_name', '')
        address = request.form.get('address', '')
        pincode = request.form.get('pincode', '')
        username_exists = User.query.filter(User.username == username, User.id != user.id).first()
        if username_exists:
            flash('Username already taken', 'error')
            return render_template('edit_profile.html', user=user)
        email_exists = User.query.filter(User.email == email, User.id != user.id).first()
        if email_exists:
            flash('Email already registered', 'error')
            return render_template('edit_profile.html', user=user)
        user.username = username
        user.email = email
        user.phone = phone
        user.full_name = full_name
        user.address = address
        user.pincode = pincode
        if session['username'] != username:
            session['username'] = username
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if current_password and new_password and confirm_password:
            if not check_password_hash(user.password_hash, current_password):
                flash('Current password is incorrect', 'error')
                return render_template('edit_profile.html', user=user)
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return render_template('edit_profile.html', user=user)
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('index'))
    return render_template('edit_profile.html', user=user)

@user_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@user_bp.route('/dashboard')
def dashboard():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('user.login'))
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
    user_reservations = Reservation.query.filter_by(
        user_id=session['user_id'],
        leaving_timestamp=None
    ).all()
    return render_template('user_dashboard.html',
        lots=lots,
        reservations=user_reservations,
        filters={
            'search': search,
            'min_price': min_price,
            'max_price': max_price,
            'availability': availability
        })

@user_bp.route('/summary')
def summary():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('user.login'))
    user_parking_history = db.session.query(
        Reservation,
        ParkingSpot,
        ParkingLot,
        Vehicle
    ).join(
        ParkingSpot, Reservation.spot_id == ParkingSpot.id
    ).join(
        ParkingLot, ParkingSpot.lot_id == ParkingLot.id
    ).join(
        Vehicle, Reservation.vehicle_id == Vehicle.id
    ).filter(
        Reservation.user_id == session['user_id'],
        Reservation.leaving_timestamp != None
    ).order_by(
        Reservation.parking_timestamp.desc()
    ).all()
    total_spent = db.session.query(
        db.func.sum(Reservation.parking_cost)
    ).filter(
        Reservation.user_id == session['user_id'],
        Reservation.leaving_timestamp != None
    ).scalar() or 0
    active_reservations = Reservation.query.filter_by(
        user_id=session['user_id'],
        leaving_timestamp=None
    ).count()
    return render_template('user_summary.html',
        parking_history=user_parking_history,
        total_spent=total_spent,
        active_reservations=active_reservations)

@user_bp.route('/vehicles')
def vehicles():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('user.login'))
    user_vehicles = Vehicle.query.filter_by(user_id=session['user_id']).all()
    return render_template('user_vehicles.html', vehicles=user_vehicles)

@user_bp.route('/add_vehicle', methods=['GET', 'POST'])
def add_vehicle():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('user.login'))
    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number'].strip().upper()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        if not vehicle_number:
            flash('Vehicle number is required', 'error')
            return render_template('add_vehicle.html')
        existing = Vehicle.query.filter_by(vehicle_number=vehicle_number).first()
        if existing:
            flash('Vehicle number already registered', 'error')
            return render_template('add_vehicle.html')
        vehicle = Vehicle(
            user_id=session['user_id'],
            vehicle_number=vehicle_number,
            vehicle_type=vehicle_type
        )
        db.session.add(vehicle)
        db.session.commit()
        flash('Vehicle added successfully', 'success')
        return redirect(url_for('user.vehicles'))
    return render_template('add_vehicle.html')

@user_bp.route('/edit_vehicle/<int:vehicle_id>', methods=['GET', 'POST'])
def edit_vehicle(vehicle_id):
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('user.login'))
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('user.vehicles'))
    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number'].strip().upper()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        if not vehicle_number:
            flash('Vehicle number is required', 'error')
            return render_template('edit_vehicle.html', vehicle=vehicle)
        existing = Vehicle.query.filter(Vehicle.vehicle_number == vehicle_number, Vehicle.id != vehicle_id).first()
        if existing:
            flash('Vehicle number already registered', 'error')
            return render_template('edit_vehicle.html', vehicle=vehicle)
        vehicle.vehicle_number = vehicle_number
        vehicle.vehicle_type = vehicle_type
        db.session.commit()
        flash('Vehicle updated successfully', 'success')
        return redirect(url_for('user.vehicles'))
    return render_template('edit_vehicle.html', vehicle=vehicle)