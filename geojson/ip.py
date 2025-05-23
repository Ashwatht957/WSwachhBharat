import geopandas as gpd
from shapely.geometry import shape, Polygon
import fiona

valid_features = []
with fiona.open("RB.geojson") as src:
    for feature in src:
        try:
            geom = shape(feature["geometry"])
            if geom.is_valid and not geom.is_empty and isinstance(geom, Polygon) and len(geom.exterior.coords) >= 3:
                feature["geometry"] = geom
                valid_features.append({
                    **feature["properties"],
                    "geometry": geom
                })
        except:
            continue

# Create GeoDataFrame
import pandas as pd
gdf = gpd.GeoDataFrame(
    [f for f in valid_features],
    geometry=[f["geometry"] for f in valid_features],
    crs=src.crs
)

gdf.to_file("cleaned_wards.geojson", driver="GeoJSON")
