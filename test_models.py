"""Unit tests for domain entity models: Entity, StudentProfile, AIScores, EventRecord."""

import unittest
from datetime import datetime, timezone

from src.ai_scores import AIScores
from src.entity import Entity
from src.event_record import EventRecord
from src.exceptions import ValidationError
from src.student_profile import StudentProfile


class TestStudentProfile(unittest.TestCase):
    def test_default_profile_is_empty(self):
        profile = StudentProfile()
        self.assertTrue(profile.is_empty())
        self.assertEqual(profile.field_of_study, "")
        self.assertEqual(profile.interests, [])
        self.assertEqual(profile.home_postal_code, "")

    def test_valid_profile_creation(self):
        profile = StudentProfile(
            field_of_study="Computer Science",
            interests=["AI", "Web Dev"],
            home_postal_code="123456",
        )
        self.assertFalse(profile.is_empty())
        self.assertEqual(profile.field_of_study, "Computer Science")
        self.assertEqual(profile.interests, ["AI", "Web Dev"])
        self.assertEqual(profile.home_postal_code, "123456")

    def test_invalid_postal_code_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            StudentProfile(field_of_study="IT", home_postal_code="12345")  # 5 digits
        with self.assertRaises(ValidationError):
            StudentProfile(field_of_study="IT", home_postal_code="1234567")  # 7 digits
        with self.assertRaises(ValidationError):
            StudentProfile(field_of_study="IT", home_postal_code="ABCDEF")  # letters

    def test_add_and_remove_interest(self):
        profile = StudentProfile(field_of_study="IT")
        profile.add_interest("Robotics")
        self.assertTrue(profile.has_interest("robotics"))  # case-insensitive check
        self.assertIn("Robotics", profile.interests)

        with self.assertRaises(ValidationError):
            profile.add_interest("Robotics")  # duplicate

        profile.remove_interest("robotics")
        self.assertFalse(profile.has_interest("robotics"))

        with self.assertRaises(ValidationError):
            profile.remove_interest("NonExistent")

    def test_serialization_round_trip(self):
        profile = StudentProfile(
            field_of_study="Engineering",
            interests=["IoT", "Security"],
            home_postal_code="654321",
        )
        data = profile.to_dict()
        restored = StudentProfile.from_dict(data)
        self.assertEqual(profile, restored)


class TestAIScores(unittest.TestCase):
    def test_valid_scores(self):
        scores = AIScores(career_relevance=4, learning_value=5, networking_value=3)
        self.assertEqual(scores.career_relevance, 4)
        self.assertEqual(scores.learning_value, 5)
        self.assertEqual(scores.networking_value, 3)
        self.assertEqual(scores.total_value, 12)

    def test_score_boundaries(self):
        min_scores = AIScores(1, 1, 1)
        self.assertEqual(min_scores.total_value, 3)
        max_scores = AIScores(5, 5, 5)
        self.assertEqual(max_scores.total_value, 15)

    def test_invalid_scores_raise_error(self):
        with self.assertRaises(ValidationError):
            AIScores(0, 3, 3)  # below 1
        with self.assertRaises(ValidationError):
            AIScores(6, 3, 3)  # above 5
        with self.assertRaises(ValidationError):
            AIScores("high", 3, 3)  # non-integer
        with self.assertRaises(ValidationError):
            AIScores(True, 3, 3)  # boolean not allowed as int

    def test_serialization_round_trip(self):
        scores = AIScores(3, 4, 2)
        data = scores.to_dict()
        restored = AIScores.from_dict(data)
        self.assertEqual(scores, restored)


class TestEventRecord(unittest.TestCase):
    def setUp(self):
        self.scores = AIScores(4, 4, 3)

    def test_valid_event_record_creation(self):
        record = EventRecord(
            event_name="Tech Symposium",
            event_description="Annual technology summit",
            workload="Medium",
            ai_scores=self.scores,
            recommendation="ATTEND",
            event_category="Conference",
        )
        self.assertEqual(record.event_name, "Tech Symposium")
        self.assertEqual(record.workload, "Medium")
        self.assertEqual(record.event_value, 11)
        self.assertEqual(record.priority, "High")
        self.assertEqual(record.recommendation, "ATTEND")

    def test_invalid_workload_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            EventRecord(
                "Event", "Desc", "Extreme", ai_scores=self.scores, recommendation="ATTEND"
            )

    def test_invalid_recommendation_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            EventRecord(
                "Event", "Desc", "Low", ai_scores=self.scores, recommendation="MAYBE_NOT"
            )

    def test_timestamp_normalized_to_utc(self):
        record = EventRecord(
            "Event",
            "Desc",
            "Low",
            ai_scores=self.scores,
            recommendation="ATTEND",
            timestamp="2026-11-15T20:00:00+08:00",
        )
        self.assertTrue(record.timestamp.endswith("+00:00"))

    def test_serialization_round_trip(self):
        record = EventRecord(
            event_name="Hackathon",
            event_description="24-hour coding challenge",
            workload="High",
            ai_scores=self.scores,
            recommendation="MAYBE",
            event_category="Hackathon",
            reason="High workload consideration.",
        )
        data = record.to_dict()
        restored = EventRecord.from_dict(data)
        self.assertEqual(record, restored)


if __name__ == "__main__":
    unittest.main()
