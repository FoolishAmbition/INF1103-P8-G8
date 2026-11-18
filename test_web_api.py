"""
test_web_api.py - Flask Web Routes & IOManager Integration Tests.

PURPOSE:
Validates the web presentation layer, route handling, and manager orchestration:
- Flask Endpoints: GET /, GET /api/state, POST /api/profile, POST /api/analyse, GET /api/events, GET /api/analytics.
- IOManager Validation: Validates incoming profile payloads, event inputs, and query parameters.
- Orchestration Workflow: Verifies EventWise coordinates IOManager, AIManager, LogicManager, and DataManager.
- Privacy Boundary: Verifies live transit responses preserve map legs while storage snapshots strip them.
"""

from datetime import datetime
import unittest
from unittest.mock import patch

from main import EventWise
from src.ai_scores import AIScores
from src.data_manager import DataManager
from src.storage import PersistenceStrategy


class MockStorage(PersistenceStrategy):
    """In-memory storage for isolated offline web API tests."""

    def __init__(self):
        self._data = {}

    def save(self, key, data):
        self._data[key] = data

    def load(self, key):
        return self._data.get(key)

    def exists(self, key):
        return key in self._data


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        # Create an isolated EventWise instance with memory storage to avoid touching disk or mongo
        self.storage = MockStorage()
        data_manager = DataManager(storage=self.storage)
        self.ew = EventWise(data_manager=data_manager)
        self.client = self.ew.app.test_client()

    def test_home_page_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EventWise", response.data)

    def test_get_state_returns_empty_initially(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("profile", data)
        self.assertIn("events", data)
        self.assertEqual(data["events"], [])

    def test_save_profile_validates_and_persists(self):
        payload = {
            "field_of_study": "Information Technology",
            "interests": ["Cloud", "DevOps"],
            "home_postal_code": "569830",
        }
        response = self.client.post("/api/profile", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["profile"]["field_of_study"], "Information Technology")
        self.assertEqual(data["profile"]["home_postal_code"], "569830")

    def test_save_profile_rejects_invalid_inputs(self):
        bad_payload = {
            "field_of_study": 12345,  # non-string
            "interests": "not-a-list",
        }
        response = self.client.post("/api/profile", json=bad_payload)
        self.assertEqual(response.status_code, 400)

    def test_analyse_requires_ready_profile(self):
        event_payload = {
            "event_name": "DevOps Summit",
            "event_description": "Container orchestration and CI/CD best practices",
            "workload": "Low",
        }
        # Profile is empty right now, should fail with 400
        response = self.client.post("/api/analyse", json=event_payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Complete your Profile", response.get_json()["error"])

    def test_analyse_event_with_mocked_ai(self):
        # Set profile first
        self.client.post(
            "/api/profile",
            json={"field_of_study": "Computing", "interests": ["DevOps"], "home_postal_code": ""},
        )

        mock_ai_result = {
            "event_category": "Conference",
            "ai_scores": AIScores(5, 4, 4),
            "ai_reasoning": "Direct alignment with computing and DevOps.",
        }

        with patch.object(self.ew._ai_manager, "analyze_event", return_value=(mock_ai_result, None)):
            response = self.client.post(
                "/api/analyse",
                json={
                    "event_name": "DevOps Summit",
                    "event_description": "CI/CD and Docker pipelines in production.",
                    "workload": "Low",
                    "travel": {"origin_choice": "skip"},
                },
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["event"]["recommendation"], "ATTEND")
            self.assertEqual(data["event"]["priority"], "High")
            self.assertEqual(len(data["events"]), 1)

    def test_analyse_event_persists_travel_snapshot(self):
        from src.travel_result import TravelResult
        from src.geolocation_service import GeoLocationService
        tz = GeoLocationService.SINGAPORE_TIMEZONE

        self.client.post(
            "/api/profile",
            json={"field_of_study": "Computing", "interests": ["DevOps"], "home_postal_code": "123456"},
        )
        mock_ai_result = {
            "event_category": "Workshop",
            "ai_scores": AIScores(4, 4, 4),
            "ai_reasoning": "Great workshop.",
        }
        mock_travel = TravelResult(
            status="AVAILABLE",
            feasibility="WITHIN_LIMIT",
            distance_km=6.2,
            duration_minutes=30.0,
            recommended_departure=datetime(2026, 12, 1, 9, 0, tzinfo=tz),
            estimated_arrival=datetime(2026, 12, 1, 9, 30, tzinfo=tz),
            legs=[{"mode": "BUS", "distance_km": 6.2, "duration_minutes": 30.0}],
        )

        with patch.object(self.ew._ai_manager, "analyze_event", return_value=(mock_ai_result, None)), \
             patch.object(self.ew._logic_manager, "assess_travel", return_value=mock_travel):
            response = self.client.post(
                "/api/analyse",
                json={
                    "event_name": "Cloud Seminar",
                    "event_description": "Cloud architectures",
                    "workload": "Low",
                    "travel": {
                        "origin_choice": "home",
                        "destination_postal_code": "654321",
                        "event_start": "2026-12-01T10:00",
                    },
                },
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            # Saved event entity must contain the travel snapshot without legs
            event = data["event"]
            self.assertEqual(event["destination_postal_code"], "654321")
            self.assertIsNotNone(event["travel_snapshot"])
            self.assertEqual(event["travel_snapshot"]["status"], "AVAILABLE")
            self.assertEqual(event["travel_snapshot"]["duration_minutes"], 30.0)
            self.assertIsNone(event["travel_snapshot"]["legs"])  # privacy-safe: legs stripped from storage

            # Live travel returned to browser preserves legs for interactive map
            self.assertIsNotNone(data["travel"]["legs"])

            # Verify persisted state via GET /api/state
            state_data = self.client.get("/api/state").get_json()
            saved_event = state_data["events"][-1]
            self.assertEqual(saved_event["destination_postal_code"], "654321")
            self.assertEqual(saved_event["travel_snapshot"]["status"], "AVAILABLE")

    def test_events_filtering_and_analytics_endpoints(self):
        # Populate an event
        self.client.post(
            "/api/profile",
            json={"field_of_study": "Computing", "interests": ["AI"], "home_postal_code": ""},
        )
        mock_ai_result = {
            "event_category": "Workshop",
            "ai_scores": AIScores(4, 4, 3),
            "ai_reasoning": "Good workshop.",
        }
        with patch.object(self.ew._ai_manager, "analyze_event", return_value=(mock_ai_result, None)):
            self.client.post(
                "/api/analyse",
                json={
                    "event_name": "Machine Learning Lab",
                    "event_description": "Hands on ML workshop",
                    "workload": "Low",
                    "travel": {"origin_choice": "skip"},
                },
            )

        # Check /api/events filter
        res = self.client.get("/api/events?keyword=Machine")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()["events"]), 1)

        res_none = self.client.get("/api/events?keyword=Cyber")
        self.assertEqual(res_none.status_code, 200)
        self.assertEqual(len(res_none.get_json()["events"]), 0)

        # Check /api/analytics
        res_analytics = self.client.get("/api/analytics")
        self.assertEqual(res_analytics.status_code, 200)
        analytics_data = res_analytics.get_json()["analytics"]
        self.assertEqual(analytics_data["total_events"], 1)
        self.assertEqual(analytics_data["recommendation_breakdown"]["ATTEND"], 1)


if __name__ == "__main__":
    unittest.main()
