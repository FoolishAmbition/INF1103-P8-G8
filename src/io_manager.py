"""
src/io_manager.py - Web I/O Manager for EventWise.
Handles all user Input and Output operations for the web GUI.
"""

from flask import current_app, jsonify, render_template, request

from src.base_manager import BaseManager
from src.event_record import EventRecord
from src.student_profile import StudentProfile
from src.travel_assessment import TravelAssessment
from src.travel_result import TravelResult


class IOManager(BaseManager):
    """Handles all Input and Output operations for the EventWise web interface."""

    def __init__(self, name: str = "IOManager"):
        super().__init__(name)

    # ------------------------------------------------------------------
    # Web Presentation (Output)
    # ------------------------------------------------------------------
    def render_home(self):
        """Render the main HTML template."""
        return render_template("analyse.html")

    # ------------------------------------------------------------------
    # User Input Collection & Validation (Input)
    # ------------------------------------------------------------------
    def get_profile_input(self):
        """
        Collect and validate student profile inputs from the web request.

        Returns:
            tuple: (data_dict, None) on success, or (None, error_response) on failure.
        """
        payload = request.get_json(silent=True) or {}
        field = payload.get("field_of_study", "")
        interests = payload.get("interests", [])
        home_postal_code = payload.get("home_postal_code", None)

        # Validate home postal code: optional, but if provided must be exactly 6 digits
        if home_postal_code is not None:
            if not isinstance(home_postal_code, str):
                return None, self.send_error("Home postal code must be empty or exactly six digits.", 400)
            postal_str = home_postal_code.strip()
            if postal_str and (len(postal_str) != 6 or not postal_str.isascii() or not postal_str.isdigit()):
                return None, self.send_error("Home postal code must be empty or exactly six digits.", 400)

        # Validate field of study and interests
        if not isinstance(field, str) or not isinstance(interests, list) or not all(isinstance(x, str) for x in interests):
            return None, self.send_error("Please enter a valid field of study and interests.", 400)

        data = {
            "field_of_study": field.strip(),
            "interests": [x.strip() for x in interests if x.strip()],
            "home_postal_code": home_postal_code.strip() if isinstance(home_postal_code, str) else home_postal_code,
        }
        return data, None

    def get_event_input(self):
        """
        Collect and validate event inputs from the web request.

        Returns:
            tuple: (data_dict, None) on success, or (None, error_response) on failure.
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None, self.send_error("Enter a valid event object.", 400)

        name = payload.get("event_name", "")
        description = payload.get("event_description", "")
        workload = payload.get("workload", "")

        if (not isinstance(name, str) or not isinstance(description, str)
                or not name.strip() or not description.strip()
                or len(name) > 150 or len(description) > 2000
                or workload not in ("Low", "Medium", "High")):
            return None, self.send_error("Enter an event name, description, and valid workload.", 400)

        data = {
            "event_name": name.strip(),
            "event_description": description.strip(),
            "workload": workload,
            "travel": payload.get("travel", {}),
        }
        return data, None

    def get_filter_params(self):
        """
        Collect and parse event filter query parameters from the web request.

        Returns:
            dict: Parsed query parameters with 'keyword', 'recommended', and 'min_score'.
        """
        keyword = request.args.get("keyword", "").strip() or None
        recommended = request.args.get("recommended")
        if recommended:
            recommended = recommended.strip()
            if recommended.upper() == "ALL":
                recommended = None

        min_score_raw = request.args.get("min_score")
        min_score = None
        if min_score_raw is not None and min_score_raw.strip() != "":
            try:
                min_score = int(min_score_raw)
            except ValueError:
                try:
                    min_score = float(min_score_raw)
                except ValueError:
                    min_score = None

        return {
            "keyword": keyword,
            "recommended": recommended,
            "min_score": min_score,
        }

    # ------------------------------------------------------------------
    # Sending Responses & Displaying Information (Output)
    # ------------------------------------------------------------------
    def send_events(self, events: list[EventRecord]):
        """Format and send the filtered events list as JSON."""
        return jsonify(events=[event.to_dict() for event in events])

    def send_analytics(self, analytics):
        """Format and send the event analytics summary as JSON."""
        return jsonify(analytics=analytics)

    def send_state(self, profile: StudentProfile, events: list[EventRecord]):
        """Format and send the application state (profile and events) as JSON."""
        return jsonify(
            profile=profile.to_dict(),
            events=[event.to_dict() for event in events],
        )

    def send_profile(self, profile: StudentProfile, message="Profile saved!"):
        """Format and send the saved profile confirmation as JSON."""
        return jsonify(message=message, profile=profile.to_dict())

    def send_analysis(
        self,
        record: EventRecord,
        events: list[EventRecord],
        travel_result=None,
        message="Analysis saved!",
    ):
        """Format and send the event analysis result as JSON."""
        return jsonify(
            message=message,
            event=record.to_dict(),
            events=[event.to_dict() for event in events],
            travel=travel_result,
        )

    def sanitize_travel_result(
        self, assessment: TravelAssessment | None = None
    ) -> dict:
        """Format travel data as a safe GUI response."""
        return TravelResult(assessment).to_dict()

    def send_error(self, message, status_code=400):
        """Format and send an error response with an HTTP status code."""
        return jsonify(error=message), status_code

    def send_server_error(self, exc=None):
        """Format and send a 503 server error message without leaking internal details."""
        if current_app:
            current_app.logger.exception("EventWise backend failed: %s", exc)
        return jsonify(error="Could not connect to EventWise services. Check Docker, MongoDB, and your .env configuration."), 503
