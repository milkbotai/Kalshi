"""Fetch NWS grid coordinates for 10 target cities.

This script queries the weather.gov API to get grid coordinates
for each city and saves the complete configuration to cities.json.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict

import requests

# City coordinates (lat, lon)
CITIES = {
    "NYC": {
        "name": "New York City",
        "lat": 40.7128,
        "lon": -74.0060,
        "timezone": "America/New_York",
        "cluster": "NE",
        "settlement_station": "KNYC",
    },
    "CHI": {
        "name": "Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
        "timezone": "America/Chicago",
        "cluster": "Midwest",
        "settlement_station": "KORD",
    },
    "LAX": {
        "name": "Los Angeles",
        "lat": 34.0522,
        "lon": -118.2437,
        "timezone": "America/Los_Angeles",
        "cluster": "West",
        "settlement_station": "KLAX",
    },
    "MIA": {
        "name": "Miami",
        "lat": 25.7617,
        "lon": -80.1918,
        "timezone": "America/New_York",
        "cluster": "SE",
        "settlement_station": "KMIA",
    },
    "AUS": {
        "name": "Austin",
        "lat": 30.2672,
        "lon": -97.7431,
        "timezone": "America/Chicago",
        "cluster": "SE",
        "settlement_station": "KAUS",
    },
    "DEN": {
        "name": "Denver",
        "lat": 39.7392,
        "lon": -104.9903,
        "timezone": "America/Denver",
        "cluster": "Mountain",
        "settlement_station": "KDEN",
    },
    "PHL": {
        "name": "Philadelphia",
        "lat": 39.9526,
        "lon": -75.1652,
        "timezone": "America/New_York",
        "cluster": "NE",
        "settlement_station": "KPHL",
    },
    "BOS": {
        "name": "Boston",
        "lat": 42.3601,
        "lon": -71.0589,
        "timezone": "America/New_York",
        "cluster": "NE",
        "settlement_station": "KBOS",
    },
    "SEA": {
        "name": "Seattle",
        "lat": 47.6062,
        "lon": -122.3321,
        "timezone": "America/Los_Angeles",
        "cluster": "West",
        "settlement_station": "KSEA",
    },
    "SFO": {
        "name": "San Francisco",
        "lat": 37.7749,
        "lon": -122.4194,
        "timezone": "America/Los_Angeles",
        "cluster": "West",
        "settlement_station": "KSFO",
    },
}

USER_AGENT = "Milkbot/1.0 (contact@milkbot.ai)"


def fetch_nws_grid(lat: float, lon: float) -> Dict[str, Any]:
    """Fetch NWS grid coordinates for a location.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dictionary with office, gridX, gridY
        
    Raises:
        requests.RequestException: If API call fails
    """
    url = f"https://api.weather.gov/points/{lat},{lon}"
    headers = {"User-Agent": USER_AGENT}
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    properties = data["properties"]
    
    return {
        "nws_office": properties["gridId"],
        "nws_grid_x": properties["gridX"],
        "nws_grid_y": properties["gridY"],
        "forecast_url": properties["forecast"],
        "forecast_hourly_url": properties["forecastHourly"],
        "observation_stations_url": properties["observationStations"],
    }


def main() -> None:
    """Fetch NWS grid data for all cities and save to JSON."""
    print("Fetching NWS grid coordinates for 10 cities...")
    
    cities_data = {}
    
    for code, city_info in CITIES.items():
        print(f"\nFetching {code} ({city_info['name']})...")
        
        try:
            nws_data = fetch_nws_grid(city_info["lat"], city_info["lon"])
            
            cities_data[code] = {
                "code": code,
                "name": city_info["name"],
                "lat": city_info["lat"],
                "lon": city_info["lon"],
                "timezone": city_info["timezone"],
                "cluster": city_info["cluster"],
                "settlement_station": city_info["settlement_station"],
                **nws_data,
            }
            
            print(f"  ✓ Office: {nws_data['nws_office']}, "
                  f"Grid: ({nws_data['nws_grid_x']}, {nws_data['nws_grid_y']})")
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            # Use placeholder values if API fails
            cities_data[code] = {
                "code": code,
                "name": city_info["name"],
                "lat": city_info["lat"],
                "lon": city_info["lon"],
                "timezone": city_info["timezone"],
                "cluster": city_info["cluster"],
                "settlement_station": city_info["settlement_station"],
                "nws_office": "PLACEHOLDER",
                "nws_grid_x": 0,
                "nws_grid_y": 0,
                "forecast_url": "",
                "forecast_hourly_url": "",
                "observation_stations_url": "",
            }
    
    # Save to file
    output_dir = Path("data/cities")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "cities.json"
    with open(output_file, "w") as f:
        json.dump(cities_data, f, indent=2)
    
    print(f"\n✓ Saved city data to {output_file}")
    print(f"  Total cities: {len(cities_data)}")


if __name__ == "__main__":
    main()
