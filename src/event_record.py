from datetime import datetime, timezone

from src.ai_scores import AIScores
from src.entity import Entity
from src.exceptions import ValidationError

VALID_WORKLOADS = ("Low", "Medium", "High")
VALID_PRIORITIES = ("Low", "Medium", "High")
VALID_RECOMMENDATIONS = ("ATTEND", "MAYBE", "SKIP")


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
        self._event_name = self.clean_text(event_name, "event_name")
        self._event_description = self.clean_text(event_description, "event_description")
        self._event_category = self.clean_text(event_category, "event_category")
        self._ai_reasoning = self.clean_text(ai_reasoning, "ai_reasoning")
        self._reason = self.clean_text(reason, "reason")
        self._recommendation = self.clean_text(recommendation, "recommendation")
        if self._recommendation not in VALID_RECOMMENDATIONS:
            raise ValidationError(
                f"Invalid recommendation '{self._recommendation}'. "
                f"Allowed: {VALID_RECOMMENDATIONS}."
            )

        workload_text = self.clean_text(workload, "workload")
        if workload_text not in VALID_WORKLOADS:
            raise ValidationError(
                f"Invalid workload '{workload_text}'. Allowed: {VALID_WORKLOADS}."
            )
        self._workload = workload_text

        # Accept the domain object or its serialized form.
        if isinstance(ai_scores, dict):
            ai_scores = AIScores.from_dict(ai_scores)
        elif ai_scores is not None and not isinstance(ai_scores, AIScores):
            raise ValidationError(
                f"ai_scores must be an AIScores or dict, got {type(ai_scores).__name__}."
            )
        if ai_scores is None:
            raise ValidationError("ai_scores is required for an EventRecord.")
        self._ai_scores = ai_scores

        self._timestamp = self._normalize_timestamp(timestamp)

        if event_value is not None:
            if not isinstance(event_value, int) or isinstance(event_value, bool):
                raise ValidationError(
                    f"event_value must be an integer, got {type(event_value).__name__}."
                )
            if not 3 <= event_value <= 15:
                raise ValidationError("event_value must be between 3 and 15.")

        total = ai_scores.total_value
        if event_value is None:
            event_value = total
        elif event_value != total:
            raise ValidationError(
                f"event_value must equal the AIScores total ({total})."
            )

        priority = self.clean_text(priority, "priority")
        if not priority:
            if event_value >= 11:
                priority = "High"
            elif event_value >= 7:
                priority = "Medium"
            else:
                priority = "Low"
        if priority not in VALID_PRIORITIES:
            raise ValidationError(
                f"Invalid priority '{priority}'. Allowed: {VALID_PRIORITIES}."
            )
        expected_priority = (
            "High" if event_value >= 11 else "Medium" if event_value >= 7 else "Low"
        )
        if priority != expected_priority:
            raise ValidationError(
                f"Priority '{priority}' does not match event_value {event_value}."
            )

        self._priority = priority
        self._event_value = event_value

    @property
    def event_name(self):
        return self._event_name

    @property
    def event_description(self):
        return self._event_description

    @property
    def workload(self):
        return self._workload

    @property
    def ai_scores(self):
        return self._ai_scores

    @property
    def recommendation(self):
        return self._recommendation

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def event_category(self):
        return self._event_category

    @property
    def ai_reasoning(self):
        return self._ai_reasoning

    @property
    def reason(self):
        return self._reason

    @property
    def priority(self):
        return self._priority

    @property
    def event_value(self):
        return self._event_value

    @property
    def career_relevance(self):
        return self.ai_scores.career_relevance if self.ai_scores else None

    @property
    def learning_value(self):
        return self.ai_scores.learning_value if self.ai_scores else None

    @property
    def networking_value(self):
        return self.ai_scores.networking_value if self.ai_scores else None

    @staticmethod
    def _normalize_timestamp(timestamp):
        if timestamp is None:
            value = datetime.now(timezone.utc)
        elif isinstance(timestamp, datetime):
            value = timestamp
        elif isinstance(timestamp, str):
            timestamp = timestamp.strip()
            if not timestamp:
                return datetime.now(timezone.utc).isoformat()
            try:
                value = datetime.fromisoformat(timestamp.strip())
            except ValueError as exc:
                raise ValidationError("timestamp must be a valid ISO 8601 datetime.") from exc
        else:
            raise ValidationError(
                f"timestamp must be a datetime, string, or None, got {type(timestamp).__name__}."
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError("timestamp must include timezone information.")
        try:
            return value.astimezone(timezone.utc).isoformat()
        except (OverflowError, ValueError) as exc:
            raise ValidationError("timestamp exceeds the supported date range.") from exc

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
            "ai_scores": scores_dict,
        }

    @classmethod
    def from_dict(cls, data):
        cls.check_is_dict(data, "EventRecord")

        scores = data.get("ai_scores")

        return cls(
            event_name=data.get("event_name", ""),
            event_description=data.get("event_description", ""),
            workload=data.get("workload"),
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
