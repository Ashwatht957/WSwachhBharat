import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, jsonify, g
from shapely.geometry import Point
import geopandas as gpd
import requests
from flask_mail import Message
from mail_setup import mail
import sys
import traceback

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
    """Validate latitude and longitude values"""
    try:
        lat, lon = float(lat), float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, TypeError):
        return False

def validate_input_text(text, max_length=255):
    """Validate and sanitize text input"""
    if not text or not isinstance(text, str):
        return False
    # Remove any potentially problematic characters
    text = text.strip()
    return len(text) <= max_length and len(text) > 0

def reverse_geocode(lat, lon):
    """Get address from coordinates"""
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1},
            timeout=10  # Increased timeout for mobile networks
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
    """Check if location is within service area"""
    try:
        response = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={"q": f"{lat},{lon}", "key": OPENCAGE_API_KEY, "no_annotations": 1},
            timeout=10  # Increased timeout
        )
        response.raise_for_status()
       
        if not response.json().get('results'):
            return False
           
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
    """Get ward information for given coordinates"""
    if wards_gdf is None:
        return jsonify({"error": "Ward boundaries data not loaded"}), 500

    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if not validate_coordinates(lat, lon):
        return jsonify({"error": "Invalid latitude or longitude"}), 400

    try:
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
       
    except Exception as e:
        print(f"[ERROR] Ward lookup failed: {e}")
        return jsonify({"error": "Failed to determine ward"}), 500

@user_routes.route('/submit_user', methods=['POST'])
def submit_user():
    """Handle user submission with improved error handling for mobile devices"""
    try:
        print(f"[DEBUG] Request headers: {dict(request.headers)}", file=sys.stderr)
        print(f"[DEBUG] Form Data: {dict(request.form)}", file=sys.stderr)
        print(f"[DEBUG] File Data: {list(request.files.keys())}", file=sys.stderr)

        # Check ward boundaries data
        if wards_gdf is None:
            print("[ERROR] Ward boundaries data not loaded")
            return jsonify({"success": False, "error": "Service temporarily unavailable"}), 500

        # Validate database connections
        if not hasattr(g, 'location_db') or not hasattr(g, 'staff_db'):
            print("[ERROR] Database connection(s) not found in Flask g")
            return jsonify({"success": False, "error": "Database connection not available"}), 500

        if g.location_db is None or g.staff_db is None:
            print("[ERROR] One or both database connections are None")
            return jsonify({"success": False, "error": "Database connection failed"}), 500

        # Get and validate form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        ward_name = request.form.get('ward', '').strip()
        image = request.files.get('image')

        print(f"[DEBUG] Processed data: name='{name}', email='{email}', lat='{latitude}', lon='{longitude}', ward='{ward_name}'")

        # Validate required fields
        if not all([name, email, latitude, longitude, ward_name]):
            missing_fields = []
            if not name: missing_fields.append('name')
            if not email: missing_fields.append('email')
            if not latitude: missing_fields.append('latitude')
            if not longitude: missing_fields.append('longitude')
            if not ward_name: missing_fields.append('ward')
           
            print(f"[ERROR] Missing fields: {missing_fields}")
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Validate text inputs
        if not validate_input_text(name, 100):
            print("[ERROR] Invalid name")
            return jsonify({"success": False, "error": "Invalid name format"}), 400

        if not validate_input_text(email, 255) or '@' not in email:
            print("[ERROR] Invalid email")
            return jsonify({"success": False, "error": "Invalid email format"}), 400

        # Validate and convert coordinates
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Coordinate conversion failed: {e}")
            return jsonify({"success": False, "error": "Invalid coordinate format"}), 400

        if not validate_coordinates(latitude, longitude):
            print("[ERROR] Coordinates out of range")
            return jsonify({"success": False, "error": "Coordinates out of valid range"}), 400

        # Validate location is in service area
        try:
            if not is_in_rabakavi_banahatti(latitude, longitude):
                print("[ERROR] Location outside service area")
                return jsonify({"success": False, "error": "Location is outside our service area"}), 400
        except Exception as e:
            print(f"[ERROR] Service area validation failed: {e}")
            return jsonify({"success": False, "error": "Could not validate service area"}), 500

        # Validate ward exists in GeoJSON
        try:
            matched_ward = wards_gdf[wards_gdf['NAME'] == ward_name]
            if matched_ward.empty:
                print(f"[ERROR] Ward '{ward_name}' not found in GeoJSON")
                return jsonify({"success": False, "error": f"Ward '{ward_name}' not recognized"}), 400

            ward_id = int(matched_ward.iloc[0]['WARD_ID'])
        except Exception as e:
            print(f"[ERROR] Ward validation failed: {e}")
            return jsonify({"success": False, "error": "Ward validation failed"}), 500

        # Process image with better error handling
        image_data = None
        if image and image.filename:
            try:
                # Check file size before reading (5MB limit)
                image.seek(0, 2)  # Seek to end
                size = image.tell()
                image.seek(0)  # Reset to beginning
               
                print(f"[DEBUG] Image size: {size} bytes")
               
                if size > 5 * 1024 * 1024:  # 5MB limit
                    print("[ERROR] Image too large")
                    return jsonify({"success": False, "error": "Image file too large (max 5MB)"}), 400
               
                if size == 0:
                    print("[WARN] Empty image file")
                    image_data = None
                else:
                    image_data = image.read()
                    if not image_data:
                        print("[WARN] Failed to read image data")
                        image_data = None
                       
            except Exception as e:
                print(f"[ERROR] Image processing failed: {e}")
                return jsonify({"success": False, "error": f"Image processing error: {str(e)[:50]}"}), 400

        # Database insertion with detailed error handling
        try:
            print("[DEBUG] Starting database insertion")
            location_db = g.location_db
           
            # Test connection first
            cursor = location_db.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
           
            # Insert user data
            cursor = location_db.cursor()
            insert_query = """
                INSERT INTO user_data (name, email, latitude, longitude, ward_id, image, ward_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                name, email, latitude, longitude, ward_id,
                psycopg2.Binary(image_data) if image_data else None,
                ward_name
            ))
            location_db.commit()
            cursor.close()
            print("[DEBUG] User data successfully inserted into database")
           
        except psycopg2.Error as db_err:
            location_db.rollback() if location_db else None
           
            # Detailed error logging
            error_info = {
                "pgcode": getattr(db_err, 'pgcode', 'Unknown'),
                "pgerror": str(getattr(db_err, 'pgerror', 'Unknown error')),
                "diag": str(getattr(db_err, 'diag', 'No diagnostic'))
            }
           
            print(f"[DB ERROR] PostgreSQL Error Details: {error_info}")
            print(f"[DB ERROR] Full exception: {traceback.format_exc()}")
           
            # Return specific error for debugging (you may want to make this generic in production)
            return jsonify({
                "success": False,
                "error": f"Database error [{error_info['pgcode']}]: {str(db_err)[:100]}"
            }), 500
           
        except Exception as e:
            print(f"[DB ERROR] Unexpected database error: {e}")
            print(f"[DB ERROR] Traceback: {traceback.format_exc()}")
            return jsonify({"success": False, "error": f"Database error: {str(e)[:100]}"}), 500

        # Query staff email for notification
        try:
            staff_cursor = g.staff_db.cursor(cursor_factory=RealDictCursor)
            staff_cursor.execute("SELECT email FROM staff WHERE ward_id = %s LIMIT 1", (ward_id,))
            worker = staff_cursor.fetchone()
            staff_cursor.close()

            if not worker:
                print(f"[WARN] No worker assigned to ward_id {ward_id}")
                return jsonify({
                    "success": True,
                    "message": "Submission successful, but no worker assigned to this ward"
                })

            # Send email notification
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
            print(f"[DEBUG] Email notification sent to: {worker['email']}")
            return jsonify({"success": True, "message": "Submission successful and notification sent"})
           
        except Exception as email_err:
            print(f"[ERROR] Email sending failed: {email_err}")
            return jsonify({
                "success": True,
                "message": "Submission successful, but notification email failed"
            })

    except Exception as e:
        print(f"[CRITICAL ERROR] Unhandled exception in submit_user: {e}")
        print(f"[CRITICAL ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)[:100]}"
        }), 500