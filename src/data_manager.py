"""DataManager: loads and saves records through an injected PersistenceStrategy.

Recovers gracefully from corrupt or missing records, handling translation
between storage dictionaries and domain entities (StudentProfile, EventRecord).
"""

import logging

from src.base_manager import BaseManager
from src.analytics_reporter import AnalyticsReporter
from src.event_filter import EventFilter
from src.event_record import EventRecord
from src.exceptions import DataCorruptionError, DatabaseError
from src.mongodb_storage import MongoStorage
from src.storage import JsonStorage, PersistenceStrategy
from src.student_profile import StudentProfile

_LOGGER = logging.getLogger(__name__)


class DataManager(BaseManager):
    PROFILE_KEY = "profile"
    EVENTS_KEY = "events"

    def __init__(
        self,
        storage: PersistenceStrategy | None = None,
        event_filter: EventFilter | None = None,
        analytics_reporter: AnalyticsReporter | None = None,
    ):
        super().__init__(name="data")
        if storage is not None:
            self._storage = storage
        else:
            try:
                self._storage = MongoStorage()
            except DatabaseError:
                _LOGGER.warning("MongoDB unavailable; falling back to JSON storage.")
                self._storage = JsonStorage()
        self._event_filter = event_filter or EventFilter()
        self._analytics_reporter = analytics_reporter or AnalyticsReporter()

    def set_storage(self, strategy: PersistenceStrategy) -> None:
        self._storage = strategy

    def get_profile(self) -> StudentProfile:
        """Load and deserialize the student profile entity from storage."""
        raw = self._storage.load(self.PROFILE_KEY)
        if raw is None:
            return StudentProfile()
        if not isinstance(raw, dict):
            raise DataCorruptionError("Stored student profile has an invalid structure.")
        try:
            return StudentProfile.from_dict(raw)
        except (TypeError, ValueError, KeyError) as exc:
            raise DataCorruptionError("Stored student profile is invalid.") from exc

    def save_profile(self, profile: StudentProfile) -> None:
        """Persist the student profile entity to storage."""
        self._storage.save(self.PROFILE_KEY, profile.to_dict())

    def update_profile(self, profile_data: dict) -> StudentProfile:
        """Merge a validated profile update with stored data and persist it."""
        existing_profile = self.get_profile()
        home_postal_code = profile_data["home_postal_code"]
        if home_postal_code is None:
            home_postal_code = existing_profile.home_postal_code

        profile = StudentProfile.from_dict({
            "field_of_study": profile_data["field_of_study"],
            "interests": profile_data["interests"],
            "home_postal_code": home_postal_code,
        })
        self.save_profile(profile)
        return profile

    def get_events(self) -> list[EventRecord]:
        """Load and deserialize event records from storage."""
        raw_events = self._storage.load(self.EVENTS_KEY)
        if raw_events is None:
            return []
        if not isinstance(raw_events, list):
            raise DataCorruptionError("Stored events have an invalid structure.")

        events: list[EventRecord] = []
        for index, item in enumerate(raw_events):
            try:
                events.append(EventRecord.from_dict(item))
            except (TypeError, ValueError, KeyError) as exc:
                raise DataCorruptionError(
                    f"Stored event at position {index} is invalid."
                ) from exc
        return events

    def filter_events(
        self,
        *,
        keyword: str | None = None,
        recommended: str | None = None,
        min_score: int | float | None = None,
    ) -> list[EventRecord]:
        """Load events and delegate search criteria to EventFilter."""
        return self._event_filter.filter(
            keyword=keyword,
            recommended=recommended,
            min_score=min_score,
            events=self.get_events(),
        )

    def get_analytics_summary(self) -> dict:
        """Load events and delegate statistics aggregation to AnalyticsReporter."""
        return self._analytics_reporter.generate_summary(events=self.get_events())

    def save_events(self, events: list[EventRecord]) -> None:
        """Persist a list of event records to storage."""
        self._storage.save(
            self.EVENTS_KEY,
            [event.to_dict() for event in events],
        )

    def add_event(self, event: EventRecord) -> list[EventRecord]:
        """Add a single event record, persist all events, and return the updated event list."""
        events = self.get_events()
        events.append(event)
        self.save_events(events)
        return events

    def close(self) -> None:
        """Close the storage connection when the strategy uses one."""
        self._storage.close()
