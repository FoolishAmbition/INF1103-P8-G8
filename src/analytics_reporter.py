"""
src/analytics_reporter.py

Provides the AnalyticsReporter class for calculating statistics and trends
from a collection of standardized EventRecord domain objects.
"""

from src.event_record import EventRecord


class AnalyticsReporter:
    """Calculates summary statistics, distributions, and averages for events."""

    STANDARD_RECOMMENDATIONS = ("ATTEND", "MAYBE", "SKIP")
    STANDARD_PRIORITIES = ("High", "Medium", "Low")
    STANDARD_WORKLOADS = ("Low", "Medium", "High")

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

    def total_events(self, events=None) -> int:
        """Return the total number of events."""
        target = self.events if events is None else events
        return len(target)

    def category_distribution(self, events=None) -> dict[str, int]:
        """Count how many events belong to each category.

        Returns a dict mapping category name to count, e.g. {"Workshop": 3}.
        """
        target = self.events if events is None else events
        counts: dict[str, int] = {}
        for event in target:
            category = (event.event_category or "").strip() or "Uncategorised"
            counts[category] = counts.get(category, 0) + 1
        return counts

    def recommendation_breakdown(self, events=None) -> dict[str, int]:
        """Count events for each recommendation status (ATTEND, MAYBE, SKIP)."""
        target = self.events if events is None else events
        counts = {rec: 0 for rec in self.STANDARD_RECOMMENDATIONS}

        for event in target:
            rec = (event.recommendation or "").strip().upper()
            if rec in counts:
                counts[rec] += 1
            elif rec:
                counts[rec] = counts.get(rec, 0) + 1
        return counts

    def attendance_ratio(self, events=None) -> float:
        """Return the ratio of ATTEND events to total events (0.0 to 1.0).

        Returns 0.0 if there are no events.
        """
        target = self.events if events is None else events
        total = len(target)
        if total == 0:
            return 0.0

        attend_count = sum(1 for e in target if (e.recommendation or "").strip().upper() == "ATTEND")
        return round(attend_count / total, 2)

    def attendance_rate(self, events=None) -> float:
        """Return the percentage of ATTEND events to total events (0.0 to 100.0).

        Returns 0.0 if there are no events.
        """
        target = self.events if events is None else events
        total = len(target)
        if total == 0:
            return 0.0

        attend_count = sum(1 for e in target if (e.recommendation or "").strip().upper() == "ATTEND")
        return round((attend_count / total) * 100, 1)

    def priority_distribution(self, events=None) -> dict[str, int]:
        """Count events for each priority level (High, Medium, Low)."""
        target = self.events if events is None else events
        counts = {pri: 0 for pri in self.STANDARD_PRIORITIES}

        for event in target:
            priority = (event.priority or "").strip().capitalize()
            if priority in counts:
                counts[priority] += 1
            elif priority:
                counts[priority] = counts.get(priority, 0) + 1
        return counts

    def workload_vs_recommendation(self, events=None) -> dict[str, dict[str, int]]:
        """Cross-tabulate events by workload (Low/Medium/High) and recommendation.

        Returns a nested dict mapping workload to recommendation counts and total.
        """
        target = self.events if events is None else events
        table = {
            workload: {rec: 0 for rec in self.STANDARD_RECOMMENDATIONS}
            for workload in self.STANDARD_WORKLOADS
        }
        for workload in table:
            table[workload]["total"] = 0

        for event in target:
            workload = (event.workload or "Low").strip().capitalize()
            rec = (event.recommendation or "").strip().upper()

            if workload not in table:
                table[workload] = {r: 0 for r in self.STANDARD_RECOMMENDATIONS}
                table[workload]["total"] = 0

            if rec in table[workload]:
                table[workload][rec] += 1
            else:
                table[workload][rec] = table[workload].get(rec, 0) + 1

            table[workload]["total"] += 1

        return table

    def average_scores(self, events=None) -> dict[str, float]:
        """Calculate average scores for career, learning, networking, and total value.

        Returns 0.0 for any score if there are no events.
        """
        target = self.events if events is None else events
        total = len(target)
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

        career_sum = sum(e.career_relevance or 0 for e in target)
        learning_sum = sum(e.learning_value or 0 for e in target)
        networking_sum = sum(e.networking_value or 0 for e in target)
        total_sum = sum(e.event_value or 0 for e in target)

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

    def generate_summary(self, events=None) -> dict:
        """Assemble all statistics into a complete summary dictionary."""
        target = self.events if events is None else events
        total = self.total_events(target)
        counts = self.category_distribution(target)

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
            "attendance_rate": self.attendance_rate(target),
            "attendance_ratio": self.attendance_ratio(target),
            "recommendation_breakdown": self.recommendation_breakdown(target),
            "category_distribution": counts,
            "categories": categories,
            "priority_distribution": self.priority_distribution(target),
            "workload_breakdown": self.workload_vs_recommendation(target),
            "average_scores": self.average_scores(target),
        }
