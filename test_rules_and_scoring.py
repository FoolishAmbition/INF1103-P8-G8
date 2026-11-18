"""
test_rules_and_scoring.py - Business Rules, RuleEngine & Scoring Strategy Tests.

PURPOSE:
Validates polymorphic decision-making and scoring logic (Open/Closed Principle):
- Polymorphic Business Rules: Verifies all 6 rules evaluate in strict priority order:
    1. TopScoresRule (ATTEND)
    2. HighValueLowWorkloadRule (ATTEND)
    3. HighValueHighWorkloadRule (MAYBE)
    4. MidValueLowWorkloadRule (MAYBE)
    5. MidValueHighWorkloadRule (SKIP)
    6. LowValueRule (SKIP)
- ScoringStrategy: Sums AI criteria scores and assigns priority bands (High: 11-15, Medium: 7-10, Low: 3-6).
- LogicManager: Coordinates rule evaluation, reason generation, and EventRecord creation.
"""

import unittest

from src.ai_scores import AIScores
from src.logic_manager import LogicManager
from src.rules import (
    HighValueHighWorkloadRule,
    HighValueLowWorkloadRule,
    LowValueRule,
    MidValueHighWorkloadRule,
    MidValueLowWorkloadRule,
    RuleEngine,
    TopScoresRule,
)
from src.scoring import StandardScoringStrategy
from src.student_profile import StudentProfile


class TestBusinessRules(unittest.TestCase):
    def setUp(self):
        self.engine = RuleEngine()

    def test_rule_1_top_scores_attend(self):
        # career_relevance >= 4, learning_value >= 4, workload in ('Low', 'Medium') -> ATTEND
        scores = AIScores(career_relevance=4, learning_value=4, networking_value=1)
        self.assertEqual(self.engine.evaluate(scores, "Low", 9), "ATTEND")
        self.assertEqual(self.engine.evaluate(scores, "Medium", 9), "ATTEND")
        # Should not match Rule 1 if workload is High
        self.assertNotEqual(self.engine.evaluate(scores, "High", 9), "ATTEND")

    def test_rule_2_high_value_low_workload_attend(self):
        # event_value >= 11, workload in ('Low', 'Medium') -> ATTEND
        scores = AIScores(career_relevance=3, learning_value=5, networking_value=3)
        self.assertEqual(self.engine.evaluate(scores, "Low", 11), "ATTEND")
        self.assertEqual(self.engine.evaluate(scores, "Medium", 11), "ATTEND")

    def test_rule_3_high_value_high_workload_maybe(self):
        # event_value >= 11, workload == 'High' -> MAYBE
        scores = AIScores(career_relevance=4, learning_value=4, networking_value=4)
        self.assertEqual(self.engine.evaluate(scores, "High", 12), "MAYBE")

    def test_rule_4_mid_value_low_workload_maybe(self):
        # event_value >= 8, workload in ('Low', 'Medium') -> MAYBE
        scores = AIScores(career_relevance=3, learning_value=3, networking_value=3)
        self.assertEqual(self.engine.evaluate(scores, "Low", 9), "MAYBE")
        self.assertEqual(self.engine.evaluate(scores, "Medium", 9), "MAYBE")

    def test_rule_5_mid_value_high_workload_skip(self):
        # event_value >= 8, workload == 'High' -> SKIP
        scores = AIScores(career_relevance=3, learning_value=3, networking_value=3)
        self.assertEqual(self.engine.evaluate(scores, "High", 9), "SKIP")

    def test_rule_6_low_value_fallthrough_skip(self):
        # event_value <= 7 -> SKIP
        scores = AIScores(career_relevance=2, learning_value=2, networking_value=2)
        self.assertEqual(self.engine.evaluate(scores, "Low", 6), "SKIP")
        self.assertEqual(self.engine.evaluate(scores, "Medium", 6), "SKIP")
        self.assertEqual(self.engine.evaluate(scores, "High", 6), "SKIP")


class TestScoringStrategy(unittest.TestCase):
    def setUp(self):
        self.scoring = StandardScoringStrategy()

    def test_calculate_sums_scores(self):
        scores = AIScores(3, 4, 5)
        self.assertEqual(self.scoring.calculate(scores), 12)

    def test_priority_bands(self):
        self.assertEqual(self.scoring.priority_for(15), "High")
        self.assertEqual(self.scoring.priority_for(11), "High")
        self.assertEqual(self.scoring.priority_for(10), "Medium")
        self.assertEqual(self.scoring.priority_for(7), "Medium")
        self.assertEqual(self.scoring.priority_for(6), "Low")
        self.assertEqual(self.scoring.priority_for(3), "Low")


class TestLogicManager(unittest.TestCase):
    def setUp(self):
        self.manager = LogicManager()

    def test_profile_is_ready(self):
        empty_profile = StudentProfile()
        self.assertFalse(self.manager.profile_is_ready(empty_profile))

        ready_profile = StudentProfile(field_of_study="Computing", interests=["AI"])
        self.assertTrue(self.manager.profile_is_ready(ready_profile))

    def test_generate_reason_text(self):
        attend_low = self.manager.generate_reason("ATTEND", "Low")
        self.assertIn("manageable", attend_low)

        maybe_high = self.manager.generate_reason("MAYBE", "High")
        self.assertIn("commitments", maybe_high)

        skip = self.manager.generate_reason("SKIP", "Low")
        self.assertIn("skip", skip.lower())

    def test_create_event_record(self):
        scores = AIScores(4, 5, 4)
        record = self.manager.create_event_record(
            ai_scores=scores,
            event_category="Seminar",
            ai_reasoning="Great match for cybersecurity student.",
            event_name="Cyber Summit",
            event_description="Security trends for 2027",
            workload="Low",
        )
        self.assertEqual(record.event_name, "Cyber Summit")
        self.assertEqual(record.recommendation, "ATTEND")
        self.assertEqual(record.priority, "High")
        self.assertEqual(record.event_value, 13)


if __name__ == "__main__":
    unittest.main()
