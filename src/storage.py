"""Persistence strategies behind one interface (LSP + OCP for the DB option)."""

import json
import os
from abc import ABC, abstractmethod

from src.exceptions import DataCorruptionError


class PersistenceStrategy(ABC):
    @abstractmethod
    def save(self, key: str, data) -> None:
        raise NotImplementedError

    @abstractmethod
    def load(self, key: str):
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError


class JsonStorage(PersistenceStrategy):
    def __init__(self, base_dir: str = "data"):
        self._base_dir = base_dir
        os.makedirs(self._base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self._base_dir, f"{key}.json")

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def save(self, key: str, data) -> None:
        try:
            with open(self._path(key), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            raise DataCorruptionError(f"Could not write {key}: {exc}") from exc

    def load(self, key: str):
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise DataCorruptionError(f"Corrupt data file {path}: {exc}") from exc