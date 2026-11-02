"""LogicManager: applies business rules to AI-enriched records.

The class holds a RuleEngine and a ScoringStrategy (both injected).
Module-level functions are kept as thin wrappers so existing callers
(main.py and test_logic_manager.py) keep working during the refactor.
"""

import random

from src.base_manager import BaseManager
from src.rules import RuleEngine
from src.scoring import ScoringStrategy, StandardScoringStrategy


VALID_FIELDS = (
    "event_category",
    "career_relevance",
    "learning_value",
    "networking_value",
    "ai_reasoning",
)
SCORE_FIELDS = ("career_relevance", "learning_value", "networking_value")


class LogicManager(BaseManager):
    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        scoring: ScoringStrategy | None = None,
    ):
        super().__init__(name="logic")
        self._rule_engine = rule_engine or RuleEngine()
        self._scoring = scoring or StandardScoringStrategy()

    # -- validation -----------------------------------------------------
    def validate_ai_result(self, ai_result: dict) -> bool:
        if not isinstance(ai_result, dict):
            return False
        for field in VALID_FIELDS:
            if field not in ai_result:
                return False
        if not isinstance(ai_result["event_category"], str) or not ai_result[
            "event_category"
        ].strip():
            return False
        if not isinstance(ai_result["ai_reasoning"], str):
            return False
        for field in SCORE_FIELDS:
            value = ai_result[field]
            if type(value) is not int:   # rejects bool, float, str
                return False
            if not (1 <= value <= 5):
                return False
        return True

    # -- scoring --------------------------------------------------------
    def calculate_event_value(self, ai_result: dict) -> int:
        return self._scoring.calculate(ai_result)

    def event_priority(self, value: int) -> str:
        return self._scoring.priority_for(value)

    # -- decision -------------------------------------------------------
    def generate_recommendation(self, ai_result: dict, workload: str) -> str:
        return self._rule_engine.evaluate(ai_result, workload)

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
    def generate_summary(self, ai_result: dict, workload: str):
        if not self.validate_ai_result(ai_result):
            return None, "Invalid AI response: missing or malformed fields."
        value = self.calculate_event_value(ai_result)
        recommendation = self.generate_recommendation(ai_result, workload)
        summary = {
            "event_category": ai_result["event_category"],
            "career_relevance": ai_result["career_relevance"],
            "learning_value": ai_result["learning_value"],
            "networking_value": ai_result["networking_value"],
            "ai_reasoning": ai_result["ai_reasoning"],
            "event_value": value,
            "priority": self.event_priority(value),
            "recommendation": recommendation,
            "reason": self.generate_reason(recommendation, workload),
        }
        return summary, None

    def add_dummy_event(self) -> dict:
        categories = [
            "Technical Workshop",
            "Career Talk",
            "Networking Session",
            "Club Activity",
            "Hackathon",
        ]
        workloads = ["Low", "Medium", "High"]
        return {
            "event_category": random.choice(categories),
            "career_relevance": random.randint(1, 5),
            "learning_value": random.randint(1, 5),
            "networking_value": random.randint(1, 5),
            "ai_reasoning": "Dummy event generated for demonstration/testing.",
            "event_name": "Dummy Event",
            "event_description": "Randomly generated event (no API call).",
            "workload": random.choice(workloads),
        }

    # -- BaseManager contract ------------------------------------------
    def run(self) -> None:
        # LogicManager has no interactive loop; presence satisfies the ABC.
        return None


# ----------------------------------------------------------------------
# Module-level wrappers (backward compatible with main.py + tests)
# ----------------------------------------------------------------------
_default_logic = LogicManager()


def validate_ai_result(ai_result: dict) -> bool:
    return _default_logic.validate_ai_result(ai_result)


def calculate_event_value(ai_result: dict) -> int:
    return _default_logic.calculate_event_value(ai_result)


def event_priority(value: int) -> str:
    return _default_logic.event_priority(value)


def generate_recommendation(ai_result: dict, workload: str) -> str:
    return _default_logic.generate_recommendation(ai_result, workload)


def generate_reason(recommendation: str, workload: str) -> str:
    return _default_logic.generate_reason(recommendation, workload)


def generate_summary(ai_result: dict, workload: str):
    return _default_logic.generate_summary(ai_result, workload)


def format_scores(career: int, learning: int, networking: int) -> dict:
    return {
        "career_relevance": f"{career}/5",
        "learning_value": f"{learning}/5",
        "networking_value": f"{networking}/5",
    }


def add_dummy_event() -> dict:
    return _default_logic.add_dummy_event()