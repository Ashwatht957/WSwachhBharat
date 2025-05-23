import mysql.connector
from flask import Blueprint, render_template, request, jsonify
from shapely.geometry import Point
import geopandas as gpd
import requests
from flask_mail import Message
from mail_setup import mail  # Your configured Flask-Mail instance

# Blueprint setup
user_routes = Blueprint('user_routes', __name__, template_folder='../templates/user')

# Database configs
USER_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'location'
}

STAFF_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'staff'
}

# Load wards GeoJSON once at startup
GEOJSON_FILE = "geojson/RB.geojson"
wards_gdf = gpd.read_file(GEOJSON_FILE)

# OpenCage API key
OPENCAGE_API_KEY = 'd0dd67bb35e54bc4ba67c965e7b37a45'


def get_user_db_connection():
    return mysql.connector.connect(**USER_DB_CONFIG)

def get_staff_db_connection():
    return mysql.connector.connect(**STAFF_DB_CONFIG)

def validate_coordinates(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
        valid = -90 <= lat <= 90 and -180 <= lon <= 180
        print(f"Validating coords: lat={lat}, lon={lon} => {valid}")
        return valid
    except (TypeError, ValueError):
        print(f"Invalid coords: lat={lat}, lon={lon}")
        return False

def reverse_geocode(lat, lon):
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get('results'):
            location = data['results'][0].get('formatted', 'Unknown location')
            print(f"Reverse geocode result: {location}")
            return location
    except Exception as e:
        print(f"OpenCage error: {e}")
    return "Unknown location"

def is_in_rabakavi_banahatti(lat, lon):
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1},
            timeout=5
        )
        response.raise_for_status()
        components = response.json()['results'][0]['components']

        village = components.get('village', '').lower().strip()
        town = components.get('town', '').lower().strip()
        city = components.get('city', '').lower().strip()
        state = components.get('state', '').lower().strip()
        country = components.get('country', '').lower().strip()

        location_text = " ".join([village, town, city])
        allowed_locations = ["rabakavi", "banahatti", "rampur", "hosur"]

        is_valid = any(loc in location_text for loc in allowed_locations) and state == "karnataka" and country == "india"
        print(f"Location check: {location_text}, state={state}, country={country} => {is_valid}")
        return is_valid
    except Exception as e:
        print(f"OpenCage location check error: {e}")
        return False

# Routes

@user_routes.route('/')
def home():
    return render_template('user/user_form.html')

@user_routes.route('/get_ward')
def get_ward():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not validate_coordinates(lat, lon):
        return jsonify({"error": "Invalid latitude or longitude"}), 400

    point = Point(lon, lat)
    print(f"Checking point: ({lat}, {lon})")

    # Ensure all geometries are valid
    wards_gdf['geometry'] = wards_gdf['geometry'].buffer(0)

    # Try exact match first
    for _, row in wards_gdf.iterrows():
        if row['geometry'].contains(point):
            print(f"Exact match found: {row['NAME']} (WARD_ID: {row['WARD_ID']})")
            return jsonify({
                "ward_id": row['WARD_ID'],
                "ward_name": row['NAME'],
                "in_bounds": True
            })

    # Try buffered match (fallback)
    buffer_dist = 0.0005  # ~50m
    for _, row in wards_gdf.iterrows():
        buffered = row['geometry'].buffer(buffer_dist)
        if buffered.contains(point):
            print(f"Buffered match found: {row['NAME']} (WARD_ID: {row['WARD_ID']})")
            return jsonify({
                "ward_id": row['WARD_ID'],
                "ward_name": row['NAME'],
                "in_bounds": True,
                "note": "Buffered match"
            })

    # No match — reverse geocode for info
    location_name = reverse_geocode(lat, lon)
    print("No match found. Location:", location_name)

    return jsonify({
        "error": "Point not in any ward",
        "location": location_name
    }), 404



@user_routes.route('/submit_user', methods=['POST'])
def submit_user():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        image = request.files.get('image')
        ward_name = request.form.get('ward')

        print(f"Received submission: name={name}, email={email}, lat={latitude}, lon={longitude}, ward={ward_name}")

        # Basic validation
        if not all([name, email, latitude, longitude, ward_name]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        if not validate_coordinates(latitude, longitude):
            return jsonify({"success": False, "error": "Invalid latitude or longitude"}), 400

        if not is_in_rabakavi_banahatti(latitude, longitude):
            return jsonify({"success": False, "error": "Coordinates not in Rabakavi-Banahatti area"}), 400

        matched_ward = wards_gdf[wards_gdf['NAME'] == ward_name]
        if matched_ward.empty:
            return jsonify({"success": False, "error": f"Ward '{ward_name}' not found in GeoJSON"}), 400

        ward_id = int(matched_ward.iloc[0]['WARD_ID'])
        print(f"Ward matched: {ward_name} (WARD_ID: {ward_id})")

        # Insert data into location DB
        conn = get_user_db_connection()
        cursor = conn.cursor()
        image_data = image.read() if image else None

        insert_query = """
            INSERT INTO user_data (name, email, latitude, longitude, ward_id, image, ward_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (name, email, latitude, longitude, ward_id, image_data, ward_name))
        conn.commit()
        cursor.close()
        conn.close()

        # Fetch worker email from staff DB
        staff_conn = get_staff_db_connection()
        staff_cursor = staff_conn.cursor(dictionary=True)
        staff_cursor.execute('SELECT email FROM staff WHERE ward_id = %s LIMIT 1', (ward_id,))
        worker = staff_cursor.fetchone()
        staff_cursor.close()
        staff_conn.close()

        if not worker or not worker.get('email'):
            return jsonify({"success": False, "error": "No worker found for this ward."}), 400

        worker_email = worker['email']

        # Send notification email
        msg = Message(
            subject='New Location Submitted',
            sender='swachhindiamission@gmail.com',
            recipients=[worker_email],
            body=(
                f"A new location has been submitted:\n\n"
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Latitude: {latitude}\n"
                f"Longitude: {longitude}\n"
                f"Ward Name: {ward_name}\n"
                f"Ward ID: {ward_id}\n\n"
                "Please visit the location and complete the work."
            )
        )
        mail.send(msg)

        return jsonify({"success": True, "message": "Data inserted and email sent successfully!"})

    except mysql.connector.Error as db_err:
        print(f"Database error: {db_err}")
        return jsonify({"success": False, "error": "Database error occurred."}), 500

    except Exception as e:
        print(f"submit_user error: {e}")
        return jsonify({"success": False, "error": "Internal server error."}), 500
