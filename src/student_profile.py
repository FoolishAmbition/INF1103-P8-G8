from src.entity import Entity
from src.exceptions import ValidationError
from src.transit_routing_service import TransitRoutingService


class StudentProfile(Entity):
    def __init__(self, field_of_study="", interests=None, home_postal_code=""):
        self._field_of_study = self.clean_text(field_of_study, "field_of_study")
        self._interests = []
        # Older saved profiles have no postal code. Empty means it is unset.
        if home_postal_code is None:
            home_postal_code = ""
        if home_postal_code != "":
            self.validate_singapore_postal_code(home_postal_code)
        self._home_postal_code = home_postal_code

        if interests is not None:
            if not isinstance(interests, (list, tuple, set)):
                raise ValidationError(
                    f"interests must be a list of strings, got {type(interests).__name__}."
                )
            for item in interests:
                text = self.clean_text(item, "interest")
                if text != "" and not self.has_interest(text):
                    self._interests.append(text)

    @property
    def field_of_study(self):
        return self._field_of_study

    @property
    def interests(self):
        return list(self._interests)

    @property
    def home_postal_code(self):
        return self._home_postal_code

    def has_interest(self, text):
        """Check if the interest is already in the list (ignores upper/lower case)."""
        for existing in self._interests:
            if existing.lower() == text.lower():
                return True
        return False

    def add_interest(self, interest):
        text = self.clean_text(interest, "interest")
        if text == "":
            raise ValidationError("Interest cannot be empty.")
        if self.has_interest(text):
            raise ValidationError(f"That interest is already in your list: '{text}'.")
        self._interests.append(text)

    def remove_interest(self, interest):
        text = self.clean_text(interest, "interest")
        for existing in self._interests:
            if existing.lower() == text.lower():
                self._interests.remove(existing)
                return
        raise ValidationError(f"Interest '{interest}' not found in profile.")

    @staticmethod
    def validate_singapore_postal_code(postal_code: str) -> str:
        return TransitRoutingService.validate_singapore_postal_code(postal_code)

    def is_empty(self):
        return self.field_of_study == "" and len(self._interests) == 0

    def to_dict(self):
        return {
            "field_of_study": self.field_of_study,
            "interests": list(self._interests),
            "home_postal_code": self.home_postal_code,
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()
        cls.check_is_dict(data, "StudentProfile")
        return cls(
            field_of_study=data.get("field_of_study", ""),
            interests=data.get("interests", []),
            home_postal_code=data.get("home_postal_code", ""),
        )

    def __eq__(self, other):
        if not isinstance(other, StudentProfile):
            return False
        return self.to_dict() == other.to_dict()
