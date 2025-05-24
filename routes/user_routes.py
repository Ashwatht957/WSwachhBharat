import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, jsonify, g
from shapely.geometry import Point
import geopandas as gpd
import requests
from flask_mail import Message
from mail_setup import mail

user_routes = Blueprint('user_routes', __name__, template_folder='../templates/user')

# Load ward boundaries from GeoJSON
GEOJSON_FILE = "geojson/RB.geojson"
wards_gdf = gpd.read_file(GEOJSON_FILE)

# OpenCage API key
OPENCAGE_API_KEY = 'd0dd67bb35e54bc4ba67c965e7b37a45'

# === Utility Functions ===

def validate_coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except:
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
        return data['results'][0].get('formatted', 'Unknown location') if data.get('results') else "Unknown location"
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
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
        print(f"Location validation error: {e}")
        return False

# === Routes ===

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

@user_routes.route('/submit_user', methods=['POST'])
def submit_user():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        ward_name = request.form.get('ward')
        image = request.files.get('image')

        if not all([name, email, latitude, longitude, ward_name]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        if not validate_coordinates(latitude, longitude):
            return jsonify({"success": False, "error": "Invalid coordinates"}), 400

        if not is_in_rabakavi_banahatti(latitude, longitude):
            return jsonify({"success": False, "error": "Outside service area"}), 400

        matched_ward = wards_gdf[wards_gdf['NAME'] == ward_name]
        if matched_ward.empty:
            return jsonify({"success": False, "error": f"Ward '{ward_name}' not found"}), 400

        ward_id = int(matched_ward.iloc[0]['WARD_ID'])
        image_data = image.read() if image else None

        # Insert into user_data
        location_db = g.location_db
        cursor = location_db.cursor()
        cursor.execute("""
            INSERT INTO user_data (name, email, latitude, longitude, ward_id, image, ward_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, email, latitude, longitude, ward_id,
              psycopg2.Binary(image_data) if image_data else None, ward_name))
        location_db.commit()
        cursor.close()

        # Fetch worker email
        staff_cursor = g.staff_db.cursor(cursor_factory=RealDictCursor)
        staff_cursor.execute("SELECT email FROM staff WHERE ward_id = %s LIMIT 1", (ward_id,))
        worker = staff_cursor.fetchone()
        staff_cursor.close()

        if not worker:
            return jsonify({"success": False, "error": "No worker assigned to this ward"}), 400

        # Send email
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
        mail.send(msg)

        return jsonify({"success": True, "message": "Submission successful and email sent."})

    except psycopg2.Error as db_err:
        print(f"[DB Error] {db_err}")
        return jsonify({"success": False, "error": "Database error"}), 500

    except Exception as e:
        print(f"[Unhandled Error] {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
