

import os
from flask import Flask, g, render_template
import psycopg2
from psycopg2 import OperationalError
from flask_mail import Mail
from mail_setup import mail
from routes.user_routes import user_routes
from routes.staff_routes import staff_routes
from routes.worker_routes import worker_routes
from routes.central_routes import central_routes

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Use your fixed URLs directly here:
app.config['STAFF_DB_URL'] = 'postgresql://neondb_owner:npg_64pzLnOdiYEm@ep-summer-rice-a11qf6db-pooler.ap-southeast-1.aws.neon.tech/staff?sslmode=require'
app.config['LOCATION_DB_URL'] = 'postgresql://neondb_owner:npg_64pzLnOdiYEm@ep-summer-rice-a11qf6db-pooler.ap-southeast-1.aws.neon.tech/location?sslmode=require'

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'swachhindiamission@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'wucy ksgf lwuq zjeb')  # Use env vars in production!

mail.init_app(app)

@app.before_request
def before_request():
    try:
        g.staff_db = psycopg2.connect(app.config['STAFF_DB_URL'])
    except OperationalError as e:
        print(f"Staff DB connection failed: {e}")
        g.staff_db = None
    try:
        g.location_db = psycopg2.connect(app.config['LOCATION_DB_URL'])
    except OperationalError as e:
        print(f"Location DB connection failed: {e}")
        g.location_db = None

@app.teardown_appcontext
def close_db(error):
    staff_db = g.pop('staff_db', None)
    location_db = g.pop('location_db', None)
    if staff_db:
        staff_db.close()
    if location_db:
        location_db.close()

# Register routes
app.register_blueprint(user_routes, url_prefix='/user')
app.register_blueprint(staff_routes, url_prefix='/staff')
app.register_blueprint(worker_routes, url_prefix='/worker')
app.register_blueprint(central_routes, url_prefix='/central')

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ✅ This is the Render-specific fix
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)