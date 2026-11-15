"""Scoring strategies: interchangeable implementations behind one interface."""

from abc import ABC, abstractmethod

from src.ai_scores import AIScores


class ScoringStrategy(ABC):
    @abstractmethod
    def calculate(self, ai_scores: AIScores) -> int:
        raise NotImplementedError

    @abstractmethod
    def priority_for(self, value: int) -> str:
        raise NotImplementedError


class StandardScoringStrategy(ScoringStrategy):
    """Original EventWise scoring: sum of three scores, 3-band priority."""

    def calculate(self, ai_scores: AIScores) -> int:
        return ai_scores.total_value

    def priority_for(self, value: int) -> str:
        if value >= 11:
            return "High"
        if value >= 7:
            return "Medium"
        return "Low"