"""
main.py - EventWise Web GUI Application Entrypoint.
Coordinates the application workflow and serves the Flask web application using IOManager.
"""

from datetime import datetime
from pathlib import Path
import time

from dotenv import load_dotenv
from flask import Flask

from src.ai_manager import AIManager
from src.data_manager import DataManager
from src.exceptions import ValidationError
from src.geolocation import GeoLocationService
from src.io_manager import IOManager
from src.journey_planner import JourneyPlanner
from src.logic_manager import LogicManager
from src.event_record import EventRecord
from src.student_profile import StudentProfile
from src.mongodb_storage import MongoStorage
from src.travel_assessment import TravelAssessment, TravelEvaluator
from src.travel_result import serialize_travel_result

# Load environment variables (.env)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


class EventWise:
    """Main application orchestrator coordinating program logic and managers."""

    def __init__(self, io_manager: IOManager | None = None):
        self.app = Flask(__name__)
        self.io_manager = io_manager or IOManager()
        self.ai_manager = AIManager()
        self.logic_manager = LogicManager()
        self.geo_service = GeoLocationService()
        self.travel_evaluator = TravelEvaluator()
        self.journey_planner = JourneyPlanner(self.geo_service, self.travel_evaluator)

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register URL routes to their corresponding class methods."""
        self.app.add_url_rule("/", view_func=self.home, methods=["GET"])
        self.app.add_url_rule("/api/state", view_func=self.state, methods=["GET"])
        self.app.add_url_rule("/api/profile", view_func=self.save_profile, methods=["POST"])
        self.app.add_url_rule("/api/analyse", view_func=self.analyse, methods=["POST"])

    def _get_storage(self):
        """Create a fresh database connection and DataManager instance."""
        storage = MongoStorage()
        return storage, DataManager(storage=storage)

    def _load_profile(self, data_manager: DataManager) -> StudentProfile:
        """Load and deserialize the student profile entity from storage."""
        stored = data_manager.load_profile()
        if isinstance(stored, StudentProfile):
            return stored
        if isinstance(stored, dict):
            return StudentProfile.from_dict(stored)
        return StudentProfile()

    def _load_events(self, data_manager: DataManager) -> list[EventRecord]:
        """Load and deserialize event records from storage."""
        raw_events = data_manager.load_events()
        events = []
        for obj in raw_events or []:
            try:
                event = obj if isinstance(obj, EventRecord) else EventRecord.from_dict(obj)
                events.append(event)
            except (TypeError, ValueError, KeyError):
                continue
        return events

    def assess_travel(self, travel: dict, profile: StudentProfile) -> dict:
        """Calculate public transit journey feasibility for event attendance."""
        unavailable = TravelAssessment("UNAVAILABLE", "UNAVAILABLE", self.travel_evaluator.arrival_buffer_minutes)

        def invalid_result():
            return serialize_travel_result(
                unavailable,
                error_code="INVALID_INPUT",
                preferred_limit_minutes=self.travel_evaluator.preferred_limit_minutes,
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
            event_start = self.travel_evaluator._singapore_datetime(event_start, "Event start")
        except (ValueError, ValidationError):
            return invalid_result()

        assessment, code = self.journey_planner.plan(
            origin, travel.get("destination_postal_code"), event_start
        )
        return serialize_travel_result(
            assessment,
            error_code=code,
            event_start=event_start,
            preferred_limit_minutes=self.travel_evaluator.preferred_limit_minutes,
        )

    # ------------------------------------------------------------------
    # Route Handlers
    # ------------------------------------------------------------------
    def home(self):
        """Coordinate serving the single-page application HTML GUI."""
        return self.io_manager.render_home()

    def state(self):
        """Coordinate retrieving profile and events, then returning via IOManager."""
        storage = None
        try:
            storage, db = self._get_storage()
            profile = self._load_profile(db)
            events = self._load_events(db)
            return self.io_manager.send_state(profile, events)
        except Exception as exc:
            return self.io_manager.send_server_error(exc)
        finally:
            if storage is not None:
                storage.close()

    def save_profile(self):
        """Coordinate user profile input collection, validation, saving, and response."""
        data, error = self.io_manager.get_profile_input()
        if error is not None:
            return error

        storage = None
        try:
            storage, db = self._get_storage()
            existing_profile = self._load_profile(db)

            home_postal = data["home_postal_code"]
            if home_postal is None:
                home_postal = existing_profile.home_postal_code

            profile = StudentProfile.from_dict({
                "field_of_study": data["field_of_study"],
                "interests": data["interests"],
                "home_postal_code": home_postal,
            })
            db.save_profile(profile.to_dict())
            return self.io_manager.send_profile(profile)
        except Exception as exc:
            return self.io_manager.send_server_error(exc)
        finally:
            if storage is not None:
                storage.close()

    def analyse(self):
        """Coordinate event analysis, logic evaluation, travel planning, saving, and response."""
        data, error = self.io_manager.get_event_input()
        if error is not None:
            return error

        storage = None
        try:
            storage, db = self._get_storage()
            profile = self._load_profile(db)
            if profile.is_empty():
                return self.io_manager.send_error("Complete your Profile tab before analysing an event.", 400)

            start_time = time.perf_counter()
            analysis_profile = {
                "field_of_study": profile.field_of_study,
                "interests": list(profile.interests),
            }
            ai_result, ai_error = self.ai_manager.analyze_event(
                analysis_profile, data["event_name"], data["event_description"]
            )
            end_time = time.perf_counter()
            print(f"AI Analysis Time: {end_time - start_time:.2f} seconds", flush=True)

            if ai_result is None:
                return self.io_manager.send_error(ai_error or "AI analysis was unsuccessful.", 502)

            summary, logic_error = self.logic_manager.generate_summary(ai_result, data["workload"])
            if summary is None:
                return self.io_manager.send_error(logic_error or "Could not calculate the recommendation.", 422)

            summary = dict(summary)
            summary.update(
                event_name=data["event_name"],
                event_description=data["event_description"],
                workload=data["workload"],
            )
            record = EventRecord.from_dict(summary)
            existing = self._load_events(db)
            existing.append(record)
            db.save_events([e.to_dict() for e in existing])

            travel_result = self.assess_travel(data.get("travel", {}), profile)
            return self.io_manager.send_analysis(record, existing, travel_result)
        except Exception as exc:
            return self.io_manager.send_server_error(exc)
        finally:
            if storage is not None:
                storage.close()

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
        """Start the Flask web application."""
        self.app.run(host=host, port=port, debug=debug)


# Global application instance and Flask WSGI reference
eventwise = EventWise()
app = eventwise.app


def main() -> None:
    """Application main entrypoint."""
    EventWise().run()


if __name__ == "__main__":
    main()
