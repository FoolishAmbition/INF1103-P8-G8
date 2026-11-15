from src.entity import Entity
from src.exceptions import ValidationError


class AIScores(Entity):
    def __init__(self, career_relevance, learning_value, networking_value):
        self._career_relevance = self.check_score(career_relevance, "career_relevance")
        self._learning_value = self.check_score(learning_value, "learning_value")
        self._networking_value = self.check_score(networking_value, "networking_value")

    @property
    def career_relevance(self):
        return self._career_relevance

    @property
    def learning_value(self):
        return self._learning_value

    @property
    def networking_value(self):
        return self._networking_value

    @property
    def total_value(self):
        """Sum of the three scores (3 to 15)."""
        return self.career_relevance + self.learning_value + self.networking_value

    def to_dict(self):
        return {
            "career_relevance": self.career_relevance,
            "learning_value": self.learning_value,
            "networking_value": self.networking_value,
        }

    @classmethod
    def from_dict(cls, data):
        cls.check_is_dict(data, "AIScores")
        for key in ("career_relevance", "learning_value", "networking_value"):
            if key not in data:
                raise ValidationError(f"Missing required score field: {key}")
        return cls(
            data["career_relevance"],
            data["learning_value"],
            data["networking_value"],
        )

    def __eq__(self, other):
        if not isinstance(other, AIScores):
            return False
        return self.to_dict() == other.to_dict()
