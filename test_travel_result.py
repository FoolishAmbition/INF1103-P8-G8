"""Offline checks for the GUI travel response contract."""

import json
import unittest
from datetime import datetime, timezone

from src.exceptions import ValidationError
from src.geolocation import SINGAPORE_TIMEZONE, TransitRoute
from src.travel_assessment import TravelEvaluator
from src.travel_result import ERROR_MESSAGES, serialize_travel_result


class TestTravelResult(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2027, 1, 1, 0, 20, tzinfo=SINGAPORE_TIMEZONE)
        self.route = TransitRoute(
            12.5, 32,
            datetime(2026, 12, 31, 23, 33, tzinfo=SINGAPORE_TIMEZONE),
            datetime(2027, 1, 1, 0, 5, tzinfo=SINGAPORE_TIMEZONE),
        )
        self.evaluator = TravelEvaluator(preferred_limit_minutes=40)
        self.assessment = self.evaluator.evaluate(self.start, self.route)

    def test_available_result_round_trips_through_json(self):
        result = serialize_travel_result(self.assessment, preferred_limit_minutes=40)
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["distance_km"], 12.5)
        self.assertEqual(result["duration_minutes"], 32)
        self.assertEqual(result["arrival_buffer_minutes"], 15)
        self.assertEqual(result["preferred_travel_limit_minutes"], 40)
        self.assertEqual(result["feasibility"], "WITHIN_LIMIT")
        self.assertEqual(result["recommended_departure"], "2026-12-31T23:33:00+08:00")
        self.assertEqual(result["estimated_arrival"], "2027-01-01T00:05:00+08:00")
        self.assertIsNone(result["error_code"])

    def test_utc_times_are_serialized_in_singapore_time(self):
        self.assessment.estimated_arrival = self.route.estimated_arrival.astimezone(timezone.utc)
        result = serialize_travel_result(self.assessment)
        self.assertEqual(result["estimated_arrival"], "2027-01-01T00:05:00+08:00")
        self.assertEqual(self.assessment.estimated_arrival.tzinfo, timezone.utc)

    def test_skip_and_unavailable_have_null_journey_fields_and_same_keys(self):
        skipped = serialize_travel_result()
        unavailable = serialize_travel_result(self.evaluator.evaluate(self.start))
        available = serialize_travel_result(self.assessment)
        self.assertEqual(set(skipped), set(available))
        self.assertEqual(set(unavailable), set(available))
        self.assertEqual(skipped["status"], "SKIPPED")
        self.assertEqual(unavailable["status"], "UNAVAILABLE")
        for result in (skipped, unavailable):
            for field in ("distance_km", "duration_minutes", "recommended_departure", "estimated_arrival"):
                self.assertIsNone(result[field])
            json.dumps(result, allow_nan=False)

    def test_provider_failure_codes_use_safe_messages(self):
        assessment = self.evaluator.evaluate(self.start)
        assessment.error_message = "private-token and home postal 012345"
        assessment.provider = "private-token"
        for code in ERROR_MESSAGES:
            with self.subTest(code=code):
                result = serialize_travel_result(assessment, error_code=code)
                self.assertEqual(result["error_code"], code)
                self.assertEqual(result["error_message"], ERROR_MESSAGES[code])
                encoded = json.dumps(result)
                self.assertNotIn("private-token", encoded)
                self.assertNotIn("012345", encoded)

    def test_unknown_error_does_not_leak_its_text(self):
        result = serialize_travel_result(
            self.evaluator.evaluate(self.start), error_code="secret-provider-detail"
        )
        self.assertEqual(result["error_code"], "TRAVEL_UNAVAILABLE")
        self.assertNotIn("secret-provider-detail", json.dumps(result))

    def test_unavailable_discards_stale_journey_measurements(self):
        self.assessment.status = "UNAVAILABLE"
        result = serialize_travel_result(self.assessment)
        self.assertIsNone(result["duration_minutes"])
        self.assertIsNone(result["estimated_arrival"])

    def test_unimplemented_fields_and_unsupplied_limit_stay_unknown(self):
        result = serialize_travel_result(self.assessment)
        for field in ("legs", "alternatives", "warning_codes", "preferred_travel_limit_minutes"):
            self.assertIsNone(result[field])

    def test_invalid_contract_inputs_are_rejected(self):
        with self.assertRaises(ValidationError):
            serialize_travel_result({})
        for limit in (0, -1, True, float("nan")):
            with self.subTest(limit=limit), self.assertRaises(ValidationError):
                serialize_travel_result(self.assessment, preferred_limit_minutes=limit)
        with self.assertRaises(ValidationError):
            serialize_travel_result(error_code="NO_ROUTE")
        self.assessment.recommended_departure = datetime(2027, 1, 1)
        with self.assertRaises(ValidationError):
            serialize_travel_result(self.assessment)


if __name__ == "__main__":
    unittest.main()
