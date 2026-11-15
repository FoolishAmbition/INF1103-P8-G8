"""Backward-compatible event venue and historical journey persistence."""

import json
import unittest

from src.exceptions import ValidationError
from src.models import EventRecord


class TestEventLocations(unittest.TestCase):
    def test_legacy_event_loads_without_location_or_journey(self):
        event = EventRecord.from_dict({"event_name": "Old event", "event_description": "Description"})
        self.assertEqual(event.venue_name, "")
        self.assertEqual(event.venue_address, "")
        self.assertEqual(event.destination_postal_code, "")
        self.assertIsNone(event.travel_snapshot)

    def test_json_round_trip_preserves_venue_and_snapshot(self):
        event = EventRecord("Workshop", "Python", "Low", venue_name="Hall",
                            venue_address="10 Example Road", destination_postal_code="012345",
                            travel_snapshot={"status": "AVAILABLE", "duration_minutes": 32,
                                             "estimated_arrival": "2030-01-01T09:00:00+08:00"})
        restored = EventRecord.from_dict(json.loads(json.dumps(event.to_dict())))
        self.assertEqual(restored, event)
        self.assertEqual(restored.destination_postal_code, "012345")
        self.assertEqual(restored.venue_name, "Hall")
        self.assertEqual(restored.venue_address, "10 Example Road")
        self.assertEqual(restored.travel_snapshot, event.travel_snapshot)

    def test_snapshot_copies_do_not_mutate_saved_record(self):
        snapshot = {"status": "AVAILABLE", "warning_codes": ["BUFFER_MISSED"]}
        event = EventRecord("Workshop", "Python", "Low", travel_snapshot=snapshot)
        snapshot["warning_codes"].clear()
        output = event.to_dict()
        output["travel_snapshot"]["warning_codes"].clear()
        self.assertEqual(event.travel_snapshot["warning_codes"], ["BUFFER_MISSED"])
        stored = event.to_dict()
        restored = EventRecord.from_dict(stored)
        stored["travel_snapshot"]["warning_codes"].clear()
        self.assertEqual(restored.travel_snapshot["warning_codes"], ["BUFFER_MISSED"])

    def test_unrecognised_snapshot_fields_are_not_persisted(self):
        event = EventRecord("Workshop", "Python", "Low", travel_snapshot={
            "status": "UNAVAILABLE", "origin_postal_code": "012345", "access_token": "secret"
        })
        self.assertEqual(event.travel_snapshot, {"status": "UNAVAILABLE"})
        event.travel_snapshot["origin_postal_code"] = "012345"
        self.assertEqual(event.to_dict()["travel_snapshot"], {"status": "UNAVAILABLE"})

    def test_invalid_snapshot_or_postal_is_rejected(self):
        for snapshot in (
            [], {}, {"status": "UNKNOWN"},
            {"status": "AVAILABLE", "distance_km": float("nan")},
            {"status": "AVAILABLE", "duration_minutes": float("inf")},
            {"status": "AVAILABLE", "estimated_arrival": object()},
        ):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValidationError):
                EventRecord("Workshop", "Python", "Low", travel_snapshot=snapshot)
        with self.assertRaises(ValidationError):
            EventRecord("Workshop", "Python", "Low", destination_postal_code="12345")

    def test_invalid_venue_and_postal_types_are_rejected(self):
        for metadata in (
            {"venue_name": None}, {"venue_address": []},
            {"destination_postal_code": 123456},
            {"destination_postal_code": None},
        ):
            with self.subTest(metadata=metadata), self.assertRaises(ValidationError):
                EventRecord("Workshop", "Python", "Low", **metadata)


if __name__ == "__main__":
    unittest.main()
