"""Abstract base class shared by the four managers."""

from abc import ABC


class BaseManager(ABC):
    """Shared base class for managers with a read-only name."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name