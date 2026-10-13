import json
import time
import os

import httpx
from dotenv import load_dotenv

from google import genai
from google.genai import errors, types


# REQUIRES YOUR OWN API KEY
# USE GOOGLE AI STUDIO
# CREATE A .env FILE, IN THERE WRITE
# API_KEY=YOUR_API_KEY_HERE

# environment var
load_dotenv()
API_KEY = os.getenv("API_KEY")

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_RETRIES = 3
REQUEST_TIMEOUT_MS = 30000
RETRY_CODES = {429, 500, 503, 504}  # Network errors and timeouts can retry till max

# Define the expected JSON output
ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "event_category": {
            "type": "STRING",
            "description": "Short category of the event (e.g. 'Career Workshop'). Return 'unknown' if unclear.",
        },
        "career_relevance": {
            "type": "INTEGER",
            "description": "1: Not relevant at all, 2: Slightly, 3: Somewhat, 4: Highly, 5: Directly relevant.",
        },
        "learning_value": {
            "type": "INTEGER",
            "description": "1: Very little, 2: Low, 3: Moderate, 4: High, 5: Very high learning value.",
        },
        "networking_value": {
            "type": "INTEGER",
            "description": "1: None, 2: Very limited, 3: Some, 4: Good, 5: Strong networking opportunity.",
        },
        "ai_reasoning": {
            "type": "STRING",
            "description": "CONCISE 1-2 sentence explanation of how the event aligns with the student's profile and why these scores were given.",
        },
    },
    "required": [
        "event_category",
        "career_relevance",
        "learning_value",
        "networking_value",
        "ai_reasoning",
    ],
}

SYSTEM_INSTRUCTION = (
    "You are an event decision assistant for students. "
    "Evaluate each event strictly against the student's profile. "
    "Consider the student's field of study and interests. "
    "Assign integer ratings from 1 to 5 for career_relevance, learning_value, "
    "networking_value."
    "Do not assume or invent information that is not provided. "
    "If the event category cannot be determined, return 'unknown'."
)


def build_prompt(student_profile, event_name, event_description):
    return f"""
        STUDENT PROFILE:
        Field of study: {student_profile["field_of_study"]}
        Interests: {", ".join(student_profile["interests"])}

        EVENT NAME: {event_name}
        EVENT DESCRIPTION:
        {event_description}

        Analyse this event for this student.
    """


def handle_api_error(error):
    message = (error.message or "").lower()

    # Invalid api key
    if error.code in [401, 403] or (error.code == 400 and "api key" in message):
        return "Authentication failed: your API key is invalid or not allowed.", False

    # Wrong ai model
    if error.code == 404:
        return f"Model '{MODEL_NAME}' was not found. Check the model name.", False

    # Temporary errors, so trying again may work
    if error.code == 429:
        return "Rate limit reached (too many requests). Wait a moment and try again.", True
    if error.code in RETRY_CODES:
        return f"The Gemini server had a problem (error {error.code}).", True

    # other error that retrying won't fix
    return f"Gemini API error {error.code}: {error.message}", False


def wait_before_retry(attempt):
    # wait 1,5,25 seconds and power of 5 so on, but cannot exceed 60s
    if attempt < MAX_RETRIES - 1:
        wait = min(5**attempt,  60)
        print(f"Retrying in {wait} seconds... (attempt {attempt + 1}/{MAX_RETRIES})")
        time.sleep(wait)


def request_analysis(client, prompt):
    # Makes ONE request to Gemini and returns the reply as a dictionary.
    # Errors are NOT handled here, analyze_event deals with them.
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ANALYSIS_SCHEMA,
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def analyze_event(student_profile: dict, event_name, event_description):
    """
    Send student profile and event information to Gemini to analyze
    return:
    response dictionary, error
    """

    if not API_KEY:
        return None, "API_KEY not found. Make sure your .env file has API_KEY=your_key"

    client = genai.Client(
        api_key=API_KEY,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),  # give up after REQUEST_TIMEOUT_MS
    )

    prompt = build_prompt(student_profile, event_name, event_description)

    error_message = ""

    for attempt in range(MAX_RETRIES):
        try:
            return request_analysis(client, prompt), None

        except errors.APIError as error:
            error_message, should_retry = handle_api_error(error)
            if not should_retry:
                return None, error_message

        except httpx.TransportError:
            # no internet, no connection, timeouts
            error_message = "Network problem: could not reach the Gemini API. Check your internet connection."

        except (json.JSONDecodeError, TypeError):
            # empty, blocked, invalid JSON
            error_message = "Gemini sent back an empty or invalid response."

        # attempt worth retry
        wait_before_retry(attempt)

    return None, f"Gave up after {MAX_RETRIES} attempts. Error not could not be resolved. {error_message}"


if __name__ == "__main__":
    sample_profile = {
        "field_of_study": "Computer Science",
        "interests": [
            "Backend Engineering",
            "Cloud Computing",
            "Summer software internships",
        ],
    }
 
    sample_name = "Distributed Systems Meetup"
    sample_description = ("Senior engineers discuss building high-throughput microservices with Go and Kubernetes. Q&A and networking session afterwards.")
 
    result = analyze_event(sample_profile, sample_name, sample_description)
 
    if result is None:
        print("AI Analysis failed.")
    else:
        print("Function Output:")
        print(json.dumps(result, indent=2))