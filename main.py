"""
main.py
"""

from src.ai_manager import AIManager
from src.data_manager import DataManager
from src.io_manager import IOManager
from src.logic_manager import LogicManager
from src.models import EventRecord, StudentProfile


class EventWiseApp:
    """Main application orchestrator coordinating all managers."""

    MENU_CHOICES = [
        "Profile",
        "Analyse New Events",
        "View Analysed Events",
        "Add Dummy Event",
        "Exit",
    ]

    def __init__(self):
        self._io_manager = IOManager()
        self._ai_manager = AIManager()
        self._logic_manager = LogicManager()
        self._data_manager = DataManager()

        # Load persisted profile and events into domain entities
        self._profile = self._load_profile()
        self._events = self._load_events()

        # UI status messaging state
        self._status: str | None = None
        self._is_error: bool = False

    @property
    def profile(self) -> StudentProfile:
        return self._profile

    @property
    def events(self) -> list[EventRecord]:
        return self._events

    def _load_profile(self) -> StudentProfile:
        """Load profile from data storage into a StudentProfile entity."""
        data = self._data_manager.load_profile()
        if data and isinstance(data, dict):
            try:
                return StudentProfile.from_dict(data)
            except Exception:
                return StudentProfile()
        return StudentProfile()

    def _load_events(self) -> list[EventRecord]:
        """Load events from data storage into EventRecord entities."""
        raw_events = self._data_manager.load_events()
        events = []
        if isinstance(raw_events, list):
            for item in raw_events:
                if isinstance(item, EventRecord):
                    events.append(item)
                elif isinstance(item, dict):
                    try:
                        events.append(EventRecord.from_dict(item))
                    except Exception:
                        continue
        return events

    def _handle_exit(self) -> None:
        """Save user profile and events before closing the application."""
        if not self._profile.is_empty():
            self._data_manager.save_profile(self._profile.to_dict())

        if self._events:
            self._data_manager.save_events(
                [e.to_dict() if isinstance(e, EventRecord) else e for e in self._events]
            )

        self._io_manager.display_message("Goodbye!")

    def _handle_profile(self) -> None:
        """Allow user to view and edit their student profile."""
        updated = self._io_manager.collect_profile(self._profile)
        if updated is not self._profile:
            if isinstance(updated, dict):
                self._profile = StudentProfile.from_dict(updated)
            elif isinstance(updated, StudentProfile):
                self._profile = updated
            self._status = "Profile saved!"

    def _handle_analyse_event(self) -> None:
        """Prompt for event details, analyze with AI, evaluate rules, and save record."""
        if self._profile.is_empty():
            self._status = "Please create your profile first"
            self._is_error = True
            return

        event_info = self._io_manager.collect_event_info()
        if event_info is None:
            self._status = "Cancelled. No event was added."
            return

        event_name, event_description, workload = event_info

        # Check AI result
        ai_result, error_message = self._ai_manager.analyze_event(
            self._profile.to_dict(), event_name, event_description
        )
        if ai_result is None:
            self._status = error_message
            self._is_error = True
            return

        # Validate and process result through LogicManager
        event_summary, error_message = self._logic_manager.generate_summary(ai_result, workload)
        if event_summary is None:
            self._status = error_message
            self._is_error = True
            return

        event_summary |= {
            "event_name": event_name,
            "event_description": event_description,
            "workload": workload,
        }

        record = EventRecord.from_dict(event_summary)
        self._io_manager.display_event_summary(record)
        self._events.append(record)
        self._status = "Event analyzed successfully"

    def _handle_dummy_event(self) -> None:
        """Add a mock event for demonstration/testing without calling the AI API."""
        dummy_result = self._logic_manager.add_dummy_event()
        workload = dummy_result.get("workload", "Low")

        # Validate and process result through LogicManager
        event_summary, error_message = self._logic_manager.generate_summary(dummy_result, workload)
        if event_summary is None:
            self._status = error_message
            self._is_error = True
            return

        event_summary |= {
            "event_name": dummy_result.get("event_name", "Dummy Event"),
            "event_description": dummy_result.get(
                "event_description", "Randomly generated event (no API call)."
            ),
            "workload": workload,
        }

        record = EventRecord.from_dict(event_summary)
        self._io_manager.display_event_summary(record)
        self._events.append(record)
        self._status = "Dummy event added successfully"

    def _handle_view_events(self) -> None:
        """Display all analyzed events in a formatted table."""
        self._io_manager.display_event_list(self._events)

    def run(self) -> None:
        """Main application loop."""
        while True:
            choice = self._io_manager.get_main_menu_choice(
                self.MENU_CHOICES, self._status, self._is_error
            )

            # Reset status and error flag after displaying them
            self._status = None
            self._is_error = False

            match choice:
                case "Exit" | None:
                    self._handle_exit()
                    break

                case "Profile":
                    self._handle_profile()

                case "Analyse New Events":
                    self._handle_analyse_event()

                case "Add Dummy Event":
                    self._handle_dummy_event()

                case "View Analysed Events":
                    self._handle_view_events()


def main():
    app = EventWiseApp()
    app.run()


if __name__ == "__main__":
    main()
