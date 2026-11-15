"""Offline checks for the GUI travel response contract."""

import json
import unittest
from datetime import datetime, timedelta, timezone

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

    def test_leg_serialization_excludes_geometry_and_arbitrary_fields(self):
        self.route.legs = [{"mode": "BUS", "duration_minutes": 0, "distance_km": 0,
                            "route": " 42 ", "from_name": "Stop A", "to_name": "Stop B",
                            "geometry_points": "PRIVATE_GEOMETRY", "token": "PRIVATE_TOKEN"}]
        assessment = self.evaluator.evaluate(self.start, self.route)
        self.route.legs[0]["route"] = "changed"
        result = serialize_travel_result(assessment)
        self.assertEqual(result["legs"], [{"mode": "BUS", "duration_minutes": 0,
                         "distance_km": 0, "route": "42", "from_name": "Stop A", "to_name": "Stop B", "geometry": None}])
        self.assertNotIn("PRIVATE_", json.dumps(result))
        result["legs"][0]["route"] = "client edit"
        self.assertEqual(assessment.legs[0]["route"], " 42 ")

    def test_malformed_optional_leg_fields_remain_json_safe(self):
        for value in (True, -1, float("inf"), float("nan"), "5", 10 ** 400):
            self.assessment.legs = [None, {"mode": {}, "duration_minutes": value,
                "distance_km": value, "route": [], "from_name": 123, "to_name": " "}]
            with self.subTest(value=value):
                result = serialize_travel_result(self.assessment)
                self.assertEqual(result["legs"], [{"mode": None, "duration_minutes": None,
                    "distance_km": None, "route": None, "from_name": None, "to_name": None, "geometry": None}])
                json.dumps(result, allow_nan=False)

    def test_valid_geometry_is_decoded_only_for_available_current_result(self):
        self.assessment.legs = [{"mode": "WALK", "geometry_points": '_||F_mpxRgEoKgEfE'}]
        result = serialize_travel_result(self.assessment)
        self.assertEqual(result['legs'][0]['geometry'], [[1.3, 103.8], [1.301, 103.802], [1.302, 103.801]])
        self.assertNotIn('geometry_points', result['legs'][0])
        self.assertIsNone(serialize_travel_result()['legs'])

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

    def test_arrival_warning_boundaries_use_returned_arrival(self):
        cases = (
            (-16, []),
            (-15, []),
            (-14, ["BUFFER_MISSED"]),
            (0, ["BUFFER_MISSED"]),
            (1, ["EVENT_START_MISSED"]),
        )
        for minutes, expected in cases:
            with self.subTest(minutes=minutes):
                self.assessment.estimated_arrival = self.start + timedelta(minutes=minutes)
                result = serialize_travel_result(self.assessment, event_start=self.start)
                self.assertEqual(result["warning_codes"], expected)
                self.assertEqual(result["feasibility"], "WITHIN_LIMIT")
                self.assertEqual(self.assessment.recommended_departure, self.route.departure_time)

    def test_warning_converts_utc_and_crosses_midnight(self):
        event_start = self.start.replace(minute=0)
        self.assessment.estimated_arrival = event_start - timedelta(minutes=10)
        result = serialize_travel_result(
            self.assessment, event_start=event_start.astimezone(timezone.utc)
        )
        self.assertEqual(result["warning_codes"], ["BUFFER_MISSED"])
        self.assertEqual(result["estimated_arrival"], "2026-12-31T23:50:00+08:00")

    def test_custom_buffer_and_limit_preserve_independent_meanings(self):
        evaluator = TravelEvaluator(arrival_buffer_minutes=20, preferred_limit_minutes=32)
        assessment = evaluator.evaluate(self.start, self.route)
        result = serialize_travel_result(
            assessment, event_start=self.start, preferred_limit_minutes=32
        )
        self.assertEqual(result["recommended_departure"], "2026-12-31T23:28:00+08:00")
        self.assertEqual(result["warning_codes"], ["BUFFER_MISSED"])
        self.assertEqual(result["feasibility"], "WITHIN_LIMIT")
        self.assertEqual(result["preferred_travel_limit_minutes"], 32)
        longer = TravelEvaluator(arrival_buffer_minutes=20, preferred_limit_minutes=31)
        long_result = serialize_travel_result(
            longer.evaluate(self.start, self.route), event_start=self.start,
            preferred_limit_minutes=31,
        )
        self.assertEqual(long_result["feasibility"], "LONG_JOURNEY")
        self.assertEqual(long_result["warning_codes"], result["warning_codes"])
        self.assertEqual(long_result["recommended_departure"], result["recommended_departure"])

    def test_zero_buffer_and_long_journey_can_arrive_on_time(self):
        evaluator = TravelEvaluator(arrival_buffer_minutes=0, preferred_limit_minutes=20)
        assessment = evaluator.evaluate(self.start, self.route)
        assessment.estimated_arrival = self.start
        result = serialize_travel_result(assessment, event_start=self.start)
        self.assertEqual(result["warning_codes"], [])
        self.assertEqual(result["feasibility"], "LONG_JOURNEY")

    def test_skipped_and_unavailable_cannot_have_arrival_warnings(self):
        for assessment in (None, self.evaluator.evaluate(self.start)):
            result = serialize_travel_result(assessment, event_start=self.start)
            self.assertIsNone(result["warning_codes"])

    def test_invalid_event_start_and_excessive_buffer_are_rejected(self):
        for invalid in ("2027-01-01", datetime(2027, 1, 1)):
            with self.subTest(value=invalid), self.assertRaises(ValidationError):
                serialize_travel_result(self.assessment, event_start=invalid)
        self.assessment.arrival_buffer_minutes = 1e100
        with self.assertRaises(ValidationError):
            serialize_travel_result(self.assessment, event_start=self.start)


if __name__ == "__main__":
    unittest.main()
