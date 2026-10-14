import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")


def ensure_data_directory():
    os.makedirs(DATA_DIR, exist_ok=True)


def save_profile(profile:dict):
    ensure_data_directory()
    with open(PROFILE_FILE, "w", encoding="utf-8") as file:
        json.dump(profile, file, indent=4)


def load_profile():
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_events(events:list):
    ensure_data_directory()

    with open(EVENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(events, file, indent=4)


def load_events():
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return []


# SEARCH / QUERY EVENTS
def query_events(filter_function):
    events = load_events()
    return [event for event in events if filter_function(event)]