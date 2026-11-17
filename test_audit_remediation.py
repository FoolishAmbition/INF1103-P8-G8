import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import httpx
from google.genai.errors import APIError as GoogleGenAIAPIError

from src.ai_manager import AIManager
from src.ai_client import GeminiClient
from src.ai_scores import AIScores
from src.analytics_reporter import AnalyticsReporter
from src.data_manager import DataManager
from src.event_record import EventRecord
from src.exceptions import (
    DataCorruptionError,
    DatabaseError,
    APIError,
    ResponseValidationError,
    ValidationError,
)
from src.geolocation_service import GeoLocationService
from src.journey_planner import JourneyPlanner
from src.logic_manager import LogicManager
from src.prompt_builder import PromptBuilder
from src.storage import PersistenceStrategy
from src.student_profile import StudentProfile
from src.transit_routing_service import TransitRoutingService
from src.travel_result import TravelResult


class MemoryStorage(PersistenceStrategy):
    def __init__(self, data=None, save_error=None):
        self.data = {} if data is None else data
        self.save_error = save_error

    def save(self, key, data):
        if self.save_error is not None:
            raise self.save_error
        self.data[key] = data

    def load(self, key):
        return self.data.get(key)

    def exists(self, key):
        return key in self.data


class FixedRoutingService(TransitRoutingService):
    def __init__(self):
        self.departures = []

    def get_transit_route(self, origin_postal_code, destination_postal_code, departure_time):
        self.departures.append(departure_time)
        return TravelResult(
            distance_km=5,
            duration_minutes=30,
            departure_time=departure_time,
            estimated_arrival=departure_time + timedelta(minutes=30),
        )


class AuditRemediationTests(unittest.TestCase):
    def test_gemini_client_wraps_transport_and_sdk_errors_only(self):
        client = GeminiClient(api_key="test-key")
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
        service_errors = (
            httpx.ConnectError("connection failed", request=request),
            httpx.ConnectTimeout("request timed out", request=request),
            GoogleGenAIAPIError(503, {"message": "service unavailable"}),
        )

        for error in service_errors:
            with self.subTest(error=type(error).__name__):
                with patch("google.genai.Client", side_effect=error):
                    with self.assertRaises(APIError) as raised:
                        client.call("prompt")
                self.assertIs(raised.exception.__cause__, error)

        with patch("google.genai.Client", side_effect=TypeError("programming error")):
            with self.assertRaises(TypeError):
                client.call("prompt")

    def test_standard_scoring_creates_a_consistent_event_record(self):
        record = LogicManager().create_event_record(
            AIScores(4, 3, 5),
            "Workshop",
            "Relevant",
            "Workshop",
            "Description",
            "Low",
        )

        self.assertEqual(record.career_relevance, 4)
        self.assertEqual(record.learning_value, 3)
        self.assertEqual(record.networking_value, 5)
        self.assertEqual(record.event_value, 12)
        self.assertEqual(record.priority, "High")
        self.assertEqual(record.recommendation, "ATTEND")
        serialized = record.to_dict()
        self.assertNotIn("career_relevance", serialized)
        self.assertNotIn("learning_value", serialized)
        self.assertNotIn("networking_value", serialized)
        self.assertEqual(serialized["ai_scores"], {
            "career_relevance": 4,
            "learning_value": 3,
            "networking_value": 5,
        })
        restored = EventRecord.from_dict(serialized)
        self.assertEqual(restored.ai_scores, record.ai_scores)

    def test_profile_state_is_read_only_outside_the_entity(self):
        profile = StudentProfile(field_of_study="Computing", interests=["AI"])

        interests = profile.interests
        interests.append("Changed externally")

        self.assertEqual(profile.interests, ["AI"])
        with self.assertRaises(AttributeError):
            profile.field_of_study = "Changed externally"

    def test_domain_and_route_properties_are_read_only(self):
        scores = AIScores(4, 3, 5)
        route = TravelResult(
            distance_km=5,
            duration_minutes=30,
            departure_time=datetime(2025, 1, 1),
            estimated_arrival=datetime(2025, 1, 1, 0, 30),
        )
        event = EventRecord(
            "Workshop",
            "Description",
            "Low",
            ai_scores=scores,
            recommendation="ATTEND",
        )

        with self.assertRaises(AttributeError):
            scores.career_relevance = 1
        with self.assertRaises(AttributeError):
            route.duration_minutes = 5
        with self.assertRaises(AttributeError):
            event.workload = "High"

    def test_event_record_rejects_inconsistent_scores_and_invalid_enums(self):
        scores = AIScores(4, 4, 4)
        base = {
            "workload": "Low",
            "ai_scores": scores,
            "recommendation": "ATTEND",
            "priority": "High",
            "event_value": 12,
        }

        def create_record(**overrides):
            values = {**base, **overrides}
            workload = values.pop("workload")
            return EventRecord("Workshop", "Description", workload, **values)

        invalid_values = (
            {"ai_scores": None},
            {"event_value": 2},
            {"event_value": 16},
            {"event_value": 11},
            {"event_value": True},
            {"priority": "Urgent"},
            {"priority": "Low"},
            {"workload": "low"},
            {"workload": "Urgent"},
            {"recommendation": "attend"},
            {"recommendation": "GO"},
        )
        for overrides in invalid_values:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    create_record(**overrides)

    def test_travel_assessments_are_read_only_and_departure_updates_copy(self):
        assessment = TravelResult(
            status="AVAILABLE",
            feasibility="WITHIN_LIMIT",
            arrival_buffer_minutes=15,
            recommended_departure=datetime(2025, 1, 1, 9, 0),
        )

        updated = assessment.with_recommended_departure(
            datetime(2025, 1, 1, 9, 15)
        )

        self.assertEqual(assessment.recommended_departure, datetime(2025, 1, 1, 9, 0))
        self.assertEqual(updated.recommended_departure, datetime(2025, 1, 1, 9, 15))
        with self.assertRaises(AttributeError):
            assessment.status = "UNAVAILABLE"

    def test_journey_planner_returns_immutable_assessment_with_checked_departure(self):
        singapore = GeoLocationService.SINGAPORE_TIMEZONE
        now = datetime(2025, 1, 1, 8, 0, tzinfo=singapore)
        event_start = datetime(2025, 1, 1, 10, 0, tzinfo=singapore)
        service = FixedRoutingService()
        planner = JourneyPlanner(
            service,
            clock=lambda: now,
        )

        assessment, error_code = planner.plan("123456", "654321", event_start)

        self.assertIsNone(error_code)
        self.assertEqual(len(service.departures), 2)
        self.assertEqual(assessment.recommended_departure, datetime(2025, 1, 1, 9, 15, tzinfo=singapore))

    def test_event_timestamps_are_normalized_to_utc_and_require_timezone(self):
        event = EventRecord(
            "Workshop",
            "Description",
            "Low",
            ai_scores=AIScores(2, 2, 2),
            recommendation="SKIP",
            timestamp="2025-01-01T10:00:00+08:00",
        )

        self.assertEqual(event.timestamp, "2025-01-01T02:00:00+00:00")
        with self.assertRaises(ValidationError):
            EventRecord(
                "Workshop",
                "Description",
                "Low",
                ai_scores=AIScores(2, 2, 2),
                recommendation="SKIP",
                timestamp="2025-01-01T10:00:00",
            )

    def test_ai_prompt_whitelists_profile_fields_and_schema_rejects_extras(self):
        prompt = PromptBuilder().build_analysis_prompt(
            {
                "field_of_study": "Computing",
                "interests": ["AI"],
                "home_postal_code": "123456",
                "transit_origin": "1.3,103.8",
            },
            "Workshop",
            "Description",
        )
        self.assertNotIn("123456", prompt)
        self.assertNotIn("1.3,103.8", prompt)

        result = {
            "event_category": "Workshop",
            "career_relevance": 4,
            "learning_value": 4,
            "networking_value": 3,
            "ai_reasoning": "Relevant",
        }
        manager = AIManager()
        self.assertTrue(manager.validate_schema(result))
        self.assertFalse(manager.validate_schema({**result, "unexpected": True}))
        self.assertFalse(manager.validate_schema({**result, "ai_reasoning": "  "}))
        self.assertFalse(manager.validate_schema({**result, "career_relevance": 6}))

        parsed = manager.parse_response(json.dumps(result))
        self.assertIsInstance(parsed["ai_scores"], AIScores)
        self.assertEqual(parsed["ai_scores"].total_value, 11)

        with self.assertRaises(ResponseValidationError):
            manager.parse_response(
                json.dumps({**result, "career_relevance": 6})
            )

    def test_persistence_failures_and_corrupt_records_are_reported(self):
        failing_manager = DataManager(
            storage=MemoryStorage(save_error=DatabaseError("write failed"))
        )
        with self.assertRaises(DatabaseError):
            failing_manager.save_profile(StudentProfile())

        corrupt_manager = DataManager(
            storage=MemoryStorage(data={"events": ["not an event record"]})
        )
        with self.assertRaises(DataCorruptionError):
            corrupt_manager.get_events()

        invalid_event = {
            "event_name": "Workshop",
            "event_description": "Description",
            "workload": "Low",
            "recommendation": "ATTEND",
            "ai_scores": AIScores(4, 4, 4).to_dict(),
            "priority": "High",
            "event_value": 11,
        }
        corrupt_manager = DataManager(
            storage=MemoryStorage(data={"events": [invalid_event]})
        )
        with self.assertRaises(DataCorruptionError):
            corrupt_manager.get_events()

    def test_mongo_fallback_is_reported(self):
        fallback_storage = MemoryStorage()

        with self.assertLogs("src.data_manager", level="WARNING") as captured:
            with patch(
                "src.data_manager.MongoStorage",
                side_effect=DatabaseError("MongoDB is unavailable"),
            ), patch(
                "src.data_manager.JsonStorage",
                return_value=fallback_storage,
            ):
                manager = DataManager()

        self.assertIn("falling back to JSON storage", captured.output[0])
        self.assertEqual(manager.get_events(), [])

    def test_data_manager_deserializes_records_before_filtering_and_analytics(self):
        record = EventRecord(
            "Workshop",
            "Description",
            "Low",
            ai_scores=AIScores(4, 4, 4),
            recommendation="ATTEND",
            event_category="Workshop",
        )
        manager = DataManager(
            storage=MemoryStorage(data={"events": [record.to_dict()]})
        )

        filtered = manager.filter_events(keyword="Workshop")
        summary = manager.get_analytics_summary()

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].event_name, "Workshop")
        self.assertEqual(summary["total_events"], 1)

    def test_analytics_summary_uses_one_canonical_metric_name(self):
        summary = AnalyticsReporter().generate_summary(events=[])

        self.assertIn("attendance_rate", summary)
        self.assertNotIn("attendance_ratio", summary)
        self.assertEqual(
            set(summary["average_scores"]),
            {
                "career_relevance",
                "learning_value",
                "networking_value",
                "total_value",
            },
        )


if __name__ == "__main__":
    unittest.main()
