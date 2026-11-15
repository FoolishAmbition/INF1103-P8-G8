"""DataManager: loads and saves records through an injected PersistenceStrategy.

Recovers gracefully from corrupt or missing records, handling translation
between storage dictionaries and domain entities (StudentProfile, EventRecord).
"""

from src.base_manager import BaseManager
from src.event_record import EventRecord
from src.exceptions import DatabaseError, DataCorruptionError
from src.storage import JsonStorage, PersistenceStrategy
from src.student_profile import StudentProfile


class DataManager(BaseManager):
    PROFILE_KEY = "profile"
    EVENTS_KEY = "events"

    def __init__(self, storage: PersistenceStrategy | None = None):
        super().__init__(name="data")
        self._storage = storage or JsonStorage()

    def set_storage(self, strategy: PersistenceStrategy) -> None:
        self._storage = strategy

    # -- Profile Operations --------------------------------------------
    def get_profile(self) -> StudentProfile:
        """Load and deserialize the student profile entity from storage."""
        try:
            raw = self._storage.load(self.PROFILE_KEY)
            if isinstance(raw, StudentProfile):
                return raw
            if isinstance(raw, dict):
                return StudentProfile.from_dict(raw)
        except (DatabaseError, DataCorruptionError, TypeError, ValueError, KeyError):
            pass
        return StudentProfile()

    def save_profile(self, profile: StudentProfile | dict) -> None:
        """Persist the student profile entity to storage."""
        try:
            payload = profile.to_dict() if hasattr(profile, "to_dict") else profile
            self._storage.save(self.PROFILE_KEY, payload)
        except (DatabaseError, DataCorruptionError):
            pass

    def load_profile(self) -> StudentProfile:
        """Backward-compatible alias for get_profile()."""
        return self.get_profile()

    # -- Event Operations ----------------------------------------------
    def get_events(self) -> list[EventRecord]:
        """Load and deserialize event records from storage."""
        try:
            raw_events = self._storage.load(self.EVENTS_KEY)
            if not isinstance(raw_events, list):
                return []
            events: list[EventRecord] = []
            for item in raw_events:
                try:
                    event = item if isinstance(item, EventRecord) else EventRecord.from_dict(item)
                    events.append(event)
                except (TypeError, ValueError, KeyError):
                    continue
            return events
        except (DatabaseError, DataCorruptionError):
            return []

    def save_events(self, events: list[EventRecord | dict]) -> None:
        """Persist a list of event records to storage."""
        try:
            payload = [
                e.to_dict() if hasattr(e, "to_dict") else e
                for e in events
            ]
            self._storage.save(self.EVENTS_KEY, payload)
        except (DatabaseError, DataCorruptionError):
            pass

    def add_event(self, event: EventRecord | dict) -> list[EventRecord]:
        """Add a single event record, persist all events, and return the updated event list."""
        record = event if isinstance(event, EventRecord) else EventRecord.from_dict(event)
        events = self.get_events()
        events.append(record)
        self.save_events(events)
        return events

    def load_events(self) -> list[EventRecord]:
        """Backward-compatible alias for get_events()."""
        return self.get_events()

    def close(self) -> None:
        """Close underlying storage connection if supported."""
        if hasattr(self._storage, "close") and callable(self._storage.close):
            self._storage.close()

    def run(self) -> None:
        return None
