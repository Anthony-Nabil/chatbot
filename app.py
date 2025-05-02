import re
import json
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

TEAM_MEMBERS = [
    {"name": "Anthony Nabil Farag Boutros", "id": "20210065"},
    {"name": "Laila Abdel Nasser Ahmed", "id": "20210380"},
    {"name": "Mahmoud Saad Noman", "id": "20210263"},
    {"name": "Mohamed Khaled Abdallah", "id": "20212489"},
    {"name": "Omar Salah Mohamed", "id": "20210336"},
    {"name": "Youssef Mohamed Ahmed", "id": "20210154"},
]

chat_history = []

unit_synonyms = {
    "meter": "m",
    "meters": "m",
    "kilometer": "km",
    "kilometers": "km",
    "cm": "cm",
    "mile": "mi",
    "miles": "mi",
    "foot": "ft",
    "feet": "ft",
    "inch": "in",
    "inches": "in",
    "kilogram": "kg",
    "kilograms": "kg",
    "gram": "g",
    "grams": "g",
    "pound": "lb",
    "pounds": "lb",
    "celsius": "C",
    "centigrade": "C",
    "fahrenheit": "F",
    "kelvin": "K",
}


conversion_factors = {
    # Length (m based)
    ("m", "km"): lambda x: x / 1000.0,
    ("km", "m"): lambda x: x * 1000.0,
    ("m", "mi"): lambda x: x / 1609.34,
    ("mi", "m"): lambda x: x * 1609.34,
    ("m", "ft"): lambda x: x * 3.28084,
    ("ft", "m"): lambda x: x / 3.28084,
    ("m", "in"): lambda x: x * 39.3701,
    ("in", "m"): lambda x: x / 39.3701,
    ("ft", "in"): lambda x: x * 12.0,
    ("in", "ft"): lambda x: x / 12.0,
    # Weight (kg based)
    ("kg", "g"): lambda x: x * 1000.0,
    ("g", "kg"): lambda x: x / 1000.0,
    ("kg", "lb"): lambda x: x * 2.20462,
    ("lb", "kg"): lambda x: x / 2.20462,
    # Temperature (specific formulas)
    ("C", "F"): lambda x: (x * 9 / 5) + 32,
    ("F", "C"): lambda x: (x - 32) * 5 / 9,
    ("C", "K"): lambda x: x + 273.15,
    ("K", "C"): lambda x: x - 273.15,
    ("F", "K"): lambda x: (x - 32) * 5 / 9 + 273.15,
    ("K", "F"): lambda x: (x - 273.15) * 9 / 5 + 32,
}

# weather API codes
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Slight showers",
    81: "Showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm + hail",
    99: "Thunderstorm + heavy hail",
}


def convert_units(value_str, unit_from, unit_to):
    """Performs unit conversion based on defined factors."""
    try:
        val = float(value_str)
    except ValueError:
        return "Error: Invalid number."

    norm_from = unit_synonyms.get(unit_from.lower(), unit_from.lower())
    norm_to = unit_synonyms.get(unit_to.lower(), unit_to.lower())

    if norm_from == norm_to:
        return f"{value_str} {norm_from} is {value_str} {norm_to}."

    conversion_func = conversion_factors.get((norm_from, norm_to))

    if conversion_func:
        result = conversion_func(val)
        return f"{value_str} {norm_from} is {result:.2f} {norm_to}."


def get_weather(city_name):
    """Gets weather using Open-Meteo (Geocoding + Forecast)."""
    try:
        geo_params = {"name": city_name, "count": 1, "format": "json"}
        geo_res = requests.get(GEOCODING_URL, params=geo_params, timeout=5)
        geo_res.raise_for_status()
        geo_data = geo_res.json()

        if not geo_data.get("results"):
            return f"Sorry, couldn't find the location '{city_name}'."

        location = geo_data["results"][0]
        lat, lon = location["latitude"], location["longitude"]

        display_name = location.get("name", city_name) + (
            f", {location['country_code']}" if "country_code" in location else ""
        )

        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "temperature_unit": "celsius",
            "timezone": "auto",
        }
        weather_res = requests.get(FORECAST_URL, params=weather_params, timeout=5)
        weather_res.raise_for_status()
        weather_data = weather_res.json()

        current = weather_data.get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code")

        if temp is None or code is None:
            return "Sorry, received incomplete weather data."

        condition = WMO_CODES.get(code, f"Code {code}")
        temp_unit = weather_data.get("current_units", {}).get("temperature_2m", "°C")

        return f"Weather in {display_name}: {condition}, {temp}{temp_unit}."

    except requests.exceptions.Timeout:
        return "Sorry, the weather service timed out."
    except requests.exceptions.RequestException as e:
        print(f"Weather API Error: {e}")
        return "Sorry, couldn't connect to the weather service."
    except Exception as e:
        print(f"General Weather Error: {e}")
        return "Sorry, an error occurred fetching weather."


def get_bot_response(user_message):
    """Main function to process user input and return bot response."""
    msg = user_message.lower().strip()

    # greatings and farewells
    if msg in ("hi", "hello", "hey"):
        return "Hello! Ask me to convert units ('10 kg to lbs'), get weather ('weather in paris'), or ask 'who made this?'."
    if msg in ("bye", "goodbye", "exit", "quit"):
        return "Goodbye!"
    if msg == "help":
        return "Examples:\n- 'convert 10 miles to km'\n- '50 f to c'\n- 'weather in london'\n- 'who made you?'"

    # team members rule
    if re.search(r"\b(who made|creator|team|member|developer)\b", msg):
        response = ["Created by:"]
        if TEAM_MEMBERS:
            response.extend(f"- {m['name']} ({m['id']})" for m in TEAM_MEMBERS)

        return "\n".join(response)

    # weather rules
    match = re.match(r"(?:what's|how's)?\s*weather\s*(?:in|for)\s+(.+)\??$", msg)
    if match:
        city = match.group(1).strip()
        return get_weather(city)

    # conversion rules
    match = re.match(
        r"(?:convert)?\s*(\d+\.?\d*)\s*([a-z]+)\s*(?:to|in)\s*([a-z]+)\s*$", msg
    )
    if match:
        value, unit1, unit2 = match.groups()
        return convert_units(value, unit1, unit2)

    return "Sorry, I didn't understand. Try 'help'."


@app.route("/")
def home():
    """Render the chat page."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat messages."""
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"response": "Error: Empty message."}), 400

    chat_history.append({"sender": "User", "message": user_message})
    bot_response = get_bot_response(user_message)
    chat_history.append({"sender": "Bot", "message": bot_response})

    return jsonify({"response": bot_response})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
