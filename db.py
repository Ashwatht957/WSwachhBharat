import psycopg2
from flask import current_app, g

def get_staff_db():
    if 'staff_db' not in g:
        try:
            g.staff_db = psycopg2.connect(current_app.config['STAFF_DB_URL'])
        except Exception as e:
            print(f"❌ PostgreSQL error during init: staff_db - {e}")
            raise
    return g.staff_db

def get_location_db():
    if 'location_db' not in g:
        try:
            g.location_db = psycopg2.connect(current_app.config['LOCATION_DB_URL'])
        except Exception as e:
            print(f"submit_user error: location_db - {e}")
            raise
    return g.location_db
