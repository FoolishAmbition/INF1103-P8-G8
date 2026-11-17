"""LogicManager: applies business rules to AI-enriched records.

The class holds a RuleEngine and a ScoringStrategy (both injected).
"""

from datetime import datetime

from src.ai_scores import AIScores
from src.base_manager import BaseManager
from src.event_record import EventRecord
from src.exceptions import ValidationError
from src.geolocation_service import GeoLocationService
from src.journey_planner import JourneyPlanner
from src.rules import RuleEngine
from src.scoring import ScoringStrategy, StandardScoringStrategy
from src.student_profile import StudentProfile
from src.travel_result import TravelResult

class LogicManager(BaseManager):
    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        scoring: ScoringStrategy | None = None,
        journey_planner: JourneyPlanner | None = None,
    ):
        super().__init__(name="logic")
        self._rule_engine = rule_engine if rule_engine is not None else RuleEngine()
        self._scoring = scoring if scoring is not None else StandardScoringStrategy()
        self._journey_planner = (
            journey_planner
            if journey_planner is not None
            else JourneyPlanner(GeoLocationService())
        )

    # -- scoring --------------------------------------------------------
    def calculate_event_value(self, ai_scores: AIScores) -> int:
        return self._scoring.calculate(ai_scores)

    def event_priority(self, value: int) -> str:
        return self._scoring.priority_for(value)

    # -- decision -------------------------------------------------------
    def generate_recommendation(
        self, ai_scores: AIScores, workload: str, event_value: int
    ) -> str:
        return self._rule_engine.evaluate(ai_scores, workload, event_value)

    def generate_reason(self, recommendation: str, workload: str) -> str:
        if recommendation == "ATTEND":
            if workload == "Low":
                return "High value and your workload is manageable — go for it."
            return "Strong value; your workload is manageable enough to attend."
        if recommendation == "MAYBE":
            if workload == "High":
                return "Valuable event, but heavy commitments — consider carefully."
            return "Worth considering; weigh against your other plans."
        return "Low overall value relative to your workload — likely skip."

    # -- orchestration --------------------------------------------------
    def generate_summary(
        self,
        ai_scores: AIScores,
        event_category: str,
        ai_reasoning: str,
        workload: str,
    ) -> dict:
        value = self.calculate_event_value(ai_scores)
        recommendation = self.generate_recommendation(ai_scores, workload, value)
        summary = {
            "event_category": event_category,
            "career_relevance": ai_scores.career_relevance,
            "learning_value": ai_scores.learning_value,
            "networking_value": ai_scores.networking_value,
            "ai_reasoning": ai_reasoning,
            "ai_scores": ai_scores,
            "event_value": value,
            "priority": self.event_priority(value),
            "recommendation": recommendation,
            "reason": self.generate_reason(recommendation, workload),
        }
        return summary

    def create_event_record(
        self,
        ai_scores: AIScores,
        event_category: str,
        ai_reasoning: str,
        event_name: str,
        event_description: str,
        workload: str,
    ) -> EventRecord:
        """Apply event rules and construct the resulting domain record."""
        summary = self.generate_summary(
            ai_scores, event_category, ai_reasoning, workload
        )
        summary.update(
            event_name=event_name,
            event_description=event_description,
            workload=workload,
        )
        return EventRecord.from_dict(summary)

    def profile_is_ready(self, profile: StudentProfile) -> bool:
        """Return whether the profile has enough information for event analysis."""
        return not profile.is_empty()

    def assess_travel(
        self, travel: dict, profile: StudentProfile
    ) -> TravelResult | None:
        """Coordinate travel assessment without exposing transit data to AI."""
        event_start = None

        def unavailable(error_code):
            return TravelResult(
                status="UNAVAILABLE",
                feasibility="UNAVAILABLE",
                arrival_buffer_minutes=self._journey_planner.arrival_buffer_minutes,
                error_code=error_code,
                event_start=event_start,
                preferred_limit_minutes=self._journey_planner.preferred_limit_minutes,
            )

        if not isinstance(travel, dict):
            return unavailable("INVALID_INPUT")

        choice = travel.get("origin_choice", "skip")
        if choice == "skip":
            return None
        if choice not in ("home", "alternate"):
            return unavailable("INVALID_INPUT")

        origin = profile.home_postal_code
        if choice == "alternate":
            origin = travel.get("origin_postal_code")

        start_text = travel.get("event_start")
        if not isinstance(start_text, str):
            return unavailable("INVALID_INPUT")
        try:
            event_start = JourneyPlanner.to_singapore_datetime(
                datetime.fromisoformat(start_text), "Event start"
            )
        except (ValueError, ValidationError):
            return unavailable("INVALID_INPUT")

        assessment, _ = self._journey_planner.plan(
            origin, travel.get("destination_postal_code"), event_start
        )
        return assessment
