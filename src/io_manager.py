"""
src/io_manager.py - Web I/O Manager for EventWise.
Handles all user Input and Output operations for the web GUI.
"""

from flask import current_app, jsonify, render_template, request

from src.base_manager import BaseManager


class IOManager(BaseManager):
    """Handles all Input and Output operations for the EventWise web interface."""

    def __init__(self, name: str = "IOManager"):
        super().__init__(name)

    def run(self) -> None:
        """Lifecycle entry point required by BaseManager."""
        pass

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

    # ------------------------------------------------------------------
    # Sending Responses & Displaying Information (Output)
    # ------------------------------------------------------------------
    def send_state(self, profile, events):
        """Format and send the application state (profile and events) as JSON."""
        profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else (profile or {})
        events_list = [e.to_dict() if hasattr(e, "to_dict") else e for e in (events or [])]
        return jsonify(profile=profile_dict, events=events_list)

    def send_profile(self, profile, message="Profile saved!"):
        """Format and send the saved profile confirmation as JSON."""
        profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else profile
        return jsonify(message=message, profile=profile_dict)

    def send_analysis(self, record, events, travel_result=None, message="Analysis saved!"):
        """Format and send the event analysis result as JSON."""
        record_dict = record.to_dict() if hasattr(record, "to_dict") else record
        events_list = [e.to_dict() if hasattr(e, "to_dict") else e for e in (events or [])]
        return jsonify(
            message=message,
            event=record_dict,
            events=events_list,
            travel=travel_result,
        )

    def send_error(self, message, status_code=400):
        """Format and send an error response with an HTTP status code."""
        return jsonify(error=message), status_code

    def send_server_error(self, exc=None):
        """Format and send a 503 server error message without leaking internal details."""
        if current_app:
            current_app.logger.exception("EventWise backend failed: %s", exc)
        return jsonify(error="Could not connect to EventWise services. Check Docker, MongoDB, and your .env configuration."), 503
