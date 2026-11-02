"""Business rules as first-class objects.

Each Rule is an independent class extending the Rule ABC. The RuleEngine
iterates registered rules in priority order and returns the first match.
Adding a new rule requires only a new subclass + registration (OCP).
"""

from abc import ABC, abstractmethod


def _event_value(ai_result: dict) -> int:
    return (
        ai_result["career_relevance"]
        + ai_result["learning_value"]
        + ai_result["networking_value"]
    )


class Rule(ABC):
    """Abstract contract: does this rule match, and what does it recommend?"""

    recommendation: str = ""

    @abstractmethod
    def matches(self, ai_result: dict, workload: str) -> bool:
        raise NotImplementedError

    def get_recommendation(self) -> str:
        return self.recommendation


class TopScoresRule(Rule):
    recommendation = "ATTEND"

    def matches(self, ai_result: dict, workload: str) -> bool:
        return (
            ai_result["career_relevance"] >= 4
            and ai_result["learning_value"] >= 4
            and workload in ("Low", "Medium")
        )


class HighValueLowWorkloadRule(Rule):
    recommendation = "ATTEND"

    def matches(self, ai_result: dict, workload: str) -> bool:
        return _event_value(ai_result) >= 11 and workload in ("Low", "Medium")


class HighValueHighWorkloadRule(Rule):
    recommendation = "MAYBE"

    def matches(self, ai_result: dict, workload: str) -> bool:
        return _event_value(ai_result) >= 11 and workload == "High"


class MidValueLowWorkloadRule(Rule):
    recommendation = "MAYBE"

    def matches(self, ai_result: dict, workload: str) -> bool:
        return _event_value(ai_result) >= 8 and workload in ("Low", "Medium")


class MidValueHighWorkloadRule(Rule):
    recommendation = "SKIP"

    def matches(self, ai_result: dict, workload: str) -> bool:
        return _event_value(ai_result) >= 8 and workload == "High"


class LowValueRule(Rule):
    recommendation = "SKIP"

    def matches(self, ai_result: dict, workload: str) -> bool:
        # Catch-all: fires only if nothing above matched.
        return True


class RuleEngine:
    """Ordered collection of Rules; evaluates first match."""

    def __init__(self, rules: list[Rule] | None = None):
        self._rules: list[Rule] = rules if rules is not None else self._default_rules()

    @staticmethod
    def _default_rules() -> list[Rule]:
        return [
            TopScoresRule(),
            HighValueLowWorkloadRule(),
            HighValueHighWorkloadRule(),
            MidValueLowWorkloadRule(),
            MidValueHighWorkloadRule(),
            LowValueRule(),
        ]

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def evaluate(self, ai_result: dict, workload: str) -> str:
        for rule in self._rules:
            if rule.matches(ai_result, workload):
                return rule.get_recommendation()
        return "SKIP"