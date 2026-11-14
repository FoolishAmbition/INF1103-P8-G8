"""EventWise Flask interface. Run alongside your existing src/ package."""
from flask import Flask, jsonify, render_template, request
import time
from datetime import datetime

from src.exceptions import ValidationError
from src.geolocation import GeoLocationService
from src.journey_planner import JourneyPlanner
from src.travel_assessment import TravelAssessment, TravelEvaluator
from src.travel_result import serialize_travel_result

app = Flask(__name__)


def get_backend():
    """Construct the existing managers without starting the terminal UI."""
    from src.ai_manager import AIManager
    from src.data_manager import DataManager
    from src.logic_manager import LogicManager
    from src.mongodb_storage import MongoStorage
    from src.models import StudentProfile, EventRecord
    storage = MongoStorage()
    return storage, DataManager(storage=storage), AIManager(), LogicManager(), StudentProfile, EventRecord


def unpack_events(raw, EventRecord):
    items = []
    for obj in raw or []:
        try:
            event = obj if isinstance(obj, EventRecord) else EventRecord.from_dict(obj)
            items.append(event)
        except (TypeError, ValueError, KeyError):
            continue
    return items


def profile_from_storage(data_manager, StudentProfile):
    stored = data_manager.load_profile()
    if isinstance(stored, StudentProfile):
        return stored
    if isinstance(stored, dict):
        return StudentProfile.from_dict(stored)
    return StudentProfile()


def error_response(exc):
    # Avoid exposing internal exception details to browser users.
    app.logger.exception("EventWise backend failed: %s", exc)
    return jsonify(error="Could not connect to EventWise services. Check Docker, MongoDB, and your .env configuration."), 503


@app.get("/")
def home():
    return render_template("analyse.html")


@app.get("/api/state")
def state():
    storage = None
    try:
        storage, db, _, _, StudentProfile, EventRecord = get_backend()
        profile = profile_from_storage(db, StudentProfile)
        events = unpack_events(db.load_events(), EventRecord)
        return jsonify(profile=profile.to_dict(), events=[e.to_dict() for e in events])
    except Exception as exc:
        return error_response(exc)
    finally:
        if storage is not None:
            storage.close()


@app.post("/api/profile")
def save_profile():
    payload = request.get_json(silent=True) or {}
    field = payload.get("field_of_study", "")
    interests = payload.get("interests", [])
    home_postal_code = payload.get("home_postal_code", None)
    if home_postal_code is not None and (not isinstance(home_postal_code, str) or (home_postal_code and (len(home_postal_code) != 6 or not home_postal_code.isascii() or not home_postal_code.isdigit()))):
        return jsonify(error="Home postal code must be empty or exactly six digits."), 400
    if not isinstance(field, str) or not isinstance(interests, list) or not all(isinstance(x, str) for x in interests):
        return jsonify(error="Please enter a valid field of study and interests."), 400
    storage = None
    try:
        storage, db, _, _, StudentProfile, _ = get_backend()
        existing_profile = profile_from_storage(db, StudentProfile)
        profile = StudentProfile.from_dict({
            "field_of_study": field.strip(),
            "interests": [x.strip() for x in interests if x.strip()],
            "home_postal_code": home_postal_code if home_postal_code is not None else existing_profile.home_postal_code
        })
        db.save_profile(profile.to_dict())
        return jsonify(message="Profile saved!", profile=profile.to_dict())
    except Exception as exc:
        return error_response(exc)
    finally:
        if storage is not None:
            storage.close()


def assess_web_travel(travel, profile):
    """Keep optional journey failures separate from successful event analysis."""
    evaluator = TravelEvaluator()
    unavailable = TravelAssessment("UNAVAILABLE", "UNAVAILABLE", evaluator.arrival_buffer_minutes)

    def invalid_result():
        return serialize_travel_result(
            unavailable, error_code="INVALID_INPUT",
            preferred_limit_minutes=evaluator.preferred_limit_minutes,
        )

    if not isinstance(travel, dict):
        return invalid_result()
    choice = travel.get("origin_choice", "skip")
    if choice == "skip":
        return serialize_travel_result()
    if choice not in ("home", "alternate"):
        return invalid_result()

    origin = profile.home_postal_code
    if choice == "alternate":
        origin = travel.get("origin_postal_code")
    start_text = travel.get("event_start")
    if not isinstance(start_text, str):
        return invalid_result()
    try:
        event_start = datetime.fromisoformat(start_text)
        event_start = evaluator._singapore_datetime(event_start, "Event start")
    except (ValueError, ValidationError):
        return invalid_result()

    planner = JourneyPlanner(GeoLocationService(), evaluator)
    assessment, code = planner.plan(
        origin, travel.get("destination_postal_code"), event_start
    )
    return serialize_travel_result(
        assessment, error_code=code, event_start=event_start,
        preferred_limit_minutes=evaluator.preferred_limit_minutes,
    )


@app.post("/api/analyse")
def analyse():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error="Enter a valid event object."), 400
    name = payload.get("event_name", "")
    description = payload.get("event_description", "")
    workload = payload.get("workload", "")
    if (not isinstance(name, str) or not isinstance(description, str)
            or not name.strip() or not description.strip()
            or len(name) > 150 or len(description) > 2000
            or workload not in ("Low", "Medium", "High")):
        return jsonify(error="Enter an event name, description, and valid workload."), 400

    storage = None
    try:
        storage, db, ai, logic, StudentProfile, EventRecord = get_backend()
        profile = profile_from_storage(db, StudentProfile)
        if profile.is_empty():
            return jsonify(error="Complete your Profile tab before analysing an event."), 400

        start_time = time.perf_counter()
        analysis_profile = {
            "field_of_study": profile.field_of_study,
            "interests": list(profile.interests),
        }
        ai_result, ai_error = ai.analyze_event(analysis_profile, name.strip(), description.strip())
        end_time = time.perf_counter()
        print(f"AI Analysis Time: {end_time - start_time:.2f} seconds", flush=True)
        if ai_result is None:
            return jsonify(error=ai_error or "AI analysis was unsuccessful."), 502
        summary, logic_error = logic.generate_summary(ai_result, workload)
        if summary is None:
            return jsonify(error=logic_error or "Could not calculate the recommendation."), 422

        summary = dict(summary)
        summary.update(event_name=name.strip(), event_description=description.strip(), workload=workload)
        record = EventRecord.from_dict(summary)
        existing = unpack_events(db.load_events(), EventRecord)
        existing.append(record)
        db.save_events([e.to_dict() for e in existing])
        travel_result = assess_web_travel(payload.get("travel", {}), profile)
        return jsonify(
            message="Analysis saved!", event=record.to_dict(),
            events=[e.to_dict() for e in existing], travel=travel_result,
        )
    except Exception as exc:
        return error_response(exc)
    finally:
        if storage is not None:
            storage.close()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
