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


# test
if __name__ == "__main__":
    print("Data manager is working!")

    ensure_data_directory()
    print("Data directory checked.")

    profile = load_profile()
    print("Profile:", profile)

    events = load_events()
    print("Events:", events)


if __name__ == "__main__":
    print("Testing data manager...")

    # --------------------------------------------------------
    # TEST 1: Create and save a student profile
    # --------------------------------------------------------

    profile = {
        "name": "Test Student",
        "course": "BEng ICT",
        "year": 3,
        "interests": ["AI", "Cybersecurity", "Data Analytics"],
    }

    save_profile(profile)

    print("Profile saved successfully.")

    # --------------------------------------------------------
    # TEST 2: Load the student profile
    # --------------------------------------------------------

    loaded_profile = load_profile()

    print("Loaded profile:")
    print(loaded_profile)

    # --------------------------------------------------------
    # TEST 3: Create and save an event
    # --------------------------------------------------------

    event = {
        "io_input": {
            "event_name": "AI Technology Meetup",
            "description": "A meetup about AI and machine learning.",
            "duration": 120,
        },
        "ai_output": {
            "event_category": "Tech Meetup",
            "career_relevance": 5,
            "learning_value": 5,
            "networking_value": 4,
        },
        "logic_output": {
            "recommendation": "ATTEND",
            "reason": "The event is highly relevant to the student's interests.",
        },
    }

    save_event(event)

    print("Event saved successfully.")

    # --------------------------------------------------------
    # TEST 4: Load events
    # --------------------------------------------------------

    loaded_events = load_events()

    print("Loaded events:")
    print(loaded_events)

    print("\nData manager test completed!")
