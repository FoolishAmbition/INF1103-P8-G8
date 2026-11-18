"""
main.py - EventWise Web GUI Application Entrypoint.
Coordinates the application workflow and serves the Flask web application using IOManager.
"""

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from src.ai_manager import AIManager
from src.data_manager import DataManager
from src.exceptions import EventWiseError
from src.io_manager import IOManager
from src.logic_manager import LogicManager

# Load environment variables (.env)
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


class EventWise:
    """Main application orchestrator coordinating program logic and managers."""

    def __init__(
        self,
        io_manager: IOManager | None = None,
        ai_manager: AIManager | None = None,
        logic_manager: LogicManager | None = None,
        data_manager: DataManager | None = None,
    ):
        self._app = Flask(__name__)
        self._io_manager = io_manager if io_manager is not None else IOManager()
        self._ai_manager = ai_manager if ai_manager is not None else AIManager()
        self._logic_manager = (
            logic_manager if logic_manager is not None else LogicManager()
        )

        self._data_manager = data_manager if data_manager is not None else DataManager()

        self._setup_routes()

    @property
    def app(self):
        return self._app

    def _setup_routes(self) -> None:
        """Register URL routes to their corresponding class methods."""
        self._app.add_url_rule("/", view_func=self.home, methods=["GET"])
        self._app.add_url_rule("/api/state", view_func=self.state, methods=["GET"])
        self._app.add_url_rule("/api/events", view_func=self.get_events, methods=["GET"])
        self._app.add_url_rule("/api/analytics", view_func=self.get_analytics, methods=["GET"])
        self._app.add_url_rule("/api/profile", view_func=self.save_profile, methods=["POST"])
        self._app.add_url_rule("/api/analyse", view_func=self.analyse, methods=["POST"])

    # ------------------------------------------------------------------
    # Route Handlers
    # ------------------------------------------------------------------
    def home(self):
        """Coordinate serving the single-page application HTML GUI."""
        return self._io_manager.render_home()

    def state(self):
        """Coordinate retrieving profile and events, then returning via IOManager."""
        try:
            profile = self._data_manager.get_profile()
            events = self._data_manager.get_events()
            return self._io_manager.send_state(profile, events)
        except EventWiseError as exc:
            return self._io_manager.send_server_error(exc)

    def get_events(self):
        """Coordinate event query input, filtering, and response formatting."""
        params = self._io_manager.get_filter_params()
        try:
            filtered = self._data_manager.filter_events(
                keyword=params.get("keyword"),
                recommended=params.get("recommended"),
                min_score=params.get("min_score"),
            )
            return self._io_manager.send_events(filtered)
        except EventWiseError as exc:
            return self._io_manager.send_server_error(exc)

    def get_analytics(self):
        """Coordinate analytics retrieval and response formatting."""
        try:
            summary = self._data_manager.get_analytics_summary()
            return self._io_manager.send_analytics(summary)
        except EventWiseError as exc:
            return self._io_manager.send_server_error(exc)

    def save_profile(self):
        """Coordinate user profile input collection, validation, saving, and response."""
        data, error = self._io_manager.get_profile_input()
        if error is not None:
            return error

        try:
            profile = self._data_manager.update_profile(data)
            return self._io_manager.send_profile(profile)
        except EventWiseError as exc:
            return self._io_manager.send_server_error(exc)

    def analyse(self):
        """Coordinate event analysis, manager delegation, and response formatting."""
        data, error = self._io_manager.get_event_input()
        if error is not None:
            return error

        try:
            profile = self._data_manager.get_profile()
            if not self._logic_manager.profile_is_ready(profile):
                return self._io_manager.send_error("Complete your Profile tab before analysing an event.", 400)

            analysis_profile = {
                "field_of_study": profile.field_of_study,
                "interests": list(profile.interests),
            }
            ai_result, ai_error = self._ai_manager.analyze_event(
                analysis_profile, data["event_name"], data["event_description"]
            )

            if ai_result is None:
                return self._io_manager.send_error(ai_error or "AI analysis was unsuccessful.", 502)

            # Assess travel planning first (if provided)
            travel_data = data.get("travel", {})
            assessment = self._logic_manager.assess_travel(travel_data, profile)
            travel_result = self._io_manager.sanitize_travel_result(assessment)

            # Build a privacy-safe summary snapshot for persistence (legs removed)
            travel_snapshot = dict(travel_result) if travel_result and travel_result.get("status") != "SKIPPED" else None
            if travel_snapshot:
                travel_snapshot["legs"] = None

            dest_postal = travel_data.get("destination_postal_code", "") if isinstance(travel_data, dict) else ""

            record = self._logic_manager.create_event_record(
                ai_result["ai_scores"],
                ai_result["event_category"],
                ai_result["ai_reasoning"],
                data["event_name"],
                data["event_description"],
                data["workload"],
                destination_postal_code=dest_postal,
                travel_snapshot=travel_snapshot,
            )

            all_events = self._data_manager.add_event(record)
            return self._io_manager.send_analysis(record, all_events, travel_result)
        except EventWiseError as exc:
            return self._io_manager.send_server_error(exc)

    def close(self) -> None:
        """Close DataManager connections."""
        self._data_manager.close()

    def run(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
        """Start the Flask web application."""
        self._app.run(host=host, port=port, debug=debug)


# Global application instance and Flask WSGI reference
eventwise = EventWise()
app = eventwise.app


def main() -> None:
    """Application main entrypoint."""
    eventwise.run()


if __name__ == "__main__":
    main()
