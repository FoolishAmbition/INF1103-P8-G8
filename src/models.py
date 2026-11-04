"""
1.StudentProfile: student degree and interests.
2.AIScores: three AI scores, each from 1 to 5.
3.EventRecord: an event with workload, AI scores, recommendation, timestamp.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from src.exceptions import ValidationError

VALID_WORKLOADS = ("Low", "Medium", "High")


# -- Small helper functions ---------------------------------------------

def clean_text(value, name):
    """Make sure value is a string, and remove spaces from both ends."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}.")
    return value.strip()


def check_score(value, name):
    """Make sure value is a whole number from 1 to 5."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer, got {type(value).__name__}.")
    if value < 1 or value > 5:
        raise ValidationError(f"{name} must be between 1 and 5, got {value}.")
    return value


def check_is_dict(data, class_name):
    if not isinstance(data, dict):
        raise ValidationError(
            f"Cannot create {class_name}: expected dict, got {type(data).__name__}."
        )


# -- Abstract base class ------------------------------------------------

class Entity(ABC):
    """Every entity must be able to turn itself into a dictionary."""

    @abstractmethod
    def to_dict(self):
        pass

    def __repr__(self):
        return type(self).__name__ + str(self.to_dict())


# -- StudentProfile -----------------------------------------------------

class StudentProfile(Entity):
    def __init__(self, field_of_study="", interests=None):
        self.field_of_study = clean_text(field_of_study, "field_of_study")
        self.interests = []

        if interests is not None:
            if not isinstance(interests, (list, tuple, set)):
                raise ValidationError(
                    f"interests must be a list of strings, got {type(interests).__name__}."
                )
            for item in interests:
                text = clean_text(item, "interest")
                if text != "" and not self.has_interest(text):
                    self.interests.append(text)

    def has_interest(self, text):
        """Check if the interest is already in the list (ignores upper/lower case)."""
        for existing in self.interests:
            if existing.lower() == text.lower():
                return True
        return False

    def add_interest(self, interest):
        text = clean_text(interest, "interest")
        if text == "":
            raise ValidationError("Interest cannot be empty.")
        if self.has_interest(text):
            raise ValidationError(f"That interest is already in your list: '{text}'.")
        self.interests.append(text)

    def remove_interest(self, interest):
        text = clean_text(interest, "interest")
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
        }

    # Lets dictionary-like access like profile["field_of_study"] or profile.get(...) work
    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()
        check_is_dict(data, "StudentProfile")
        return cls(data.get("field_of_study", ""), data.get("interests", []))

    def __eq__(self, other):
        if not isinstance(other, StudentProfile):
            return False
        return self.to_dict() == other.to_dict()


# -- AIScores -----------------------------------------------------------

class AIScores(Entity):
    def __init__(self, career_relevance, learning_value, networking_value):
        self.career_relevance = check_score(career_relevance, "career_relevance")
        self.learning_value = check_score(learning_value, "learning_value")
        self.networking_value = check_score(networking_value, "networking_value")

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
        check_is_dict(data, "AIScores")
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


# -- EventRecord --------------------------------------------------------

class EventRecord(Entity):
    def __init__(
        self,
        event_name,
        event_description,
        workload,
        ai_scores=None,
        recommendation="",
        timestamp=None,
        event_category="",
        ai_reasoning="",
        reason="",
        priority="",
        event_value=None,
    ):
        # Text fields
        self.event_name = clean_text(event_name, "event_name")
        self.event_description = clean_text(event_description, "event_description")
        self.event_category = clean_text(event_category, "event_category")
        self.ai_reasoning = clean_text(ai_reasoning, "ai_reasoning")
        self.reason = clean_text(reason, "reason")
        self.recommendation = clean_text(recommendation, "recommendation").upper()

        # Workload: must be Low, Medium or High (empty means Low)
        workload_text = clean_text(workload, "workload").capitalize()
        if workload_text != "" and workload_text not in VALID_WORKLOADS:
            raise ValidationError(f"Invalid workload '{workload}'. Allowed: {VALID_WORKLOADS}.")
        if workload_text == "":
            workload_text = "Low"
        self.workload = workload_text

        # AI scores: can be an AIScores object, a dict, or None
        if isinstance(ai_scores, dict):
            ai_scores = AIScores.from_dict(ai_scores)
        elif ai_scores is not None and not isinstance(ai_scores, AIScores):
            raise ValidationError(
                f"ai_scores must be an AIScores or dict, got {type(ai_scores).__name__}."
            )
        self.ai_scores = ai_scores

        # Timestamp: if nothing is given, use the current time
        if isinstance(timestamp, str):
            timestamp = timestamp.strip()
        if timestamp is None or timestamp == "":
            timestamp = datetime.now(timezone.utc).isoformat()
        elif isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        elif not isinstance(timestamp, str):
            raise ValidationError(
                f"timestamp must be a datetime, string, or None, got {type(timestamp).__name__}."
            )
        self.timestamp = timestamp

        # event_value must be a whole number (or None)
        if event_value is not None and (not isinstance(event_value, int) or isinstance(event_value, bool)):
            raise ValidationError(
                f"event_value must be an int or None, got {type(event_value).__name__}."
            )

        # Work out priority and event_value from the scores if they were not given
        priority = clean_text(priority, "priority").capitalize()
        if ai_scores is not None:
            total = ai_scores.total_value
            if event_value is None:
                event_value = total
            if priority == "":
                if total >= 11:
                    priority = "High"
                elif total >= 7:
                    priority = "Medium"
                else:
                    priority = "Low"
        self.priority = priority
        self.event_value = event_value

        # Copies of the individual scores (None if there are no scores)
        if ai_scores is not None:
            self.career_relevance = ai_scores.career_relevance
            self.learning_value = ai_scores.learning_value
            self.networking_value = ai_scores.networking_value
        else:
            self.career_relevance = None
            self.learning_value = None
            self.networking_value = None

    # Lets old code like record["event_name"] or record.get("event_name") still work
    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    def to_dict(self):
        if self.ai_scores is not None:
            scores_dict = self.ai_scores.to_dict()
        else:
            scores_dict = None

        return {
            "event_name": self.event_name,
            "event_description": self.event_description,
            "workload": self.workload,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
            "event_category": self.event_category,
            "ai_reasoning": self.ai_reasoning,
            "reason": self.reason,
            "priority": self.priority,
            "event_value": self.event_value,
            "career_relevance": self.career_relevance,
            "learning_value": self.learning_value,
            "networking_value": self.networking_value,
            "ai_scores": scores_dict,
        }

    @classmethod
    def from_dict(cls, data):
        check_is_dict(data, "EventRecord")

        scores = data.get("ai_scores")
        # Older format: the three scores are stored directly in the dict
        if not isinstance(scores, dict) and data.get("career_relevance") is not None:
            scores = {
                "career_relevance": data.get("career_relevance"),
                "learning_value": data.get("learning_value"),
                "networking_value": data.get("networking_value"),
            }

        return cls(
            event_name=data.get("event_name", ""),
            event_description=data.get("event_description", ""),
            workload=data.get("workload", "Low"),
            ai_scores=scores,
            recommendation=data.get("recommendation", ""),
            timestamp=data.get("timestamp"),
            event_category=data.get("event_category", ""),
            ai_reasoning=data.get("ai_reasoning", ""),
            reason=data.get("reason", ""),
            priority=data.get("priority", ""),
            event_value=data.get("event_value"),
        )

    def __eq__(self, other):
        if not isinstance(other, EventRecord):
            return False
        return (
            self.event_name == other.event_name
            and self.event_description == other.event_description
            and self.workload == other.workload
            and self.ai_scores == other.ai_scores
            and self.recommendation == other.recommendation
        )