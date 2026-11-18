"""
test_features.py - Query Filtering & Analytics Aggregation Tests.

PURPOSE:
Validates backend data analysis and query engines used by DataManager:
- EventFilter: Keyword search, recommendation status filtering (ATTEND/MAYBE/SKIP),
  minimum score thresholds, and combined multi-criteria filters.
- AnalyticsReporter: Aggregated metrics calculation, including recommended attendance rate,
  category distribution percentages, workload-vs-recommendation matrix, and score averages.
"""

import unittest

from src.ai_scores import AIScores
from src.analytics_reporter import AnalyticsReporter
from src.event_filter import EventFilter
from src.event_record import EventRecord


class TestEventFilter(unittest.TestCase):
    def setUp(self):
        self.e1 = EventRecord(
            "AI Conference",
            "Deep learning and vision",
            "Low",
            ai_scores=AIScores(5, 5, 4),
            recommendation="ATTEND",
            event_category="Conference",
            reason="High value event",
        )
        self.e2 = EventRecord(
            "Web Dev Bootcamp",
            "Learn React and Flask",
            "Medium",
            ai_scores=AIScores(3, 4, 3),
            recommendation="MAYBE",
            event_category="Workshop",
            reason="Good practical skills",
        )
        self.e3 = EventRecord(
            "Gaming Social Night",
            "Casual board games",
            "High",
            ai_scores=AIScores(1, 1, 2),
            recommendation="SKIP",
            event_category="Social",
            reason="Low career value",
        )
        self.events = [self.e1, self.e2, self.e3]
        self.filter = EventFilter(self.events)

    def test_filter_by_keyword(self):
        results = self.filter.filter_by_keyword("react")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].event_name, "Web Dev Bootcamp")

        results = self.filter.filter_by_keyword("Conference")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].event_name, "AI Conference")

        # Empty keyword returns all
        self.assertEqual(len(self.filter.filter_by_keyword("")), 3)
        self.assertEqual(len(self.filter.filter_by_keyword(None)), 3)

    def test_filter_by_recommendation(self):
        attends = self.filter.filter_by_recommendation("ATTEND")
        self.assertEqual(len(attends), 1)
        self.assertEqual(attends[0].event_name, "AI Conference")

        maybes = self.filter.filter_by_recommendation("maybe")  # case-insensitive
        self.assertEqual(len(maybes), 1)
        self.assertEqual(maybes[0].event_name, "Web Dev Bootcamp")

        all_events = self.filter.filter_by_recommendation("ALL")
        self.assertEqual(len(all_events), 3)

    def test_filter_by_min_score(self):
        high_scorers = self.filter.filter_by_min_score(14)
        self.assertEqual(len(high_scorers), 1)
        self.assertEqual(high_scorers[0].event_name, "AI Conference")

        mid_scorers = self.filter.filter_by_min_score(10)
        self.assertEqual(len(mid_scorers), 2)

        # None or invalid returns all
        self.assertEqual(len(self.filter.filter_by_min_score(None)), 3)
        self.assertEqual(len(self.filter.filter_by_min_score("invalid")), 3)

    def test_combined_filter(self):
        # Combined keyword + recommendation + min_score
        results = self.filter.filter(
            keyword="learning",
            recommended="ATTEND",
            min_score=10,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].event_name, "AI Conference")

        # Mismatch returns empty list
        results = self.filter.filter(keyword="gaming", recommended="ATTEND")
        self.assertEqual(len(results), 0)


class TestAnalyticsReporter(unittest.TestCase):
    def setUp(self):
        self.e1 = EventRecord(
            "AI Conference",
            "Deep learning and vision",
            "Low",
            ai_scores=AIScores(5, 5, 4),
            recommendation="ATTEND",
            event_category="Conference",
        )
        self.e2 = EventRecord(
            "Web Dev Bootcamp",
            "Learn React and Flask",
            "Medium",
            ai_scores=AIScores(3, 4, 3),
            recommendation="MAYBE",
            event_category="Workshop",
        )
        self.e3 = EventRecord(
            "Cloud Workshop",
            "Hands-on AWS",
            "Low",
            ai_scores=AIScores(4, 4, 4),
            recommendation="ATTEND",
            event_category="Workshop",
        )
        self.events = [self.e1, self.e2, self.e3]
        self.reporter = AnalyticsReporter(self.events)

    def test_total_events(self):
        self.assertEqual(self.reporter.total_events(), 3)
        self.assertEqual(AnalyticsReporter().total_events(), 0)

    def test_category_distribution(self):
        dist = self.reporter.category_distribution()
        self.assertEqual(dist["Conference"], 1)
        self.assertEqual(dist["Workshop"], 2)

    def test_recommendation_breakdown(self):
        breakdown = self.reporter.recommendation_breakdown()
        self.assertEqual(breakdown["ATTEND"], 2)
        self.assertEqual(breakdown["MAYBE"], 1)
        self.assertEqual(breakdown["SKIP"], 0)

    def test_attendance_rate(self):
        # 2 out of 3 attend -> 66.7%
        self.assertAlmostEqual(self.reporter.attendance_rate(), 66.7, places=1)
        self.assertEqual(AnalyticsReporter().attendance_rate(), 0.0)

    def test_priority_distribution(self):
        pdist = self.reporter.priority_distribution()
        # e1: 14 (High), e2: 10 (Medium), e3: 12 (High)
        self.assertEqual(pdist["High"], 2)
        self.assertEqual(pdist["Medium"], 1)
        self.assertEqual(pdist["Low"], 0)

    def test_generate_summary_structure(self):
        summary = self.reporter.generate_summary()
        self.assertIn("total_events", summary)
        self.assertIn("category_distribution", summary)
        self.assertIn("recommendation_breakdown", summary)
        self.assertIn("attendance_rate", summary)
        self.assertIn("priority_distribution", summary)
        self.assertIn("average_scores", summary)


if __name__ == "__main__":
    unittest.main()
