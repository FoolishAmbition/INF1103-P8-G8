import json
import os


# ============================================================
# FILE LOCATIONS
# ============================================================

# Folder where our JSON data files will be stored.
# In Docker, this folder will be connected to a volume.
DATA_DIR = "data"

# File used to store the student's profile.
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")

# File used to store all event records.
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