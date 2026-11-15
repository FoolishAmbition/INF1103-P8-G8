"""
src/analytics_reporter.py

Provides the AnalyticsReporter class for calculating statistics and trends
from a collection of events. Demonstrates the Single Responsibility
Principle (SRP) by performing data aggregation and analysis only, with
no dependency on terminal UI or file storage.
"""


class AnalyticsReporter:
    """Calculates summary statistics, distributions, and averages for events."""

    STANDARD_RECOMMENDATIONS = ("ATTEND", "MAYBE", "SKIP")
    STANDARD_PRIORITIES = ("High", "Medium", "Low")
    STANDARD_WORKLOADS = ("Low", "Medium", "High")

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
        """Safely extract a field from either an EventRecord or a dict."""
        if hasattr(event, field_name):
            val = getattr(event, field_name)
            if val is not None:
                return val
        if isinstance(event, dict):
            if field_name in event and event[field_name] is not None:
                return event[field_name]
            # Common synonyms and nested fields
            if field_name == "event_name" and "name" in event and event["name"] is not None:
                return event["name"]
            if field_name == "event_description" and "description" in event and event["description"] is not None:
                return event["description"]
            if field_name == "event_category":
                if "category" in event and event["category"] is not None:
                    return event["category"]
                ai = event.get("ai_scores") or event.get("AI_Scores")
                if isinstance(ai, dict) and "event_category" in ai and ai["event_category"] is not None:
                    return ai["event_category"]
            return event.get(field_name, default)
        return default

    @staticmethod
    def _get_score(event, score_name):
        """Safely extract a specific numeric score from an EventRecord or dict."""
        # 1. Direct attribute on EventRecord
        if hasattr(event, score_name):
            val = getattr(event, score_name)
            if isinstance(val, (int, float)):
                return val

        # 2. Check within ai_scores object if present
        if hasattr(event, "ai_scores") and event.ai_scores is not None:
            if hasattr(event.ai_scores, score_name):
                val = getattr(event.ai_scores, score_name)
                if isinstance(val, (int, float)):
                    return val
            if score_name == "event_value" and hasattr(event.ai_scores, "total_value"):
                val = event.ai_scores.total_value
                if isinstance(val, (int, float)):
                    return val

        # 3. Check dictionary format
        if isinstance(event, dict):
            if score_name in event and isinstance(event[score_name], (int, float)):
                return event[score_name]
            if score_name == "event_value" and "total_value" in event and isinstance(event["total_value"], (int, float)):
                return event["total_value"]
            scores = event.get("ai_scores") or event.get("AI_Scores")
            if isinstance(scores, dict):
                if score_name in scores and isinstance(scores[score_name], (int, float)):
                    return scores[score_name]
                if score_name == "event_value" and "total_value" in scores and isinstance(scores["total_value"], (int, float)):
                    return scores["total_value"]

        return 0

    def total_events(self, events=None):
        """Return the total number of events."""
        return len(self._resolve_events(events))

    def category_distribution(self, events=None):
        """Count how many events belong to each category.

        Returns a dict mapping category name to count, e.g. {"Workshop": 3}.
        """
        target_events = self._resolve_events(events)
        counts = {}
        for event in target_events:
            category = str(self._get_field(event, "event_category", "")).strip()
            if not category:
                category = "Uncategorised"
            counts[category] = counts.get(category, 0) + 1
        return counts

    def recommendation_breakdown(self, events=None):
        """Count events for each recommendation status (ATTEND, MAYBE, SKIP)."""
        target_events = self._resolve_events(events)
        counts = {rec: 0 for rec in self.STANDARD_RECOMMENDATIONS}

        for event in target_events:
            rec = str(self._get_field(event, "recommendation", "")).strip().upper()
            if rec in counts:
                counts[rec] += 1
            elif rec:
                counts[rec] = counts.get(rec, 0) + 1
        return counts

    def attendance_ratio(self, events=None):
        """Return the ratio of ATTEND events to total events (0.0 to 1.0).

        Returns 0.0 if there are no events.
        """
        target_events = self._resolve_events(events)
        total = len(target_events)
        if total == 0:
            return 0.0

        breakdown = self.recommendation_breakdown(target_events)
        attend_count = breakdown.get("ATTEND", 0)
        return round(attend_count / total, 2)

    def attendance_rate(self, events=None):
        """Return the percentage of ATTEND events to total events (0.0 to 100.0).

        Returns 0.0 if there are no events.
        """
        target_events = self._resolve_events(events)
        total = len(target_events)
        if total == 0:
            return 0.0

        breakdown = self.recommendation_breakdown(target_events)
        attend_count = breakdown.get("ATTEND", 0)
        return round((attend_count / total) * 100, 1)

    def priority_distribution(self, events=None):
        """Count events for each priority level (High, Medium, Low)."""
        target_events = self._resolve_events(events)
        counts = {pri: 0 for pri in self.STANDARD_PRIORITIES}

        for event in target_events:
            priority = str(self._get_field(event, "priority", "")).strip().capitalize()
            if priority in counts:
                counts[priority] += 1
            elif priority:
                counts[priority] = counts.get(priority, 0) + 1
        return counts

    def workload_vs_recommendation(self, events=None):
        """Cross-tabulate events by workload (Low/Med/High) and recommendation.

        Returns a nested dict, e.g.:
        {
            "Low": {"ATTEND": 1, "MAYBE": 0, "SKIP": 0, "total": 1},
            "Medium": {"ATTEND": 0, "MAYBE": 1, "SKIP": 0, "total": 1},
            "High": {"ATTEND": 0, "MAYBE": 0, "SKIP": 1, "total": 1}
        }
        """
        target_events = self._resolve_events(events)
        table = {
            workload: {rec: 0 for rec in self.STANDARD_RECOMMENDATIONS}
            for workload in self.STANDARD_WORKLOADS
        }
        for workload in table:
            table[workload]["total"] = 0

        for event in target_events:
            workload = str(self._get_field(event, "workload", "Low")).strip().capitalize()
            rec = str(self._get_field(event, "recommendation", "")).strip().upper()

            if workload not in table:
                table[workload] = {r: 0 for r in self.STANDARD_RECOMMENDATIONS}
                table[workload]["total"] = 0

            if rec in table[workload]:
                table[workload][rec] += 1
            else:
                table[workload][rec] = table[workload].get(rec, 0) + 1

            table[workload]["total"] += 1

        return table

    def average_scores(self, events=None):
        """Calculate average scores for career, learning, networking, and total value.

        Returns 0.0 for any score if there are no events.
        """
        target_events = self._resolve_events(events)
        total = len(target_events)
        if total == 0:
            return {
                "career_relevance": 0.0,
                "learning_value": 0.0,
                "networking_value": 0.0,
                "total_value": 0.0,
                "career": 0.0,
                "learning": 0.0,
                "networking": 0.0,
                "score": 0.0,
            }

        career_sum = 0
        learning_sum = 0
        networking_sum = 0
        total_sum = 0

        for event in target_events:
            career_sum += self._get_score(event, "career_relevance")
            learning_sum += self._get_score(event, "learning_value")
            networking_sum += self._get_score(event, "networking_value")

            # Total score: check event_value first, fallback to sum of scores
            val = self._get_score(event, "event_value")
            if val == 0:
                val = self._get_score(event, "total_value")
            if val == 0:
                val = (
                    self._get_score(event, "career_relevance")
                    + self._get_score(event, "learning_value")
                    + self._get_score(event, "networking_value")
                )
            total_sum += val

        career_avg = round(career_sum / total, 1)
        learning_avg = round(learning_sum / total, 1)
        networking_avg = round(networking_sum / total, 1)
        total_avg = round(total_sum / total, 1)

        return {
            "career_relevance": career_avg,
            "learning_value": learning_avg,
            "networking_value": networking_avg,
            "total_value": total_avg,
            "career": career_avg,
            "learning": learning_avg,
            "networking": networking_avg,
            "score": total_avg,
        }

    def generate_summary(self, events=None):
        """Assemble all statistics into a complete summary dictionary."""
        target_events = self._resolve_events(events)
        total = self.total_events(target_events)
        counts = self.category_distribution(target_events)

        categories = []
        for cat, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            pct = round((count / total) * 100, 1) if total > 0 else 0.0
            categories.append({
                "category": cat,
                "count": count,
                "percentage": pct,
            })

        return {
            "total_events": total,
            "attendance_rate": self.attendance_rate(target_events),
            "attendance_ratio": self.attendance_ratio(target_events),
            "recommendation_breakdown": self.recommendation_breakdown(target_events),
            "category_distribution": counts,
            "categories": categories,
            "priority_distribution": self.priority_distribution(target_events),
            "workload_breakdown": self.workload_vs_recommendation(target_events),
            "average_scores": self.average_scores(target_events),
        }

