import os
from flask import Flask, render_template, g
import mysql.connector
from mail_setup import mail
from routes.user_routes import user_routes
from routes.staff_routes import staff_routes
from routes.worker_routes import worker_routes
from routes.central_routes import central_routes

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# MySQL config from env variables
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', '127.0.0.1')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'user')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'password')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'database')

# Mail config with hardcoded password
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'swachhindiamission@gmail.com')  # replace with your email if you want
app.config['MAIL_PASSWORD'] = 'eieu rwiw hgph dgnq'  # your app password here

# Initialize mail
mail.init_app(app)

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            port=app.config['MYSQL_PORT'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Register blueprints
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

if __name__ == '__main__':
    app.run(debug=True)
