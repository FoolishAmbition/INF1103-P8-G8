"""DataManager: loads and saves records through an injected PersistenceStrategy.

Recovers gracefully from corrupt/missing files (returns empty/None and
does not crash), which the exception-handling matrix documents.
"""

from src.base_manager import BaseManager
from src.exceptions import DataCorruptionError
from src.storage import JsonStorage, PersistenceStrategy


class DataManager(BaseManager):
    PROFILE_KEY = "profile"
    EVENTS_KEY = "events"

    def __init__(self, storage: PersistenceStrategy | None = None):
        super().__init__(name="data")
        self._storage = storage or JsonStorage()

    def set_storage(self, strategy: PersistenceStrategy) -> None:
        self._storage = strategy

    # -- profile -------------------------------------------------------
    def load_profile(self):
        try:
            return self._storage.load(self.PROFILE_KEY)
        except DataCorruptionError:
            return None

    def save_profile(self, profile) -> None:
        self._storage.save(self.PROFILE_KEY, profile)

    # -- events --------------------------------------------------------
    def load_events(self) -> list:
        try:
            data = self._storage.load(self.EVENTS_KEY)
            return data if isinstance(data, list) else []
        except DataCorruptionError:
            return []

    def save_events(self, events: list) -> None:
        self._storage.save(self.EVENTS_KEY, events)

    def run(self) -> None:
        return None


# ----------------------------------------------------------------------
# Module-level wrappers (backward compatible with main.py)
# ----------------------------------------------------------------------
_default_data = DataManager()


def load_profile():
    return _default_data.load_profile()


def save_profile(profile):
    return _default_data.save_profile(profile)


def load_events():
    return _default_data.load_events()


def save_events(events):
    return _default_data.save_events(events)