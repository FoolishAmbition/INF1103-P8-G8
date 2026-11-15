from src.entity import Entity
from src.exceptions import ValidationError
from src.geolocation import validate_singapore_postal_code


class StudentProfile(Entity):
    def __init__(self, field_of_study="", interests=None, home_postal_code=""):
        self.field_of_study = self.clean_text(field_of_study, "field_of_study")
        self.interests = []
        # Older saved profiles have no postal code. Empty means it is unset.
        if home_postal_code is None:
            home_postal_code = ""
        if home_postal_code != "":
            validate_singapore_postal_code(home_postal_code)
        self.home_postal_code = home_postal_code

        if interests is not None:
            if not isinstance(interests, (list, tuple, set)):
                raise ValidationError(
                    f"interests must be a list of strings, got {type(interests).__name__}."
                )
            for item in interests:
                text = self.clean_text(item, "interest")
                if text != "" and not self.has_interest(text):
                    self.interests.append(text)

    def has_interest(self, text):
        """Check if the interest is already in the list (ignores upper/lower case)."""
        for existing in self.interests:
            if existing.lower() == text.lower():
                return True
        return False

    def add_interest(self, interest):
        text = self.clean_text(interest, "interest")
        if text == "":
            raise ValidationError("Interest cannot be empty.")
        if self.has_interest(text):
            raise ValidationError(f"That interest is already in your list: '{text}'.")
        self.interests.append(text)

    def remove_interest(self, interest):
        text = self.clean_text(interest, "interest")
        for existing in self.interests:
            if existing.lower() == text.lower():
                self.interests.remove(existing)
                return
        raise ValidationError(f"Interest '{interest}' not found in profile.")

    def is_empty(self):
        return self.field_of_study == "" and len(self.interests) == 0

    def to_dict(self):
        return {
            "field_of_study": self.field_of_study,
            "interests": list(self.interests),
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
