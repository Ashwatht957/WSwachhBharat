import json
from shapely.geometry import shape, Point

def load_geojson():
    try:
        with open("wards_rounded.geojson", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Error: GeoJSON file not found.")
    except json.JSONDecodeError:
        print("Error: Invalid GeoJSON format.")
    return None

def get_ward_from_coordinates(latitude, longitude):
    geojson_data = load_geojson()
    if not geojson_data:
        return None

    point = Point(longitude, latitude)

    for feature in geojson_data.get("features", []):
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            props = feature["properties"]
            return {
                "ward_id": props.get("ward_id"),
                "ward_name": props.get("ward_name")
            }

    return None

def is_valid_coordinate(lat, lon):
    return -90 <= lat <= 90 and -180 <= lon <= 180
