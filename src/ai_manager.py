import json
import time
import os

from dotenv import load_dotenv

from google import genai
from google.genai import types
from google.genai import errors


# REQUIRES YOUR OWN API KEY
# USE GOOGLE AI STUDIO
# CREATE A .env FILE, IN THERE WRITE
# API_KEY={YOUR_API_KEY_HERE!!} NO CURLY BRACES AND REPLACE THE TEXT LOL

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")


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
    "networking_value, and attendance_feasibility. "
    "Do not assume or invent information that is not provided. "
    "If the event category cannot be determined, return 'unknown'."
)


def analyze_event(student_profile: dict, event_name, event_description):
    # Send student profile and event information to Gemini AI Flash
    # Return dictionary with scores and category.

    retries = 3
    client = genai.Client(api_key=API_KEY)

    prompt = f"""
        STUDENT PROFILE:
        Field of study: {student_profile["field_of_study"]}
        Interests: {", ".join(student_profile["interests"])}
        
        EVENT NAME: {event_name}
        EVENT DESCRIPTION:
        {event_description}

        Analyse this event for this student.
    """

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ANALYSIS_SCHEMA,
                    temperature=0.2,
                ),
            )

            return json.loads(response.text)

        except errors.APIError as error:
            # Temporary errors - retry
            if error.code in [429, 503]:
                if attempt < retries - 1:
                    wait = 2**attempt
                    print(
                        f"Gemini API error {error.code}. "
                        f"Retrying in {wait} seconds..."
                    )

                    time.sleep(wait)
                    continue

            # Non-retryable API error
            print(f"Gemini API error {error.code}: {error.message}")
            break

        except Exception as error:
            print(f"Unexpected error communicating with Gemini: {error}")
            break

    # Return fallback if all attempts fail
    return None


"""
if __name__ == "__main__":
    # 1. Provide sample input data    
    sample_profile = {
        "field_study": "Computer Science",
        "interest": ["Backend Engineering", "Cloud Computing", "Summer software internships"]
    }
    
    sample_event = (
        "Distributed Systems Meetup: Senior engineers discuss building high-throughput "
        "microservices with Go and Kubernetes. Q&A and networking session afterwards."
    )

    # 2. Run the function (pass your API key string here if not set in your environment)
    # result = analyze_event(sample_profile, sample_event, api_key="YOUR_GEMINI_API_KEY")
    result = analyze_event(sample_profile, sample_event)

    # 3. Print the output
    print("Function Output:")
    print(json.dumps(result, indent=2))

    # 4. Basic sanity check assertions
    expected_keys = {"event_category", "career_relevance", "learning_value", "networking_value"}
    assert expected_keys.issubset(result.keys()), f"Missing keys in result: {result}"
    print("\n✓ Schema test passed: All expected keys are present.")
"""
