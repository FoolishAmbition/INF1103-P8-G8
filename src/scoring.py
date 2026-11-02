"""Scoring strategies: interchangeable implementations behind one interface."""

from abc import ABC, abstractmethod


class ScoringStrategy(ABC):
    @abstractmethod
    def calculate(self, ai_result: dict) -> int:
        raise NotImplementedError

    @abstractmethod
    def priority_for(self, value: int) -> str:
        raise NotImplementedError


class StandardScoringStrategy(ScoringStrategy):
    """Original EventWise scoring: sum of three scores, 3-band priority."""

    def calculate(self, ai_result: dict) -> int:
        return (
            ai_result["career_relevance"]
            + ai_result["learning_value"]
            + ai_result["networking_value"]
        )

    def priority_for(self, value: int) -> str:
        if value >= 11:
            return "High"
        if value >= 7:
            return "Medium"
        return "Low"