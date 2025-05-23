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

# Load wards GeoJSON at startup
GEOJSON_FILE = "geojson/jkd.geojson"
wards_gdf = gpd.read_file(GEOJSON_FILE)

# OpenCage API key
OPENCAGE_API_KEY = 'd0dd67bb35e54bc4ba67c965e7b37a45'


def get_user_db_connection():
    return mysql.connector.connect(**USER_DB_CONFIG)

def get_staff_db_connection():
    return mysql.connector.connect(**STAFF_DB_CONFIG)

def validate_coordinates(lat, lon):
    valid = lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
    print(f"Validating coords: lat={lat}, lon={lon} => {valid}")
    return valid

def reverse_geocode(lat, lon):
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1}
        )
        response.raise_for_status()
        data = response.json()
        if data['results']:
            location = data['results'][0].get('formatted', 'Unknown location')
            print(f"Reverse geocode result: {location}")
            return location
    except Exception as e:
        print(f"OpenCage error: {e}")
    return "Unknown location"

def jamkhandi(lat, lon):
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1}
        )
        response.raise_for_status()
        components = response.json()['results'][0]['components']

        village = components.get('village', '').lower().strip()
        town = components.get('town', '').lower().strip()
        city = components.get('city', '').lower().strip()
        state = components.get('state', '').lower().strip()
        country = components.get('country', '').lower().strip()

        location_text = " ".join([village, town, city])
        print(f"Location text: {location_text}")

        allowed_locations = ["jamakhandi"]

        has_allowed_location = any(loc in location_text for loc in allowed_locations)

        return has_allowed_location and state == "karnataka" and country == "india"

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

    point = Point(lon, lat)  # shapely uses (x=lon, y=lat)
    print(f"Looking for ward containing point: ({lat}, {lon})")

    matched_ward = None
    min_distance = float('inf')
    closest_ward = None

    buffer_distance = 0.0005  # ~50 meters buffer
    for _, row in wards_gdf.iterrows():
        polygon = row['geometry']
        if polygon is None or polygon.is_empty:
            continue

        buffered_polygon = polygon.buffer(buffer_distance)
        if buffered_polygon.contains(point):
            matched_ward = row
            print(f"Point is inside buffered ward polygon: {row['NAME']} (WARD_ID: {row['WARD_ID']})")
            break

        dist = polygon.distance(point)
        if dist < min_distance:
            min_distance = dist
            closest_ward = row

    if matched_ward is not None:
        return jsonify({
            "ward_id": matched_ward['WARD_ID'],
            "ward_name": matched_ward['NAME'],
            "in_bounds": True
        })

    location_name = reverse_geocode(lat, lon)
    if closest_ward is not None:
        return jsonify({
            "ward_id": closest_ward['WARD_ID'],
            "ward_name": closest_ward['NAME'],
            "in_bounds": False,
            "nearest_location": location_name,
            "distance": round(min_distance, 5)
        })

    return jsonify({
        "error": "Ward not found and no fallback available",
        "location": location_name
    }), 404


@user_routes.route('/submit_user', methods=['POST'])
def submit_user():
    conn = None
    cursor = None
    staff_conn = None
    staff_cursor = None

    try:
        name = request.form.get('name')
        email = request.form.get('email')
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        image = request.files.get('image')
        ward_name = request.form.get('ward')

        print(f"Form submission received: name={name}, email={email}, lat={latitude}, lon={longitude}, ward={ward_name}")

        if not all([name, email, latitude, longitude, ward_name]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        if not validate_coordinates(latitude, longitude):
            return jsonify({"success": False, "error": "Invalid latitude or longitude"}), 400

        if not jamkhandi(latitude, longitude):
            return jsonify({"success": False, "error": "Coordinates not in Rabakavi-Banahatti area"}), 400

        matched_ward = wards_gdf[wards_gdf['NAME'] == ward_name]
        if matched_ward.empty:
            return jsonify({"success": False, "error": f"Ward '{ward_name}' not found in GeoJSON"}), 400

        ward_id = int(matched_ward.iloc[0]['WARD_ID'])
        print(f"Ward found in GeoJSON: {ward_name} (WARD_ID: {ward_id})")

        # Insert user data into location DB
        conn = get_user_db_connection()
        cursor = conn.cursor()
        insert_query = '''
            INSERT INTO user_data (name, email, latitude, longitude, ward_id, image,ward_name)
            VALUES (%s, %s, %s, %s, %s, %s,%s)
        '''
        image_data = image.read() if image else None
        cursor.execute(insert_query, (name, email, latitude, longitude, ward_id, image_data,ward_name))
        conn.commit()

        # Get worker email from staff DB
        staff_conn = get_staff_db_connection()
        staff_cursor = staff_conn.cursor(dictionary=True)
        staff_cursor.execute('SELECT email FROM staff WHERE ward_id = %s LIMIT 1', (ward_id,))
        worker = staff_cursor.fetchone()

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
        print(f"Error in submit_user: {e}")
        return jsonify({"success": False, "error": "Internal server error."}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        if staff_cursor:
            staff_cursor.close()
        if staff_conn:
            staff_conn.close()
