"""
src/event_filter.py

Provides the EventFilter class for filtering and searching events.
Demonstrates the Single Responsibility Principle (SRP) by handling
only event filtering logic on standardized EventRecord domain objects.
"""

from src.event_record import EventRecord


class EventFilter:
    """Filters a collection of events by recommendation, keyword, or minimum score."""

    def __init__(self, events=None):
        """Initialise with an optional collection of events (EventRecord objects or dicts)."""
        normalized = []
        for e in events or []:
            if isinstance(e, EventRecord):
                normalized.append(e)
            elif isinstance(e, dict):
                try:
                    normalized.append(EventRecord.from_dict(e))
                except (TypeError, ValueError, KeyError):
                    continue
        self.events = normalized

    def filter_by_recommendation(
        self,
        recommendation: str | None,
        events: list[EventRecord] | None = None,
    ) -> list[EventRecord]:
        """Filter events by recommendation status ('ATTEND', 'MAYBE', 'SKIP').

        Matching is case-insensitive. If recommendation is empty, None, or 'ALL',
        returns all events without filtering.
        """
        target = self.events if events is None else events
        if not recommendation or not isinstance(recommendation, str):
            return list(target)

        target_rec = recommendation.strip().upper()
        if not target_rec or target_rec == "ALL":
            return list(target)

        return [e for e in target if e.recommendation == target_rec]

    def filter_by_keyword(
        self,
        keyword: str | None,
        events: list[EventRecord] | None = None,
    ) -> list[EventRecord]:
        """Search events whose name, description, category, or reason contains keyword.

        Search is case-insensitive. If keyword is empty or None,
        returns all events without filtering.
        """
        target = self.events if events is None else events
        if not keyword or not isinstance(keyword, str):
            return list(target)

        query = keyword.strip().lower()
        if not query:
            return list(target)

        return [
            e for e in target
            if query in e.event_name.lower()
            or query in e.event_description.lower()
            or query in (e.event_category or "").lower()
            or query in (e.reason or "").lower()
        ]

    def filter_by_min_score(
        self,
        min_score: int | float | None,
        events: list[EventRecord] | None = None,
    ) -> list[EventRecord]:
        """Filter events that have a total score (event_value) >= min_score.

        If min_score is None, empty, non-numeric, or <= 0, returns all events.
        """
        target = self.events if events is None else events
        if min_score is None:
            return list(target)

        try:
            threshold = float(min_score)
        except (ValueError, TypeError):
            return list(target)

        if threshold <= 0:
            return list(target)

        return [e for e in target if (e.event_value or 0) >= threshold]

    def filter(
        self,
        recommendation: str | None = None,
        keyword: str | None = None,
        min_score: int | float | None = None,
        events: list[EventRecord] | None = None,
        recommended: str | None = None,
    ) -> list[EventRecord]:
        """Apply multiple filter criteria together.

        Accepts either 'recommendation' or 'recommended'. Any criterion left
        as None or empty is skipped.
        """
        rec = recommended if recommended is not None else recommendation
        results = self.events if events is None else events

        if rec is not None and str(rec).strip():
            results = self.filter_by_recommendation(str(rec).strip(), events=results)

        if keyword is not None and str(keyword).strip():
            results = self.filter_by_keyword(str(keyword).strip(), events=results)

        if min_score is not None:
            results = self.filter_by_min_score(min_score, events=results)

        return list(results)
