from flask import Flask, render_template, request, jsonify
import requests
import folium
import pandas as pd
import matplotlib.pyplot as plt
import json
from io import BytesIO
import base64
from folium.plugins import HeatMap
from folium import Map, TileLayer
import branca
import branca.colormap as cm
from tabulate import tabulate
import plotly.express as px
import os
import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from the .env file
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-flash')

# STAC and RASTER API endpoints
STAC_API_URL = "https://earth.gov/ghgcenter/api/stac/"
RASTER_API_URL = "https://earth.gov/ghgcenter/api/raster/"

# Initialize Flask app
app = Flask(__name__, template_folder='templates')

# Helper function to get item count from STAC API
def get_item_count(collection_id):
    count = 0
    items_url = f"{STAC_API_URL}/collections/{collection_id}/items"
    while True:
        response = requests.get(items_url)
        if not response.ok:
            print("Error getting items")
            return 0
        stac = response.json()
        count += int(stac["context"].get("returned", 0))
        next_link = next((link for link in stac["links"] if link["rel"] == "next"), None)
        if not next_link:
            break
        items_url = next_link["href"]
    return count

# --- Global Ocean Carbon Absorption ---

# Collection name
collection_name_co2_absorption = "eccodarwin-co2flux-monthgrid-v5"

# Asset name
asset_name_co2_absorption = "co2"

# Rescale values for visualization
rescale_values_co2_absorption = {"max": 0.0007, "min": -0.0007}

# Colormap for visualization
color_map_co2_absorption = "magma"

# California AOI polygon
california_coast_aoi = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "coordinates": [
            [
                [-124.19, 37.86],
                [-123.11, 37.86],
                [-119.96, 33.16],
                [-121.13, 33.16],
                [-124.19, 37.86]
            ]
        ],
        "type": "Polygon",
    },
}

# Function to generate statistics for an item and AOI (CO2 Absorption)
def generate_stats_co2_absorption(item, geojson):
    result = requests.post(
        f"{RASTER_API_URL}/cog/statistics",
        params={"url": item["assets"][asset_name_co2_absorption]["href"]},
        json=geojson,
    ).json()
    return {
        **result["properties"],
        "datetime": item["properties"]["start_datetime"],
    }

# Load world country data
world_country_data = pd.read_csv("world_country.csv")

# Flask route for the CO2 Absorption page
@app.route('/co2_absorption_air_sea', methods=['GET', 'POST'])
def co2_absorption_view():
    # Get items from STAC API (CO2 Absorption)
    number_of_items_co2_absorption = get_item_count(collection_name_co2_absorption)
    items_response_co2_absorption = requests.get(f"{STAC_API_URL}/collections/{collection_name_co2_absorption}/items?limit={number_of_items_co2_absorption}")
    items_co2_absorption = items_response_co2_absorption.json()["features"]
    items_co2_absorption = {item["properties"]["start_datetime"]: item for item in items_co2_absorption}

    # Generate statistics for all items (CO2 Absorption)
    stats_co2_absorption = {}
    for item in items_co2_absorption.values():
        date = item["properties"]["start_datetime"]
        year_month = date[:7].replace('-', '')
        stats_co2_absorption[year_month] = generate_stats_co2_absorption(item, california_coast_aoi)

    # Function to clean statistics data (CO2 Absorption)
    def clean_stats_co2_absorption(stats_json):
        pd.set_option('display.float_format', '{:.20f}'.format)
        stats_json_ = [stats_json[datetime] for datetime in stats_json]
        df = pd.json_normalize(stats_json_)
        df.columns = [col.replace("statistics.b1.", "") for col in df.columns]
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    # Clean statistics data (CO2 Absorption)
    df_co2_absorption = clean_stats_co2_absorption(stats_co2_absorption)

    # Default Country: Bangladesh
    country_name = "Bangladesh" 
    latitude = 23.6850  # Default latitude (Bangladesh)
    longitude = 90.3563  # Default longitude (Bangladesh)
    zoom_start = 5.5

    if request.method == 'POST':
        country_name = request.form.get("country")
        if country_name:
            country_data = world_country_data[world_country_data["country"] == country_name]
            if not country_data.empty:
                latitude = country_data["latitude"].iloc[0]
                longitude = country_data["longitude"].iloc[0]
            else:
                return render_template("co2_absorption_air_sea.html", error_message="Country not found in database.", country=country_name)

    # Create the map
    aoi_map_bbox = folium.Map(
        location=[latitude, longitude],
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )

    # Get tile information for April 2021 (default)
    default_date_key = list(items_co2_absorption.keys())[20]
    default_tile_co2_absorption = requests.get(
        f"{RASTER_API_URL}/collections/{items_co2_absorption[default_date_key]['collection']}/items/{items_co2_absorption[default_date_key]['id']}/tilejson.json?"
        f"&assets={asset_name_co2_absorption}"
        f"&color_formula=gamma+r+1.05&colormap_name={color_map_co2_absorption}"
        f"&rescale={rescale_values_co2_absorption['min']},{rescale_values_co2_absorption['max']}"
    ).json()

    # Add the CO2 flux layer
    folium.TileLayer(
        tiles=default_tile_co2_absorption["tiles"][0],
        attr="GHG",
        opacity=0.7
    ).add_to(aoi_map_bbox)

    # Prepare graph data 
    graph_data_co2_absorption = df_co2_absorption.copy()
    graph_data_co2_absorption['datetime'] = graph_data_co2_absorption['datetime'].dt.strftime('%Y-%m-%d')
    graph_data_co2_absorption = graph_data_co2_absorption[['datetime', 'max']].to_dict(orient='records')

    # Save graph_data to JSON file
    with open("co2_absorption_air_sea.json", "w") as f:
        json.dump(graph_data_co2_absorption, f)

    # Pass graph data and country options to the template
    country_options = [{'value': country, 'label': country} 
                      for country in world_country_data["country"].unique()]
    return render_template('co2_absorption_air_sea.html', 
                           map_html=aoi_map_bbox._repr_html_(), 
                           graph_data=graph_data_co2_absorption, 
                           default_tile=default_tile_co2_absorption,
                           latitude=latitude, 
                           longitude=longitude, 
                           country=country_name,
                           country_options=country_options)

# --- Global Annual CO₂ Emissions ---

# Collection name
collection_name_co2_emissions_mip = "oco2-mip-co2budget-yeargrid-v1"

# Asset name
asset_name_co2_emissions_mip = "ff"  # fossil fuel

# Rescale values for visualization
rescale_values_co2_emissions_mip = {"max": 450, "min": 0}

# Colormap for visualization
color_map_co2_emissions_mip = "purd"

# Texas AOI polygon
texas_aoi = {
    "type": "Feature",
    "properties": {},
    "geometry": {
        "coordinates": [
            [
                [-95, 29],
                [-95, 33],
                [-104, 33],
                [-104, 29],
                [-95, 29]
            ]
        ],
        "type": "Polygon",
    },
}

# Function to generate statistics for an item and AOI (CO2 Emissions MIP)
def generate_stats_co2_emissions_mip(item, geojson):
    result = requests.post(
        f"{RASTER_API_URL}/cog/statistics",
        params={"url": item["assets"][asset_name_co2_emissions_mip]["href"]},
        json=geojson,
    ).json()
    return {
        **result["properties"],
        "datetime": item["properties"]["start_datetime"],
    }

# Flask route for the CO2 Emissions MIP page
@app.route('/co2_emissions_mip', methods=['GET', 'POST'])
def co2_emissions_mip_view():
    # Get items from STAC API (CO2 Emissions MIP)
    number_of_items_co2_emissions_mip = get_item_count(collection_name_co2_emissions_mip)
    items_response_co2_emissions_mip = requests.get(f"{STAC_API_URL}/collections/{collection_name_co2_emissions_mip}/items?limit={number_of_items_co2_emissions_mip}")
    items_co2_emissions_mip = items_response_co2_emissions_mip.json()["features"]
    items_co2_emissions_mip = {item["properties"]["start_datetime"]: item for item in items_co2_emissions_mip}

    # Generate statistics for all items (CO2 Emissions MIP)
    stats_co2_emissions_mip = [generate_stats_co2_emissions_mip(item, texas_aoi) for item in items_co2_emissions_mip.values()]

    # Function to clean statistics data (CO2 Emissions MIP)
    def clean_stats_co2_emissions_mip(stats_json) -> pd.DataFrame:
        df = pd.json_normalize(stats_json)
        df.columns = [col.replace("statistics.b1.", "") for col in df.columns]
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    # Clean statistics data (CO2 Emissions MIP)
    df_co2_emissions_mip = clean_stats_co2_emissions_mip(stats_co2_emissions_mip)

    # Default Country: Bangladesh
    country_name = "Bangladesh" 
    latitude = 23.6850  # Default latitude (Bangladesh)
    longitude = 90.3563  # Default longitude (Bangladesh)
    zoom_start = 6.8

    # Create the map 
    aoi_map_bbox = folium.Map(
        location=[latitude, longitude],
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )

    # Get tile information for a specific item 
    co2_flux_3 = requests.get(
        f"{RASTER_API_URL}/collections/{items_co2_emissions_mip[list(items_co2_emissions_mip.keys())[2]]['collection']}/items/{items_co2_emissions_mip[list(items_co2_emissions_mip.keys())[2]]['id']}/tilejson.json?"
        f"&assets={asset_name_co2_emissions_mip}"
        f"&color_formula=gamma+r+1.05&colormap_name={color_map_co2_emissions_mip}"
        f"&rescale={rescale_values_co2_emissions_mip['min']},{rescale_values_co2_emissions_mip['max']}"
    ).json()

    # Add the CO2 flux layer (Initially)
    folium.TileLayer(
        tiles=co2_flux_3["tiles"][0],
        attr="GHG",
        opacity=0.7
    ).add_to(aoi_map_bbox)

    if request.method == 'POST':
        # Get latitude and longitude from user input
        country_name = request.form.get("country")
        if country_name:
            country_data = world_country_data[world_country_data["country"] == country_name]
            if not country_data.empty:
                latitude = country_data["latitude"].iloc[0]
                longitude = country_data["longitude"].iloc[0]
                aoi_map_bbox.location = [latitude, longitude]  # Update map center

            # Update the CO2 flux layer
            # Remove any existing TileLayer
            for layer in aoi_map_bbox._children:  # Access layers correctly
                if isinstance(layer, folium.TileLayer):
                    aoi_map_bbox.remove(layer)
            # Add the new TileLayer
            folium.TileLayer(
                tiles=co2_flux_3["tiles"][0],
                attr="GHG",
                opacity=0.7
            ).add_to(aoi_map_bbox)

    # Generate HTML for the map
    map_html = aoi_map_bbox._repr_html_()

    # Prepare graph data and convert Timestamps to strings for JSON serialization
    graph_data_co2_emissions_mip = df_co2_emissions_mip.copy()
    graph_data_co2_emissions_mip['datetime'] = graph_data_co2_emissions_mip['datetime'].dt.strftime('%Y-%m-%d')
    graph_data_co2_emissions_mip = graph_data_co2_emissions_mip[['datetime', 'max']].to_dict(orient='records')

    # Save graph_data to JSON file
    with open("co2_emissions_mip.json", "w") as f:
        json.dump(graph_data_co2_emissions_mip, f)

    # Pass graph data and country options to the template
    country_options = [{'value': country, 'label': country} 
                      for country in world_country_data["country"].unique()]
    return render_template('co2_emissions_mip.html', 
                           map_html=map_html, 
                           graph_data=graph_data_co2_emissions_mip, 
                           latitude=latitude, 
                           longitude=longitude, 
                           country=country_name,
                           country_options=country_options)


# --- Global CO₂ Emissions ---

# Collection name
collection_name_co2_emissions_odiac = "odiac-ffco2-monthgrid-v2023"

# Asset name
asset_name_co2_emissions_odiac = "co2-emissions"

# Rescale values for visualization
rescale_values_co2_emissions_odiac = {"max": 0.0007, "min": -0.0007} 

# Colormap for visualization
color_map_co2_emissions_odiac = "rainbow"

# Function to generate statistics for an item and AOI (CO2 Emissions Odiac)
def generate_stats_co2_emissions_odiac(item, geojson):
    result = requests.post(
        f"{RASTER_API_URL}/cog/statistics",
        params={"url": item["assets"][asset_name_co2_emissions_odiac]["href"]},
        json=geojson,
    ).json()
    return {
        **result["properties"],
        "datetime": item["properties"]["start_datetime"][:7],
    }

# Flask route for the CO2 Emissions Odiac page
@app.route('/co2_emissions_odiac', methods=['GET', 'POST'])
def co2_emissions_odiac_view():
    # Get items from STAC API (CO2 Emissions Odiac)
    number_of_items_co2_emissions_odiac = get_item_count(collection_name_co2_emissions_odiac)
    items_response_co2_emissions_odiac = requests.get(f"{STAC_API_URL}/collections/{collection_name_co2_emissions_odiac}/items?limit={number_of_items_co2_emissions_odiac}")
    items_co2_emissions_odiac = items_response_co2_emissions_odiac.json()["features"]
    items_co2_emissions_odiac = {item["properties"]["start_datetime"][:7]: item for item in items_co2_emissions_odiac}

    # Generate statistics for all items (CO2 Emissions Odiac)
    stats_co2_emissions_odiac = {}
    for item in items_co2_emissions_odiac.values():
        date = item["properties"]["start_datetime"]
        year_month = date[:7].replace('-', '')
        stats_co2_emissions_odiac[year_month] = generate_stats_co2_emissions_odiac(item, texas_aoi)

    # Function to clean statistics data (CO2 Emissions Odiac)
    def clean_stats_co2_emissions_odiac(stats_json):
        pd.set_option('display.float_format', '{:.20f}'.format)
        stats_json_ = [stats_json[datetime] for datetime in stats_json]
        df = pd.json_normalize(stats_json_)
        df.columns = [col.replace("statistics.b1.", "") for col in df.columns]
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    # Clean statistics data (CO2 Emissions Odiac)
    df_co2_emissions_odiac = clean_stats_co2_emissions_odiac(stats_co2_emissions_odiac)

    # Default values for Bangladesh
    latitude = 23.6850 
    longitude = 90.3563
    zoom_start = 5.5
    country_name = "Bangladesh"  

    if request.method == 'POST':
        country_name = request.form.get("country")
        if country_name:
            # Search for country data in CSV
            country_data = world_country_data[world_country_data["country"] == country_name]
            if not country_data.empty:
                latitude = country_data["latitude"].iloc[0]
                longitude = country_data["longitude"].iloc[0]
            else:
                return render_template("co2_emissions_odiac.html", error_message="Country not found in database.", country=country_name)

    # Create the map
    aoi_map_bbox = folium.Map(
        location=[latitude, longitude],
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )

    # Get tile information for April 2021 (default)
    default_date_key = list(items_co2_emissions_odiac.keys())[20]
    default_tile_co2_emissions_odiac = requests.get(
        f"{RASTER_API_URL}/collections/{items_co2_emissions_odiac[default_date_key]['collection']}/items/{items_co2_emissions_odiac[default_date_key]['id']}/tilejson.json?"
        f"&assets={asset_name_co2_emissions_odiac}"
        f"&color_formula=gamma+r+1.05&colormap_name={color_map_co2_emissions_odiac}"
        f"&rescale={rescale_values_co2_emissions_odiac['min']},{rescale_values_co2_emissions_odiac['max']}"
    ).json()

    # Add the CO2 flux layer
    folium.TileLayer(
        tiles=default_tile_co2_emissions_odiac["tiles"][0],
        attr="GHG",
        opacity=0.7
    ).add_to(aoi_map_bbox)

    # Prepare graph data 
    graph_data_co2_emissions_odiac = df_co2_emissions_odiac.copy()
    graph_data_co2_emissions_odiac['datetime'] = graph_data_co2_emissions_odiac['datetime'].dt.strftime('%Y-%m-%d')
    graph_data_co2_emissions_odiac = graph_data_co2_emissions_odiac[['datetime', 'max']].to_dict(orient='records')

    # Save graph_data to JSON file
    with open("co2_emissions_odiac.json", "w") as f:
        json.dump(graph_data_co2_emissions_odiac, f)

    # Pass graph data and country options to the template
    country_options = [{'value': country, 'label': country} 
                      for country in world_country_data["country"].unique()]
    return render_template('co2_emissions_odiac.html', 
                           map_html=aoi_map_bbox._repr_html_(), 
                           graph_data=graph_data_co2_emissions_odiac, 
                           default_tile=default_tile_co2_emissions_odiac,
                           latitude=latitude, 
                           longitude=longitude, 
                           country=country_name,
                           country_options=country_options)

# --- Global Methane Emissions ---

# Collection name
collection_name_methane_emissions = "tm54dvar-ch4flux-monthgrid-v1"

# Asset name
asset_name_methane_emissions = "fossil"  # fossil fuel

# Rescale values for visualization
rescale_values_methane_emissions = {"max": 450, "min": 0}

# Colormap for visualization
color_map_methane_emissions = "purd"

# Flask route for the Methane Emissions page
@app.route('/methane_emissions_tm5', methods=['GET', 'POST'])
def methane_emissions_view():
    # Get items from STAC API (Methane Emissions)
    number_of_items_methane_emissions = get_item_count(collection_name_methane_emissions)
    items_response_methane_emissions = requests.get(f"{STAC_API_URL}/collections/{collection_name_methane_emissions}/items?limit={number_of_items_methane_emissions}")
    items_methane_emissions = items_response_methane_emissions.json()["features"]
    items_methane_emissions = {item["properties"]["start_datetime"]: item for item in items_methane_emissions}

    # Texas AOI polygon
    texas_aoi = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "coordinates": [
                [
                    [-95, 29],
                    [-95, 33],
                    [-104, 33],
                    [-104, 29],
                    [-95, 29]
                ]
            ],
            "type": "Polygon",
        },
    }

    # Function to generate statistics for an item and AOI
    def generate_stats(item, geojson):
        result = requests.post(
            f"{RASTER_API_URL}/cog/statistics",
            params={"url": item["assets"][asset_name_methane_emissions]["href"]},
            json=geojson,
        ).json()
        return {
            **result["properties"],
            "datetime": item["properties"]["start_datetime"],
        }

    # Generate statistics for all items (Methane Emissions)
    stats_methane_emissions = [generate_stats(item, texas_aoi) for item in items_methane_emissions.values()]

    # Function to clean statistics data (Methane Emissions)
    def clean_stats_methane_emissions(stats_json) -> pd.DataFrame:
        df = pd.json_normalize(stats_json)
        df.columns = [col.replace("statistics.b1.", "") for col in df.columns]
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    # Clean statistics data (Methane Emissions)
    df_methane_emissions = clean_stats_methane_emissions(stats_methane_emissions)

    # Default Country: Bangladesh
    country_name = "Bangladesh" 
    latitude = 23.6850  # Default latitude (Bangladesh)
    longitude = 90.3563  # Default longitude (Bangladesh)
    zoom_start = 6.8

    # Create the map 
    aoi_map_bbox = folium.Map(
        location=[latitude, longitude],
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )

    # Get tile information for a specific item 
    ch4_flux_3 = requests.get(
        f"{RASTER_API_URL}/collections/{items_methane_emissions[list(items_methane_emissions.keys())[2]]['collection']}/items/{items_methane_emissions[list(items_methane_emissions.keys())[2]]['id']}/tilejson.json?"
        f"&assets={asset_name_methane_emissions}"
        f"&color_formula=gamma+r+1.05&colormap_name={color_map_methane_emissions}"
        f"&rescale={rescale_values_methane_emissions['min']},{rescale_values_methane_emissions['max']}"
    ).json()

    # Add the CO2 flux layer (Initially)
    folium.TileLayer(
        tiles=ch4_flux_3["tiles"][0],
        attr="GHG",
        opacity=0.7
    ).add_to(aoi_map_bbox)

    if request.method == 'POST':
        # Get latitude and longitude from user input
        country_name = request.form.get("country")
        if country_name:
            country_data = world_country_data[world_country_data["country"] == country_name]
            if not country_data.empty:
                latitude = country_data["latitude"].iloc[0]
                longitude = country_data["longitude"].iloc[0]
                aoi_map_bbox.location = [latitude, longitude]  # Update map center

            # Update the CO2 flux layer
            # Remove any existing TileLayer
            for layer in aoi_map_bbox._children:  # Access layers correctly
                if isinstance(layer, folium.TileLayer):
                    aoi_map_bbox.remove(layer)
            # Add the new TileLayer
            folium.TileLayer(
                tiles=ch4_flux_3["tiles"][0],
                attr="GHG",
                opacity=0.7
            ).add_to(aoi_map_bbox)

    # Generate HTML for the map
    map_html = aoi_map_bbox._repr_html_()

    # Prepare graph data and convert Timestamps to strings for JSON serialization
    graph_data_methane_emissions = df_methane_emissions.copy()
    graph_data_methane_emissions['datetime'] = graph_data_methane_emissions['datetime'].dt.strftime('%Y-%m-%d')
    graph_data_methane_emissions = graph_data_methane_emissions[['datetime', 'max']].to_dict(orient='records')

    # Save graph_data to JSON file
    with open("methane_emissions_tm5.json", "w") as f:
        json.dump(graph_data_methane_emissions, f)

    # Pass graph data and country options to the template
    country_options = [{'value': country, 'label': country} 
                      for country in world_country_data["country"].unique()]
    return render_template('methane_emissions_tm5.html', 
                           map_html=map_html, 
                           graph_data=graph_data_methane_emissions, 
                           latitude=latitude, 
                           longitude=longitude, 
                           country=country_name,
                           country_options=country_options)


# --- Global Arid Regions High Methane Concentrations ---

# Collection name
collection_name_methane_concentrations = "emit-ch4plume-v1"

# Default item ID
default_item_id = "EMIT_L2B_CH4PLM_001_20230418T200118_000829"

# Flask route to render the map
@app.route("/methane_concentrations_emit", methods=["GET", "POST"])
def methane_concentrations_view():

    number_of_items = get_item_count(collection_name_methane_concentrations)
    items_response = requests.get(f"{STAC_API_URL}/collections/{collection_name_methane_concentrations}/items?limit={number_of_items}")
    if items_response.ok:
        items = items_response.json()["features"]
        plume_complexes = {item["id"]: item for item in items}
        # Sort items by date-time
        items_sorted = sorted(items, key=lambda x: x["properties"]["datetime"])
        # Create a dictionary of dates to corresponding item IDs
        date_to_item_ids = {item["properties"]["datetime"]: item["id"] for item in items_sorted}
    else:
        print("Error fetching items from STAC API")
        plume_complexes = {}
        date_to_item_ids = {}

    # Search by Item ID only
    search_value = request.form.get('item_id', default_item_id)  # Get search value (or default)

    # Fetch and render the map
    if search_value and search_value in plume_complexes:
        item_id = search_value  # Use the search value as the item ID
        # Asset name
        asset_name = "ch4-plume-emissions"

        # Get min/max values for rescaling
        try:
            rescale_values = {
                "max": plume_complexes[item_id]["assets"][asset_name]["raster:bands"][0]["histogram"]["max"],
                "min": plume_complexes[item_id]["assets"][asset_name]["raster:bands"][0]["histogram"]["min"],
            }
        except KeyError:
            print(f"Error: 'histogram' key not found in item {item_id}")
            rescale_values = {"max": 1, "min": 0}  # Default values

        # Fetch tile data
        methane_plume_tile_response = requests.get(
            f"{RASTER_API_URL}/collections/{plume_complexes[item_id]['collection']}/items/{plume_complexes[item_id]['id']}/tilejson.json"
            f"?assets={asset_name}"
            f"&color_formula=gamma+r+1.05"
            f"&colormap_name=magma"
            f"&rescale={rescale_values['min']},{rescale_values['max']}"
        )
        if methane_plume_tile_response.ok:
            methane_plume_tile = methane_plume_tile_response.json()

            # Create the map
            map_ = folium.Map(
                location=(methane_plume_tile["center"][1], methane_plume_tile["center"][0]),
                zoom_start=14,
                tiles=None,
                tooltip="test tool tip",
            )
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png",
                name="ESRI World Imagery",
                attr="Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
                overlay=True,
            ).add_to(map_)

            # Add the raster layer
            map_layer = TileLayer(
                tiles=methane_plume_tile["tiles"][0],
                name="Plume Complex Landfill",
                overlay=True,
                attr="GHG",
                opacity=1,
            )
            map_layer.add_to(map_)

            # Add colormap
            colormap = cm.LinearColormap(
                colors=[
                    "#310597",
                    "#4C02A1",
                    "#6600A7",
                    "#7E03A8",
                    "#9511A1",
                    "#AA2395",
                    "#BC3587",
                    "#CC4778",
                    "#DA5A6A",
                    "#E66C5C",
                    "#F0804E",
                    "#F89540",
                    "#FDAC33",
                    "#FDC527",
                    "#F8DF25",
                ],
                vmin=0,
                vmax=1500,
            )
            colormap.caption = "ppm-m"
            map_.add_child(colormap)

            # Add map controls
            folium.LayerControl(collapsed=False, position="bottomleft").add_to(map_)

            # Add styling for the legend
            svg_style = '<style>svg#legend {font-size: 14px; background-color: white;}</style>'
            map_.get_root().header.add_child(folium.Element(svg_style))

            # Get the information about the number of granules found in the collection
            number_of_items = get_item_count(collection_name_methane_concentrations)
            items = requests.get(f"{STAC_API_URL}/collections/{collection_name_methane_concentrations}/items?limit={number_of_items}").json()["features"]
            # Sort the items based on their date-time attribute
            items_sorted = sorted(items, key=lambda x: x["properties"]["datetime"])

            # Create an empty list
            table_data = []
            # Extract the ID and date-time information for each granule and add them to the list
            for item in items_sorted:
                table_data.append([item['id'], item['properties']['datetime']])

            # Define the table headers
            headers = ["Methane Emission Plume Estimates ID", "Date-Time"]

            # Create a Pandas DataFrame from the table data
            df = pd.DataFrame(table_data, columns=headers)
            df['Date-Time'] = pd.to_datetime(df['Date-Time'])  # Convert to datetime

            # Create the chart using Plotly Express
            fig = px.line(df, x='Date-Time', y='Methane Emission Plume Estimates ID', title='Methane Emission Plume Estimates over Time')

            # Convert the chart to HTML
            chart_html = fig.to_html(full_html=False)

            # Save graph_data to a file
            graph_data = {
                "table_data": [{"id": row[0], "datetime": str(row[1])} for row in table_data]
            }
            with open("methane_concentrations_emit.json", "w") as f:
                json.dump(graph_data, f)

            # Render the map as HTML
            return render_template(
                "map.html", map=map_.get_root().render(), item_id=item_id, plume_complexes=plume_complexes, 
                table_data=table_data, headers=headers, chart_html=chart_html
            )

        else:
            return f"Error fetching tile data for item ID: {item_id}"

    else:
        # Render the map template with the default item ID and an empty map
        return render_template(
            "map.html", map="", item_id=default_item_id, plume_complexes=plume_complexes, table_data=[], headers=[], chart_html=""
        )

# --- Prediction Code ---

# Set the chart output folder
chart_output_folder = "generated_charts"
if not os.path.exists(chart_output_folder):
    os.makedirs(chart_output_folder)

def load_data(filename):
    """Loads data from a JSON file."""
    with open(os.path.join("charts", filename), 'r') as f:
        return json.load(f)

def generate_chart(data, title, filename):
    """Generates a line chart and saves it to a file."""
    labels = [d["datetime"] for d in data]
    values = [d["max"] for d in data]

    fig, ax = plt.subplots()
    ax.plot(labels, values)
    ax.set_xlabel("Date")
    ax.set_ylabel("Emission Value")
    ax.set_title(title)
    plt.xticks(rotation=45)  # Rotate x-axis labels for better readability

    # Save chart to file
    chart_path = os.path.join(chart_output_folder, filename)
    plt.savefig(chart_path)
    plt.close(fig)

    # Convert chart to base64
    with open(chart_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string

def predict_emissions(data, gas_type, years_range):
    """Predicts future emissions using Gemini."""
    prompt = f"""
    I have data on {gas_type} emissions from {min(years_range)} to {max(years_range)}:

    {data}

    Predict the following, considering trends in the data:

    1. What could be the {gas_type} emission values for each year from {min(years_range)} to {max(years_range)}?
    2. What could be the average annual change in {gas_type} emissions during this period?
    3. What are the potential implications of these predicted emission levels?
    4. What are some recommendations for mitigating {gas_type} emissions based on these predictions?

    Please provide your answers in a clear and concise manner.
    """
    response = model.generate_content(prompt)
    return response.text

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if request.method == 'POST':
        start_year = int(request.form.get('start_year'))
        end_year = int(request.form.get('end_year'))

        co2_human_data = load_data('co2_human_data.json')
        co2_natural_data = load_data('co2_natural_data.json')
        ch4_data = load_data('ch4_data.json')

        co2_human_predictions = predict_emissions(co2_human_data, "CO2 (Human)", range(start_year, end_year + 1))
        co2_natural_predictions = predict_emissions(co2_natural_data, "CO2 (Natural)", range(start_year, end_year + 1))
        ch4_predictions = predict_emissions(ch4_data, "CH4", range(start_year, end_year + 1))

        # Generate line charts
        co2_human_chart = generate_chart(co2_human_data, "CO2 Emissions (Human)", "co2_human_chart.png")
        co2_natural_chart = generate_chart(co2_natural_data, "CO2 Emissions (Natural)", "co2_natural_chart.png")
        ch4_chart = generate_chart(ch4_data, "CH4 Emissions", "ch4_chart.png")

        return render_template('prediction_results.html', 
                               co2_human_chart=co2_human_chart,
                               co2_natural_chart=co2_natural_chart,
                               ch4_chart=ch4_chart,
                               co2_human_predictions=co2_human_predictions,
                               co2_natural_predictions=co2_natural_predictions,
                               ch4_predictions=ch4_predictions)

    return render_template('prediction.html')

# Flask route for the main page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
