from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
from geopy.distance import geodesic  # To calculate distance
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# Your VALUE SERP API Key
API_KEY = 'A35866157B3C45C2A51ADC67956FD8E7'

CITIES_OBEROSTERREICH = [
    {"name": "Linz", "lat": 48.3069, "long": 14.2858},
    {"name": "Wels", "lat": 48.1575, "long": 14.0272},
    {"name": "Steyr", "lat": 48.0427, "long": 14.4213},
    {"name": "Leonding", "lat": 48.2545, "long": 14.2421},
    {"name": "Traun", "lat": 48.2165, "long": 14.2347}
]

class UserClassifier:
    def __init__(self, browser, language, device, location):
        self.browser = browser.lower()
        self.language = language.lower()
        self.device = device.lower()
        self.location = location

    def classify_age(self):
        modern_browsers = ["chrome", "opera gx", "safari"]
        boomer_browsers = ["internet explorer", "safari", "edge"]

        is_modern_browser = any(browser in self.browser for browser in modern_browsers)
        is_phone = "phone" in self.device or "mobile" in self.device
        is_up_to_date = int(self.browser.split()[-1]) >= 100

        young_count = sum([is_modern_browser, is_phone, is_up_to_date])
        return "Young" if young_count >= 2 else "Old"

    def classify_wealth(self):
        rich_countries = ["us", "de", "jp", "ch"]
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
        'q': 'hotels',
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
        classifier = UserClassifier(
            browser=data["browser"],
            language=data["language"],
            device=data["device"],
            location=data["location"]
        )
        classification_result = classifier.classify()

        # Perform a hotel search using the user's location
        hotel_results = search_nearby_hotels(data["location"], language='de', device='desktop')

        # Find the nearest large city in Oberösterreich
        nearest_city_result = find_nearest_city(data["location"])

        # Combine classification result with hotel search results
        result = {
            "classification": classification_result,
            "hotels": hotel_results,
            "nearest_city": nearest_city_result
        }
        return jsonify(result), 200
    except KeyError as e:
        return jsonify({"error": f"Missing key: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
