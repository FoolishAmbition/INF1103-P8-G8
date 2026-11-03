"""Abstract base class shared by the four managers."""

from abc import ABC, abstractmethod


class BaseManager(ABC):
    """Every manager has a name, can describe itself, and exposes run()."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def describe(self) -> str:
        return f"{self.__class__.__name__}(name={self._name!r})"

    @abstractmethod
    def run(self) -> None:
        """Entry point for the manager's primary responsibility."""
        raise NotImplementedError