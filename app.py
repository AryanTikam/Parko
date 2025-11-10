from flask import Flask, render_template
from models.models import db, create_admin, create_sample_data, to_ist_str
from controllers.user_controller import user_bp
from controllers.admin_controller import admin_bp
from controllers.parking_controller import parking_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = '23f2001216'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///park.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(parking_bp)

@app.route('/')
def index():
    return render_template('index.html')

@app.template_filter('ist')
def ist_time(dt, fmt='%Y-%m-%d %H:%M'):
    return to_ist_str(dt, fmt)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
        create_sample_data()
    app.run(debug=True)