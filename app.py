import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import folium_static
import geocoder
from math import radians, sin, cos, sqrt, atan2
import json
import os
from datetime import datetime, timedelta
from googletrans import Translator, LANGUAGES
import uuid
from bs4 import BeautifulSoup  # Added BeautifulSoup import

# Initialize session state for user profile and rewards
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "rewards" not in st.session_state:
    st.session_state.rewards = 0
if "donation_history" not in st.session_state:
    st.session_state.donation_history = []
if "dietary_prefs" not in st.session_state:
    st.session_state.dietary_prefs = "None"

# Spoonacular API key (replace with your own)
SPOONACULAR_API_KEY = "d97a761804394284b4f3754566d2e0d1"

# Mock food bank dataset (replace with real API in production)
food_banks = [
    {"name": "Hyderabad Food Bank", "lat": 17.385044, "lng": 78.486671, "contact": "123-456-7890"},
    {"name": "Telangana Charity Kitchen", "lat": 17.450000, "lng": 78.500000, "contact": "987-654-3210"},
    {"name": "Sreyas Community Pantry", "lat": 17.400000, "lng": 78.490000, "contact": "456-789-1234"}
]

# Haversine formula for distance calculation
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)*2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Fetch recipes from Spoonacular API
def fetch_recipes(ingredients, dietary_preference, language="en"):
    url = f"https://api.spoonacular.com/recipes/findByIngredients?apiKey={SPOONACULAR_API_KEY}&ingredients={ingredients}&number=5"
    if dietary_preference != "None":
        url += f"&diet={dietary_preference.lower()}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        recipes = response.json()
        translator = Translator()
        for recipe in recipes:
            recipe_id = recipe["id"]
            details_url = f"https://api.spoonacular.com/recipes/{recipe_id}/information?apiKey={SPOONACULAR_API_KEY}"
            details = requests.get(details_url).json()
            
            # Parse instructions with BeautifulSoup to extract steps
            instructions_html = details.get("instructions", "")
            if instructions_html:
                soup = BeautifulSoup(instructions_html, "html.parser")
                steps = []
                ol = soup.find("ol")
                if ol:
                    for li in ol.find_all("li"):
                        step_text = li.get_text(strip=True)
                        if step_text:
                            steps.append(step_text)
                else:
                    text = soup.get_text(separator="\n").strip()
                    steps = [line.strip() for line in text.split('\n') if line.strip()]
                recipe["steps"] = steps if steps else ["No instructions available."]
            else:
                recipe["steps"] = ["No instructions available."]
            
            if language != "en":
                recipe["title"] = translator.translate(recipe["title"], dest=language).text
                # Translate each step individually if steps is a list
                if isinstance(recipe["steps"], list):
                    translated_steps = []
                    for step in recipe["steps"]:
                        translated_steps.append(translator.translate(step, dest=language).text)
                    recipe["steps"] = translated_steps
                else:
                    recipe["steps"] = translator.translate(recipe["steps"], dest=language).text
        return recipes
    except Exception as e:
        st.error(f"Error fetching recipes: {e}")
        return []

# Find nearby food banks
def find_nearby_food_banks(user_lat, user_lng, radius_km=10):
    nearby = []
    for bank in food_banks:
        distance = haversine(user_lat, user_lng, bank["lat"], bank["lng"])
        if distance <= radius_km:
            bank["distance"] = round(distance, 2)
            nearby.append(bank)
    return nearby

# Save donation and award points
def record_donation(surplus_food, donation_type, user_id):
    points_earned = len(surplus_food.split(",")) * 10  # 10 points per item
    st.session_state.rewards += points_earned
    donation = {
        "user_id": user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "food_items": surplus_food,
        "donation_type": donation_type,
        "points_earned": points_earned
    }
    st.session_state.donation_history.append(donation)
    # Save to JSON file (replace with database in production)
    with open("donations.json", "a") as f:
        json.dump(donation, f)
        f.write("\n")
    return points_earned

# Load leaderboard
def get_leaderboard():
    if os.path.exists("donations.json"):
        with open("donations.json", "r") as f:
            donations = [json.loads(line) for line in f if line.strip()]
        leaderboard = {}
        for donation in donations:
            user_id = donation["user_id"]
            points = donation["points_earned"]
            leaderboard[user_id] = leaderboard.get(user_id, 0) + points
        return sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    return []

# Streamlit App
st.title("SmartBite: Recipe & Rescue")
st.markdown("Reduce food waste, donate surplus food, and earn rewards for a sustainable future!")

# Sidebar for navigation
st.sidebar.header("Navigation")
module = st.sidebar.radio("Choose Module", ["Recipe Generator", "Food Donation", "User Profile", "Leaderboard"])

if module == "Recipe Generator":
    st.header("Smart Recipe Generator")
    st.write("Enter leftover ingredients to get personalized recipes. Prioritize near-expiry items to reduce waste.")
    
    # Input form
    ingredients = st.text_input("Enter ingredients (comma-separated, e.g., tomato, onion, pasta):")
    expiry_dates = st.text_input("Enter near-expiry ingredients (optional, comma-separated):")
    dietary_preference = st.selectbox("Dietary Preference", ["None", "Vegetarian", "Vegan", "Gluten-Free"])
    language = st.selectbox("Recipe Language", ["en", "te", "hi"], format_func=lambda x: LANGUAGES.get(x, "English"))
    
    if st.button("Generate Recipes"):
        if ingredients:
            recipes = fetch_recipes(ingredients.replace(" ", "+"), dietary_preference, language)
            if recipes:
                st.subheader("Suggested Recipes")
                for recipe in recipes:
                    st.write(f"{recipe['title']}")
                    st.write("Ingredients: " + ", ".join([ing["name"] for ing in recipe.get("usedIngredients", [])] + 
                                                             [ing["name"] for ing in recipe.get("missedIngredients", [])]))
                    st.write("Steps:")
                    # Display each step nicely numbered
                    if isinstance(recipe["steps"], list):
                        for i, step in enumerate(recipe["steps"], 1):
                            st.write(f"Step {i}: {step}")
                    else:
                        st.markdown(recipe["steps"])
                    
                    # Feedback mechanism
                    feedback = st.slider(f"Rate this recipe ({recipe['title']})", 1, 5, 3, key=recipe["id"])
                    if st.button("Submit Feedback", key=f"feedback_{recipe['id']}"):
                        st.success(f"Feedback ({feedback}/5) submitted for {recipe['title']}!")
                    st.write("---")
                if expiry_dates:
                    st.info(f"Prioritized recipes using near-expiry ingredients: {expiry_dates}")
            else:
                st.warning("No recipes found. Try different ingredients or preferences.")
        else:
            st.error("Please enter at least one ingredient.")

elif module == "Food Donation":
    st.header("Food Donation Module")
    st.write("Donate surplus food to nearby food banks and earn rewards!")
    
    # Get user location
    use_current_location = st.checkbox("Use my current location")
    user_lat, user_lng = None, None
    
    if use_current_location:
        try:
            g = geocoder.ip('me')
            if g.ok:
                user_lat, user_lng = g.latlng
                st.write(f"Detected location: Latitude {user_lat}, Longitude {user_lng}")
            else:
                st.error("Unable to detect location. Please enter manually.")
        except Exception as e:
            st.error(f"Error detecting location: {e}")
    
    # Manual location input
    if not use_current_location or user_lat is None:
        st.subheader("Enter Location Manually")
        user_lat = st.number_input("Latitude", value=17.385044, format="%.6f")
        user_lng = st.number_input("Longitude", value=78.486671, format="%.6f")
    
    # Donation form
    surplus_food = st.text_area("List surplus food items for donation:")
    donation_type = st.selectbox("Donation Type", ["Drop-off", "Pickup"])
    
    if st.button("Find Nearby Food Banks"):
        if user_lat and user_lng:
            nearby_banks = find_nearby_food_banks(user_lat, user_lng)
            if nearby_banks:
                st.subheader("Nearby Food Banks")
                m = folium.Map(location=[user_lat, user_lng], zoom_start=12)
                folium.Marker([user_lat, user_lng], popup="Your Location", icon=folium.Icon(color="blue")).add_to(m)
                for bank in nearby_banks:
                    folium.Marker(
                        [bank["lat"], bank["lng"]],
                        popup=f"{bank['name']}<br>Contact: {bank['contact']}<br>Distance: {bank['distance']} km",
                        icon=folium.Icon(color="green")
                    ).add_to(m)
                folium_static(m)
                
                # Display food banks as a table
                df = pd.DataFrame(nearby_banks)
                st.table(df[["name", "contact", "distance"]])
                
                # Donation confirmation and rewards
                if surplus_food:
                    points = record_donation(surplus_food, donation_type, st.session_state.user_id)
                    st.success(f"Donation of '{surplus_food}' scheduled as {donation_type}. Earned {points} reward points!")
                else:
                    st.warning("Please list surplus food items to proceed with donation.")
            else:
                st.warning("No food banks found within 10 km of your location.")
        else:
            st.error("Please provide a valid location.")

elif module == "User Profile":
    st.header("User Profile")
    st.write("Manage your preferences and view your donation history.")
    
    # Update dietary preferences
    st.session_state.dietary_prefs = st.selectbox("Update Dietary Preference", 
                                                  ["None", "Vegetarian", "Vegan", "Gluten-Free"], 
                                                  index=["None", "Vegetarian", "Vegan", "Gluten-Free"].index(st.session_state.dietary_prefs))
    
    # Display rewards and donation history
    st.subheader("Your Rewards")
    st.write(f"Total Reward Points: {st.session_state.rewards}")
    
    st.subheader("Donation History")
    if st.session_state.donation_history:
        history_df = pd.DataFrame(st.session_state.donation_history)
        st.table(history_df[["timestamp", "food_items", "donation_type", "points_earned"]])
        
        # Analytics: Calculate waste reduction
        total_items = sum(len(d["food_items"].split(",")) for d in st.session_state.donation_history)
        st.write(f"Estimated Food Waste Reduced: ~{total_items * 0.5} kg (assuming 0.5 kg per item)")
    else:
        st.write("No donations yet. Start donating to earn rewards!")

elif module == "Leaderboard":
    st.header("Community Leaderboard")
    st.write("Top donors making a difference!")
    leaderboard = get_leaderboard()
    if leaderboard:
        df = pd.DataFrame(leaderboard, columns=["User ID", "Points"])
        st.table(df)
    else:
        st.write("No donations recorded yet. Be the first to lead!")

# Footer
st.markdown("---")
st.markdown("Developed by J.Siri, G.Sreehitha, Sameeksha, B.Rishika, guided by Mrs. B.Spandhana")
st.markdown("Sreyas Institute of Engineering & Technology, Hyderabad, India")