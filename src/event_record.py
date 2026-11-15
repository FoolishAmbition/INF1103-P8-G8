from datetime import datetime, timezone

from src.ai_scores import AIScores
from src.entity import Entity
from src.exceptions import ValidationError

VALID_WORKLOADS = ("Low", "Medium", "High")


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
        self.event_name = self.clean_text(event_name, "event_name")
        self.event_description = self.clean_text(event_description, "event_description")
        self.event_category = self.clean_text(event_category, "event_category")
        self.ai_reasoning = self.clean_text(ai_reasoning, "ai_reasoning")
        self.reason = self.clean_text(reason, "reason")
        self.recommendation = self.clean_text(recommendation, "recommendation").upper()

        # Workload: must be Low, Medium or High (empty means Low)
        workload_text = self.clean_text(workload, "workload").capitalize()
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
        priority = self.clean_text(priority, "priority").capitalize()
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

    @property
    def career_relevance(self):
        return self.ai_scores.career_relevance if self.ai_scores else None

    @property
    def learning_value(self):
        return self.ai_scores.learning_value if self.ai_scores else None

    @property
    def networking_value(self):
        return self.ai_scores.networking_value if self.ai_scores else None

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
        cls.check_is_dict(data, "EventRecord")

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
