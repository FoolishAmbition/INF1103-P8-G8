"""
src/event_filter.py

Provides the EventFilter class for filtering and searching events.
Demonstrates the Single Responsibility Principle (SRP) by handling
only event filtering logic, completely decoupled from user interface
and data persistence.
"""


class EventFilter:
    """Filters a collection of events by recommendation, keyword, or minimum score."""

    def __init__(self, events=None):
        """Initialise with an optional list of events (EventRecord objects or dicts)."""
        self.events = list(events) if events is not None else []

    def _resolve_events(self, events):
        """Helper to use the passed-in events list, or fall back to self.events."""
        if events is not None:
            return list(events)
        return list(self.events)

    @staticmethod
    def _get_field(event, field_name, default=""):
        """Safely extract a string field from either an EventRecord or a dict."""
        if hasattr(event, field_name):
            val = getattr(event, field_name)
            return val if val is not None else default
        if isinstance(event, dict):
            return event.get(field_name, default)
        return default

    @staticmethod
    def _get_score(event):
        """Safely extract the total score (event_value) from an EventRecord or dict."""
        # 1. Direct event_value attribute on EventRecord
        if hasattr(event, "event_value") and event.event_value is not None:
            return event.event_value

        # 2. total_value property on AIScores
        if hasattr(event, "ai_scores") and event.ai_scores is not None:
            if hasattr(event.ai_scores, "total_value"):
                return event.ai_scores.total_value

        # 3. Dictionary format
        if isinstance(event, dict):
            if event.get("event_value") is not None:
                return event["event_value"]
            scores = event.get("ai_scores")
            if isinstance(scores, dict):
                return (
                    scores.get("career_relevance", 0)
                    + scores.get("learning_value", 0)
                    + scores.get("networking_value", 0)
                )
            if "career_relevance" in event:
                return (
                    event.get("career_relevance", 0)
                    + event.get("learning_value", 0)
                    + event.get("networking_value", 0)
                )

        return 0

    def filter_by_recommendation(self, recommendation, events=None):
        """Filter events by recommendation status ('ATTEND', 'MAYBE', 'SKIP').

        Matching is case-insensitive. If recommendation is empty or None,
        returns all events without filtering.
        """
        target_events = self._resolve_events(events)
        if not recommendation or not isinstance(recommendation, str):
            return target_events

        target = recommendation.strip().upper()
        if not target:
            return target_events

        filtered = []
        for event in target_events:
            rec = str(self._get_field(event, "recommendation", "")).strip().upper()
            if rec == target:
                filtered.append(event)
        return filtered

    def filter_by_keyword(self, keyword, events=None):
        """Search events whose name, description, or category contains keyword.

        Search is case-insensitive. If keyword is empty or None,
        returns all events without filtering.
        """
        target_events = self._resolve_events(events)
        if not keyword or not isinstance(keyword, str):
            return target_events

        query = keyword.strip().lower()
        if not query:
            return target_events

        filtered = []
        for event in target_events:
            name = str(self._get_field(event, "event_name", "")).lower()
            desc = str(self._get_field(event, "event_description", "")).lower()
            cat = str(self._get_field(event, "event_category", "")).lower()

            if query in name or query in desc or query in cat:
                filtered.append(event)
        return filtered

    def filter_by_min_score(self, min_score, events=None):
        """Filter events that have a total score (event_value) >= min_score.

        If min_score is None, returns all events without filtering.
        """
        target_events = self._resolve_events(events)
        if min_score is None:
            return target_events

        filtered = []
        for event in target_events:
            score = self._get_score(event)
            if score >= min_score:
                filtered.append(event)
        return filtered

    def filter(self, recommendation=None, keyword=None, min_score=None, events=None):
        """Apply multiple filter criteria together.

        Any criterion left as None is skipped.
        """
        results = self._resolve_events(events)

        if recommendation is not None:
            results = self.filter_by_recommendation(recommendation, events=results)

        if keyword is not None:
            results = self.filter_by_keyword(keyword, events=results)

        if min_score is not None:
            results = self.filter_by_min_score(min_score, events=results)

        return results

