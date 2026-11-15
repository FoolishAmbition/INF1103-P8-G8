"""Offline web analysis tests with real planning/logic and mocked external services."""

import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.geolocation import GeoLocationError, SINGAPORE_TIMEZONE, TransitRoute
from src.logic_manager import LogicManager
from src.models import EventRecord, StudentProfile
from web_app import app


class TestWebTravel(unittest.TestCase):
    def setUp(self):
        self.storage = Mock()
        self.db = Mock()
        self.profile = StudentProfile("Computing", ["Python"], "012345")
        self.db.load_profile.return_value = self.profile.to_dict()
        self.db.load_events.return_value = []
        self.ai = Mock()
        self.ai.analyze_event.return_value = ({
            "career_relevance": 5, "learning_value": 5, "networking_value": 5,
            "event_category": "Workshop", "ai_reasoning": "Relevant to Python.",
        }, None)
        backend_patch = patch("web_app.get_backend", return_value=(
            self.storage, self.db, self.ai, LogicManager(), StudentProfile, EventRecord
        ))
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        service_patch = patch("web_app.GeoLocationService")
        self.service_class = service_patch.start()
        self.addCleanup(service_patch.stop)
        self.service = self.service_class.return_value
        self.start = (datetime.now(SINGAPORE_TIMEZONE) + timedelta(days=10)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        self.departure = self.start - timedelta(minutes=47)
        self.first = TransitRoute(12, 32, self.start - timedelta(minutes=75),
                                  self.start - timedelta(minutes=43))
        self.checked = TransitRoute(13, 40, self.departure,
                                    self.departure + timedelta(minutes=40))
        self.service.get_transit_route.side_effect = [self.first, self.checked]
        self.payload = {
            "event_name": "Python workshop", "event_description": "Learn Python",
            "workload": "Low",
        }
        self.travel = {
            "origin_choice": "home", "destination_postal_code": "023456",
            "event_start": self.start.isoformat(),
        }
        self.client = app.test_client()

    def submit(self, travel):
        self.payload["travel"] = travel
        response = self.client.post("/api/analyse", json=self.payload)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["event"]["recommendation"], "ATTEND")
        saved = self.db.save_events.call_args.args[0]
        self.assertEqual(len(saved), 1)
        self.assertNotIn("travel", saved[0])
        self.assertEqual(saved[0], result["event"])
        self.assertEqual(saved[0]["travel_snapshot"], result["travel"])
        self.assertEqual(result["events"], saved)
        self.assertNotIn("origin_postal_code", json.dumps(saved))
        self.assertNotIn("home_postal_code", json.dumps(saved))
        self.db.save_profile.assert_not_called()
        self.storage.close.assert_called_once_with()
        return result["travel"]

    def test_legacy_request_skips_without_constructing_routing_service(self):
        self.db.load_profile.return_value = StudentProfile("Computing", ["Python"]).to_dict()
        response = self.client.post("/api/analyse", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["travel"]["status"], "SKIPPED")
        self.service_class.assert_not_called()
        self.db.save_events.assert_called_once()

    def test_current_steps_use_rechecked_route_and_are_not_saved(self):
        self.first.legs = [{"mode": "BUS", "from_name": "INITIAL_ROUTE_SENTINEL"}]
        self.checked.legs = [{
            "mode": "SUBWAY", "route": "Example line", "duration_minutes": 40,
            "distance_km": 13, "from_name": "PRIVATE_ORIGIN_SENTINEL",
            "to_name": "Example destination", "geometry_points": "GEOMETRY_SENTINEL",
            "token": "TOKEN_SENTINEL",
        }]
        self.payload["travel"] = self.travel
        response = self.client.post("/api/analyse", json=self.payload)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["travel"]["legs"][0]["mode"], "SUBWAY")
        self.assertEqual(result["travel"]["legs"][0]["from_name"], "PRIVATE_ORIGIN_SENTINEL")
        self.assertEqual(result["travel"]["estimated_arrival"], self.checked.estimated_arrival.isoformat())
        for sentinel in ("INITIAL_ROUTE_SENTINEL", "GEOMETRY_SENTINEL", "TOKEN_SENTINEL"):
            self.assertNotIn(sentinel, json.dumps(result))
        saved = self.db.save_events.call_args.args[0]
        self.assertIsNone(saved[0]["travel_snapshot"]["legs"])
        self.assertNotIn("PRIVATE_ORIGIN_SENTINEL", json.dumps(saved))
        self.assertEqual(result["event"], saved[0])
        self.db.load_events.return_value = saved
        state = self.client.get("/api/state").get_json()
        self.assertIsNone(state["events"][0]["travel_snapshot"]["legs"])
        self.assertNotIn("PRIVATE_ORIGIN_SENTINEL", json.dumps(state))
        self.assertEqual(self.service.get_transit_route.call_count, 2)

    def test_explicit_skip_ignores_unused_travel_fields(self):
        result = self.submit({
            "origin_choice": "skip", "event_start": "invalid",
            "destination_postal_code": "invalid",
        })
        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(self.db.save_events.call_args.args[0][0]["destination_postal_code"], "")
        self.service_class.assert_not_called()

    def test_geometry_is_returned_from_rechecked_route_but_never_saved(self):
        self.first.legs = [{"mode": "BUS", "geometry_points": 'INVALID_INITIAL_GEOMETRY'}]
        self.checked.legs = [{"mode": "SUBWAY", "geometry_points": '_||F_mpxRgEoKgEfE'}]
        self.payload['travel'] = self.travel
        result = self.client.post('/api/analyse', json=self.payload).get_json()
        self.assertEqual(result['travel']['legs'][0]['geometry'], [[1.3, 103.8], [1.301, 103.802], [1.302, 103.801]])
        saved = self.db.save_events.call_args.args[0]
        self.assertIsNone(saved[0]['travel_snapshot']['legs'])
        self.assertNotIn('geometry', json.dumps(saved))
        self.assertNotIn('103.8', json.dumps(saved))
        self.db.load_events.return_value = saved
        state = self.client.get('/api/state').get_json()
        self.assertNotIn('geometry', json.dumps(state))
        self.assertEqual(self.service.get_transit_route.call_count, 2)

    def test_home_routes_twice_and_returns_arrival_warning(self):
        result = self.submit(self.travel)
        requests = self.service.get_transit_route.call_args_list
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1].args, ("012345", "023456", self.departure))
        self.assertEqual(result["recommended_departure"], self.departure.isoformat())
        self.assertEqual(result["estimated_arrival"], self.checked.estimated_arrival.isoformat())
        self.assertEqual(result["warning_codes"], ["BUFFER_MISSED"])
        self.assertEqual(result["preferred_travel_limit_minutes"], 60)
        self.assertEqual(self.db.save_events.call_args.args[0][0]["destination_postal_code"], "023456")
        self.ai.analyze_event.assert_called_once_with(
            {"field_of_study": "Computing", "interests": ["Python"]},
            "Python workshop", "Learn Python",
        )

    def test_alternate_origin_preserves_existing_home(self):
        self.travel.update(origin_choice="alternate", origin_postal_code="034567")
        result = self.submit(self.travel)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual([call.args[0] for call in self.service.get_transit_route.call_args_list],
                         ["034567", "034567"])
        self.assertEqual(self.db.load_profile.return_value["home_postal_code"], "012345")

    def test_alternate_origin_works_without_saved_home(self):
        self.db.load_profile.return_value["home_postal_code"] = ""
        self.travel.update(origin_choice="alternate", origin_postal_code="034567")
        self.assertEqual(self.submit(self.travel)["status"], "AVAILABLE")
        self.assertEqual(self.db.load_profile.return_value["home_postal_code"], "")

    def test_missing_home_returns_safe_error_and_preserves_event(self):
        self.db.load_profile.return_value["home_postal_code"] = ""
        result = self.submit(self.travel)
        self.assertEqual(result["error_code"], "MISSING_ORIGIN")
        self.service.get_transit_route.assert_not_called()

    def test_naive_start_returns_unavailable_without_routing(self):
        self.travel["event_start"] = "2030-01-01T09:00:00"
        result = self.submit(self.travel)
        self.assertEqual(result["error_code"], "INVALID_INPUT")
        self.service_class.assert_not_called()

    def test_invalid_destination_returns_unavailable_without_routing(self):
        self.travel["destination_postal_code"] = "ABC123"
        result = self.submit(self.travel)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["error_code"], "INVALID_INPUT")
        self.assertEqual(self.db.save_events.call_args.args[0][0]["destination_postal_code"], "")
        self.service.get_transit_route.assert_not_called()

    def test_malformed_travel_does_not_block_event(self):
        result = self.submit(["invalid"])
        self.assertEqual(result["error_code"], "INVALID_INPUT")
        self.service_class.assert_not_called()

    def test_provider_failure_preserves_event_and_hides_provider_details(self):
        self.service.get_transit_route.side_effect = GeoLocationError("TIMEOUT", "secret 012345")
        result = self.submit(self.travel)
        self.assertEqual(result["error_code"], "TIMEOUT")
        self.assertIsNone(result["duration_minutes"])
        self.assertNotIn("secret", str(result))
        self.assertNotIn("012345", str(result))
        saved = self.db.save_events.call_args.args[0][0]
        self.assertEqual(saved["destination_postal_code"], "023456")
        self.assertNotIn("secret", json.dumps(saved))

    def test_venue_is_saved_when_travel_is_skipped(self):
        self.payload.update(venue_name=" Hall ", venue_address=" 10 Example Road ")
        self.submit({"origin_choice": "skip"})
        saved = self.db.save_events.call_args.args[0][0]
        self.assertEqual(saved["venue_name"], "Hall")
        self.assertEqual(saved["venue_address"], "10 Example Road")
        self.assertEqual(saved["travel_snapshot"]["status"], "SKIPPED")

    def test_saved_venue_and_journey_are_reloaded_from_state(self):
        self.payload.update(venue_name="Hall", venue_address="10 Example Road")
        self.submit(self.travel)
        saved = self.db.save_events.call_args.args[0]
        self.db.load_events.return_value = json.loads(json.dumps(saved))
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["events"], saved)
        snapshot = response.get_json()["events"][0]["travel_snapshot"]
        self.assertEqual(snapshot["recommended_departure"], self.departure.isoformat())
        self.assertEqual(snapshot["estimated_arrival"], self.checked.estimated_arrival.isoformat())
        self.assertEqual(self.service.get_transit_route.call_count, 2)

    def test_legacy_history_survives_new_event_save(self):
        self.db.load_events.return_value = [{
            "event_name": "Old event", "event_description": "Description", "workload": "Low",
        }]
        response = self.client.post("/api/analyse", json=self.payload)
        self.assertEqual(response.status_code, 200)
        saved = self.db.save_events.call_args.args[0]
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["event_name"], "Old event")
        self.assertEqual(saved[0]["venue_name"], "")
        self.assertIsNone(saved[0]["travel_snapshot"])
        self.assertEqual(saved[1]["travel_snapshot"]["status"], "SKIPPED")

    def test_invalid_venue_is_rejected_before_ai_or_storage(self):
        for field in ("venue_name", "venue_address"):
            for value in (None, 123, [], {}):
                with self.subTest(field=field, value=value):
                    payload = dict(self.payload)
                    payload[field] = value
                    response = self.client.post("/api/analyse", json=payload)
                    self.assertEqual(response.status_code, 400)
        self.ai.analyze_event.assert_not_called()
        self.db.save_events.assert_not_called()
        self.service_class.assert_not_called()

    def test_client_snapshot_and_origin_metadata_are_ignored(self):
        self.payload.update(
            travel_snapshot={"status": "AVAILABLE", "access_token": "client-secret"},
            origin_postal_code="034567", home_postal_code="034567",
            destination_postal_code="999999",
        )
        self.travel.update(origin_choice="alternate", origin_postal_code="034567", access_token="client-secret")
        result = self.submit(self.travel)
        saved = self.db.save_events.call_args.args[0][0]
        self.assertEqual(saved["travel_snapshot"], result)
        self.assertEqual(saved["destination_postal_code"], "023456")
        self.assertNotIn("client-secret", json.dumps(saved))
        self.assertNotIn("034567", json.dumps(saved))
        self.assertEqual(self.profile.home_postal_code, "012345")

    def test_past_start_preserves_event_without_provider_call(self):
        self.travel["event_start"] = "2000-01-01T09:00:00+08:00"
        self.assertEqual(self.submit(self.travel)["error_code"], "EVENT_PAST")
        self.service.get_transit_route.assert_not_called()

    def test_ai_failure_does_not_route_or_save(self):
        self.ai.analyze_event.return_value = (None, "AI unavailable")
        self.payload["travel"] = self.travel
        response = self.client.post("/api/analyse", json=self.payload)
        self.assertEqual(response.status_code, 502)
        self.service_class.assert_not_called()
        self.db.save_events.assert_not_called()

    def test_non_object_event_payload_is_rejected(self):
        response = self.client.post("/api/analyse", json=["invalid"])
        self.assertEqual(response.status_code, 400)
        self.ai.analyze_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
