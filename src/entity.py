from abc import ABC, abstractmethod

from src.exceptions import ValidationError


class Entity(ABC):
    """Abstract base class for all domain entities.

    Every entity must be able to turn itself into a dictionary,
    and inherits common validation helpers.
    """

    @abstractmethod
    def to_dict(self):
        pass

    def __repr__(self):
        return type(self).__name__ + str(self.to_dict())

    # -- Helper functions accessible to all subclasses -----------------

    @staticmethod
    def clean_text(value, name):
        """Make sure value is a string, and remove spaces from both ends."""
        if not isinstance(value, str):
            raise ValidationError(f"{name} must be a string, got {type(value).__name__}.")
        return value.strip()

    @staticmethod
    def check_score(value, name):
        """Make sure value is a whole number from 1 to 5."""
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(f"{name} must be an integer, got {type(value).__name__}.")
        if value < 1 or value > 5:
            raise ValidationError(f"{name} must be between 1 and 5, got {value}.")
        return value

    @staticmethod
    def check_is_dict(data, class_name):
        """Make sure data is a dictionary."""
        if not isinstance(data, dict):
            raise ValidationError(
                f"Cannot create {class_name}: expected dict, got {type(data).__name__}."
            )



