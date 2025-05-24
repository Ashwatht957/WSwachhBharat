import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, jsonify, g
from shapely.geometry import Point
import geopandas as gpd
import requests
from flask_mail import Message
from mail_setup import mail

user_routes = Blueprint('user_routes', __name__, template_folder='../templates/user')

# Load ward boundaries from GeoJSON once at module load
GEOJSON_FILE = "geojson/RB.geojson"
try:
    wards_gdf = gpd.read_file(GEOJSON_FILE)
except Exception as e:
    print(f"[ERROR] Failed to load GeoJSON file '{GEOJSON_FILE}': {e}")
    wards_gdf = None

OPENCAGE_API_KEY = 'd0dd67bb35e54bc4ba67c965e7b37a45'

def validate_coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except Exception:
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
            return data['results'][0].get('formatted', 'Unknown location')
        else:
            return "Unknown location"
    except Exception as e:
        print(f"[ERROR] Reverse geocoding failed: {e}")
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
        location_parts = " ".join([
            components.get('village', ''),
            components.get('town', ''),
            components.get('city', '')
        ]).lower()
        return (
            any(loc in location_parts for loc in ["rabakavi", "banahatti", "rampur", "hosur"]) and
            components.get('state', '').lower() == 'karnataka' and
            components.get('country', '').lower() == 'india'
        )
    except Exception as e:
        print(f"[ERROR] Location validation error: {e}")
        return False

@user_routes.route('/')
def home():
    return render_template('user/user_form.html')

@user_routes.route('/get_ward')
def get_ward():
    if wards_gdf is None:
        return jsonify({"error": "Ward boundaries data not loaded"}), 500

    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not validate_coordinates(lat, lon):
        return jsonify({"error": "Invalid latitude or longitude"}), 400

    point = Point(lon, lat)
    wards_gdf['geometry'] = wards_gdf['geometry'].buffer(0)  # Clean geometries

    for _, row in wards_gdf.iterrows():
        if row['geometry'].contains(point):
            return jsonify({
                "ward_id": row['WARD_ID'],
                "ward_name": row['NAME'],
                "in_bounds": True
            })

    # Try buffered detection
    for _, row in wards_gdf.iterrows():
        if row['geometry'].buffer(0.0005).contains(point):
            return jsonify({
                "ward_id": row['WARD_ID'],
                "ward_name": row['NAME'],
                "in_bounds": True,
                "note": "Buffered match"
            })

    return jsonify({
        "error": "Point not in any ward",
        "location": reverse_geocode(lat, lon)
    }), 404
import sys
# ...existing imports...

@user_routes.route('/submit_user', methods=['POST'])
def submit_user():
    try:
        if wards_gdf is None:
            return jsonify({"success": False, "error": "Ward boundaries data not loaded"}), 500

        # Debug: Print form and file data to server logs
        print("Form Data:", request.form, file=sys.stderr)
        print("File Data:", request.files, file=sys.stderr)

        name = request.form.get('name')
        email = request.form.get('email')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        ward_name = request.form.get('ward')
        image = request.files.get('image')

        print(f"[DEBUG] Submission received: name={name}, email={email}, lat={latitude}, lon={longitude}, ward={ward_name}")

        # Validate DB connections
        if not hasattr(g, 'location_db') or not hasattr(g, 'staff_db'):
            print("[ERROR] Database connection(s) not found in Flask g")
            return jsonify({"success": False, "error": "Database connection error"}), 500

        if g.location_db is None or g.staff_db is None:
            print("[ERROR] One or both database connections are None")
            return jsonify({"success": False, "error": "Database connection error"}), 500

        # Validate required fields
        if not all([name, email, latitude, longitude, ward_name]):
            print("[ERROR] Missing required fields")
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # Validate coordinates
        if not validate_coordinates(latitude, longitude):
            print("[ERROR] Invalid coordinates")
            return jsonify({"success": False, "error": "Invalid coordinates"}), 400

        latitude = float(latitude)
        longitude = float(longitude)

        # Validate location inside service area
        if not is_in_rabakavi_banahatti(latitude, longitude):
            print("[ERROR] Outside service area")
            return jsonify({"success": False, "error": "Outside service area"}), 400

        # Validate ward name exists in GeoJSON
        matched_ward = wards_gdf[wards_gdf['NAME'] == ward_name]
        if matched_ward.empty:
            print(f"[ERROR] Ward '{ward_name}' not found in GeoJSON")
            return jsonify({"success": False, "error": f"Ward '{ward_name}' not found"}), 400

        ward_id = int(matched_ward.iloc[0]['WARD_ID'])

        # Read image binary data safely
        image_data = None
        if image:
            try:
                image_data = image.read()
                if not image_data:
                    print("[WARN] Uploaded image file is empty")
                    image_data = None
            except Exception as e:
                print(f"[ERROR] Reading image file failed: {e}")
                return jsonify({"success": False, "error": "Invalid image file"}), 400

        # Insert user data into location_db
        try:
            location_db = g.location_db
            cursor = location_db.cursor()
            cursor.execute("""
                INSERT INTO user_data (name, email, latitude, longitude, ward_id, image, ward_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, email, latitude, longitude, ward_id,
                  psycopg2.Binary(image_data) if image_data else None, ward_name))
            location_db.commit()
            cursor.close()
            print("[DEBUG] User data inserted into DB")
        except psycopg2.Error as db_err:
            print(f"[DB ERROR] Code: {db_err.pgcode}, Message: {db_err.pgerror}")
            return jsonify({"success": False, "error": "Database error"}), 500

        # Query staff email for that ward
        staff_cursor = g.staff_db.cursor(cursor_factory=RealDictCursor)
        staff_cursor.execute("SELECT email FROM staff WHERE ward_id = %s LIMIT 1", (ward_id,))
        worker = staff_cursor.fetchone()
        staff_cursor.close()

        if not worker:
            print(f"[ERROR] No worker assigned to ward_id {ward_id}")
            return jsonify({"success": False, "error": "No worker assigned to this ward"}), 400

        # Compose and send email notification
        msg = Message(
            subject="New Location Submitted",
            sender="swachhindiamission@gmail.com",
            recipients=[worker['email']],
            body=(
                f"New location submitted:\n\n"
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Latitude: {latitude}\n"
                f"Longitude: {longitude}\n"
                f"Ward: {ward_name} (ID: {ward_id})\n\n"
                "Please visit the location and complete the task."
            )
        )
        try:
            mail.send(msg)
            print(f"[DEBUG] Email sent to worker: {worker['email']}")
        except Exception as e:
            print(f"[ERROR] Failed to send email: {e}")
            return jsonify({"success": True, "message": "Submission successful but failed to send email."})

        return jsonify({"success": True, "message": "Submission successful and email sent."})

    except Exception as e:
        print(f"[UNHANDLED ERROR] {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500