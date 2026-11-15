"""Integration tests for EventWise Flask web routes and IOManager."""

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
