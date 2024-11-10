from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
from geopy.distance import geodesic  # To calculate distance
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re
from statistics import mean

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Your VALUE SERP API Key
API_KEY = 'A35866157B3C45C2A51ADC67956FD8E7'

CITIES_OBEROSTERREICH = [
    {"name": "Linz", "lat": 48.3069, "long": 14.2858}
]

def get_nearest_town(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse"

    headers = {
        'User-Agent': 'AustrianTourismHackathonThingieThing/1.0 (tdvorak227@gmail.com)',
        'Referer': 'https://is.muni.cz'
    }

    # Set up the parameters for the reverse geocoding request
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'zoom': 10  # Zoom level 10 returns towns, cities, and localities
    }

    # Send the request to the Nominatim API
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()

        # Get the town or city name from the response
        town = data['name']

        # If the response includes town/city data, return it; otherwise, show an error
        if town:
            return town
        else:
            return "Town or city not found"
    else:
        return f"Error: {response.status_code}"



def google_search(start_location, end_location, vehicle):
    query = f"{end_location} {start_location} {vehicle}"

    # Define the endpoint and parameters for ValueSERP API
    url = 'https://api.valueserp.com/search'
    params = {
        'api_key': API_KEY,
        'q': query,
        'location': end_location,  # Change if necessary
        'hl': 'de',
        'gl': 'at',
    }

    # Send the GET request to ValueSERP API
    response = requests.get(url, params=params)
    # return link, text
    return response


class UserClassifier:
    def __init__(self, browser, language, device, location, referrer):
        self.browser = browser.lower()
        self.language = language.lower()
        self.device = device.lower()
        self.location = location
        self.referrer = referrer

    def classify_age(self):
        modern_browsers = ["chrome", "opera gx", "safari"]
        boomer_browsers = ["internet explorer", "safari", "edge"]

        boomer_referrers = ["facebook", "yahoo", "msn",
                            "nextdoor", "weather", "linkedin", "huffpost", "foxnews", "cnn", "quora", "yelp"]

        is_modern_browser = any(browser in self.browser for browser in modern_browsers)
        is_phone = "phone" in self.device or "mobile" in self.device
        is_up_to_date = int(self.browser.split()[-1]) >= 100
        contains_boomer = int(any(ref in self.referrer for ref in boomer_referrers))

        young_count = sum([is_modern_browser, is_phone, is_up_to_date]) - contains_boomer
        return "Young" if young_count >= 2 else "Old"

    def classify_wealth(self):
        rich_countries = ["at", "be", "ch", "de", "fr", "ie", "li", "lu", "mc", "nl", "en-gb"]

        country_code = self.language
        is_rich_country = country_code in rich_countries

        is_apple_device = "apple" in self.device
        is_old = self.classify_age() == "Old"

        rich_count = sum([is_rich_country, is_apple_device, is_old])
        return "Rich" if rich_count >= 2 else "Poor"

    def classify(self):
        age = self.classify_age()
        wealth = self.classify_wealth()
        return {"Age": age, "Capital": wealth}


def find_nearest_city(location):
    user_coords = (location["lat"], location["long"])
    closest_city = None
    min_distance = float("inf")

    for city in CITIES_OBEROSTERREICH:
        city_coords = (city["lat"], city["long"])
        distance = geodesic(user_coords, city_coords).kilometers
        if distance < min_distance:
            min_distance = distance
            closest_city = city["name"]

    return {"nearest_city": closest_city, "distance_km": round(min_distance, 2)}

def search_nearby_hotels(location, language='de', device='desktop'):
    # Define the endpoint and parameters for the VALUE SERP API
    url = 'https://api.valueserp.com/search'
    params = {
        'api_key': API_KEY,
        'q': f'hotels Linz',
        'location': f"lat:{location['lat']},lon:{location['long']},zoom:15",
        'hl': language,
        'device': 'desktop',
        'tbm': 'lcl',  # 'lcl' for local search
        'search_type': 'places'
    }

    # Send the GET request to VALUE SERP API
    response = requests.get(url, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        hotels = response.json()
        return hotels
    else:
        return {"error": f"Unable to retrieve hotels: {response.status_code}, {response.text}"}


@app.route('/classify', methods=['POST'])
def classify_user():
    try:
        data = request.get_json()

        referrer = data.get("referrer", "")

        classifier = UserClassifier(
            browser=data["browser"],
            language=data["language"],
            device=data["device"],
            location=data["location"],
            referrer=referrer
        )
        classification_result = classifier.classify()

        # Perform a hotel search using the user's location
        hotel_results = search_nearby_hotels(data["location"], language='de', device='desktop')

        # Find the nearest large city in Oberösterreich
        nearest_city_result = find_nearest_city(data["location"])

        # Do travel data bullshit fuck my life
        travel_info = {}

        start_location = get_nearest_town(data["location"]['lat'], data["location"]['long'])
        for vehicle in ['bus', 'train', 'plane']:
            oof = google_search(start_location, nearest_city_result['nearest_city'], vehicle)

            # Check if any item matches the "omio" domain, otherwise set to None
            omio_items = [item for item in oof.json()['organic_results'] if "omio" in item['domain']]
            if omio_items:
                omio_item = omio_items[0]
                link = omio_item['link']
                preis_info = omio_item['rich_snippet']['top']['detected_extensions']['price']
                nums = [int(word) for word in omio_item['snippet'].split() if word.isdigit()]
                fahrzeit_info = nums[:2]
            else:
                link, fahrzeit_info, preis_info = None, None, None

            travel_info[vehicle] = {
                "Fahrzeit": fahrzeit_info,
                "Preis": preis_info,
                "Link": link,
            }
            # Combine classification result with hotel search results
        result = {
            "classification": classification_result,
            "hotels": hotel_results['places_results'][:3],
            "nearest_city": start_location,
            "travel_data": travel_info
        }
        return jsonify(result), 200
    except KeyError as e:
        return jsonify({"error": f"Missing key: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
