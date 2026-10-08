import json
import os


# ============================================================
# FILE LOCATIONS
# ============================================================

# Folder where our JSON data files will be stored.
# In Docker, this folder will be connected to a volume.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create the path to the data folder.
DATA_DIR = os.path.join(BASE_DIR, "data")

# Create the full paths to the JSON files.
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")


EVENTS_FILE = os.path.join(DATA_DIR, "events.json")


# ============================================================
# CREATE DATA FOLDER
# ============================================================

def ensure_data_directory():
    # Create the data folder if it does not already exist.
    #
    # exist_ok=True means:
    # - If the folder does not exist -> create it.
    # - If the folder already exists -> do nothing.
    os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================
# SAVE STUDENT PROFILE
# ============================================================

def save_profile(profile):
    # Make sure the data folder exists before saving.
    ensure_data_directory()

    # Open profile.json in write mode.
    # "w" means the existing profile will be replaced.
    # UTF-8 allows normal text characters to be stored.
    with open(PROFILE_FILE, "w", encoding="utf-8") as file:

        # Convert the Python dictionary into JSON
        # and save it into the file.
        #
        # indent=4 makes the JSON easier for humans to read.
        json.dump(profile, file, indent=4)


# ============================================================
# LOAD STUDENT PROFILE
# ============================================================

def load_profile():
    try:
        # Open the existing profile.json file.
        with open(PROFILE_FILE, "r", encoding="utf-8") as file:

            # Convert the JSON data back into a Python object
            # and return it to the program.
            return json.load(file)

    except FileNotFoundError:
        # If profile.json does not exist,
        # return an empty dictionary instead of crashing.
        return {}

    except json.JSONDecodeError:
        # If profile.json exists but contains invalid JSON,
        # return an empty dictionary instead of crashing.
        return {}


# ============================================================
# SAVE EVENT
# ============================================================

def save_event(record):
    # Make sure the data folder exists.
    ensure_data_directory()

    # Load all existing event records first.
    events = load_events()

    # Add the new processed event record to the list.
    #
    # The record can contain:
    # - io_input
    # - ai_output
    # - logic_output
    events.append(record)

    # Open events.json in write mode.
    with open(EVENTS_FILE, "w", encoding="utf-8") as file:

        # Save the updated list of events as JSON.
        json.dump(events, file, indent=4)


# ============================================================
# LOAD EVENTS
# ============================================================

def load_events():
    try:
        # Open events.json.
        with open(EVENTS_FILE, "r", encoding="utf-8") as file:

            # Convert the JSON data into a Python list
            # and return it.
            return json.load(file)

    except FileNotFoundError:
        # If events.json does not exist yet,
        # return an empty list.
        return []

    except json.JSONDecodeError:
        # If events.json is corrupted or contains invalid JSON,
        # return an empty list instead of crashing.
        return []


# ============================================================
# SEARCH / QUERY EVENTS
# ============================================================

def query_events(filter_function):
    # Load all saved events.
    events = load_events()

    # Go through every event and keep only the events
    # that satisfy the filter function.
    #
    # Example:
    # query_events(lambda event: event["logic_output"]["recommendation"] == "ATTEND")
    #
    # This would return only events recommended as ATTEND.
    return [event for event in events if filter_function(event)]

#test
if __name__ == "__main__":
    print("Data manager is working!")

    ensure_data_directory()
    print("Data directory checked.")

    profile = load_profile()
    print("Profile:", profile)

    events = load_events()
    print("Events:", events)



# ============================================================
# TEST DATA MANAGER
# ============================================================

if __name__ == "__main__":
    print("Testing data manager...")

    # --------------------------------------------------------
    # TEST 1: Create and save a student profile
    # --------------------------------------------------------

    profile = {
        "name": "Test Student",
        "course": "BEng ICT",
        "year": 3,
        "interests": ["AI", "Cybersecurity", "Data Analytics"]
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
            "duration": 120
        },

        "ai_output": {
            "event_category": "Tech Meetup",
            "career_relevance": 5,
            "learning_value": 5,
            "networking_value": 4
        },

        "logic_output": {
            "recommendation": "ATTEND",
            "reason": "The event is highly relevant to the student's interests."
        }
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