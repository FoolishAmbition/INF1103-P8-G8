"""Offline orchestration checks using fixed time and mocked transit requests."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from src.geolocation import GeoLocationError, SINGAPORE_TIMEZONE, TransitRoute
from src.journey_planner import JourneyPlanner
from src.travel_assessment import TravelEvaluator
from src.travel_result import serialize_travel_result


class TestJourneyPlanner(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 12, 31, 20, tzinfo=SINGAPORE_TIMEZONE)
        self.start = datetime(2027, 1, 1, 0, 20, tzinfo=SINGAPORE_TIMEZONE)
        self.service = Mock()
        self.clock = Mock(return_value=self.now)
        self.evaluator = TravelEvaluator()
        self.planner = JourneyPlanner(self.service, self.evaluator, self.clock)
        self.first = TransitRoute(12, 32, self.start - timedelta(minutes=75),
                                  self.start - timedelta(minutes=43))
        self.departure = self.start - timedelta(minutes=47)
        self.checked = TransitRoute(13, 40, self.departure,
                                    self.departure + timedelta(minutes=40))
        self.service.get_transit_route.side_effect = [self.first, self.checked]

    def test_recheck_keeps_matching_departure_arrival_across_midnight(self):
        assessment, code = self.planner.plan("012345", "023456", self.start)
        requests = self.service.get_transit_route.call_args_list
        self.assertEqual(requests[0].args, ("012345", "023456", self.first.departure_time))
        self.assertEqual(requests[1].args, ("012345", "023456", self.departure))
        self.assertEqual(assessment.recommended_departure, self.departure)
        self.assertEqual(assessment.estimated_arrival, self.checked.estimated_arrival)
        self.assertEqual(assessment.duration_minutes, 40)
        self.assertIsNone(code)
        result = serialize_travel_result(assessment, error_code=code, event_start=self.start)
        self.assertEqual(result["warning_codes"], ["BUFFER_MISSED"])

    def test_skip_does_not_validate_inputs_read_clock_or_call_provider(self):
        assessment, code = self.planner.plan(enabled=False)
        self.assertIsNone(assessment)
        self.assertIsNone(code)
        self.assertEqual(self.service.mock_calls, [])
        self.clock.assert_not_called()
        self.assertEqual(serialize_travel_result(assessment)["status"], "SKIPPED")

    def test_invalid_inputs_are_unavailable_before_provider_calls(self):
        cases = (
            (None, "023456", self.start, "MISSING_ORIGIN"),
            ("12345", "023456", self.start, "INVALID_INPUT"),
            ("012345", "ABC123", self.start, "INVALID_INPUT"),
            ("012345", "023456", datetime(2027, 1, 1), "INVALID_INPUT"),
            ("012345", "023456", self.now, "EVENT_PAST"),
        )
        for origin, destination, start, expected in cases:
            with self.subTest(code=expected):
                assessment, code = self.planner.plan(origin, destination, start)
                self.assertEqual(assessment.status, "UNAVAILABLE")
                self.assertIsNone(assessment.duration_minutes)
                self.assertEqual(code, expected)
                self.assertEqual(self.service.mock_calls, [])

    def test_provider_errors_at_either_request_keep_codes(self):
        for code in ("TIMEOUT", "NO_ROUTE", "AUTHENTICATION_ERROR", "QUOTA_EXCEEDED"):
            for second in (False, True):
                with self.subTest(code=code, second=second):
                    responses = [GeoLocationError(code, "Safe provider failure.")]
                    if second:
                        responses.insert(0, self.first)
                    self.service.get_transit_route.side_effect = responses
                    assessment, actual = self.planner.plan("012345", "023456", self.start)
                    self.assertEqual(actual, code)
                    result = serialize_travel_result(assessment, error_code=actual)
                    self.assertEqual(result["error_code"], code)
                    self.assertIsNone(result["duration_minutes"])

    def test_past_calculated_departure_stops_before_recheck(self):
        self.first.duration_minutes = 600
        assessment, code = self.planner.plan("012345", "023456", self.start)
        self.assertEqual(code, "DEPARTURE_PAST")
        self.assertEqual(assessment.status, "UNAVAILABLE")
        self.assertEqual(self.service.get_transit_route.call_count, 1)

    def test_initial_departure_is_clamped_to_now(self):
        now = self.start - timedelta(minutes=50)
        self.clock.return_value = now
        self.planner.plan("012345", "023456", self.start)
        self.assertEqual(self.service.get_transit_route.call_args_list[0].args[2], now)

    def test_custom_preferences_and_utc_start_use_same_flow(self):
        evaluator = TravelEvaluator(arrival_buffer_minutes=20, preferred_limit_minutes=35)
        planner = JourneyPlanner(self.service, evaluator, self.clock)
        assessment, code = planner.plan("012345", "023456", self.start.astimezone(timezone.utc))
        self.assertIsNone(code)
        self.assertEqual(assessment.recommended_departure, self.start - timedelta(minutes=52))
        self.assertEqual(assessment.arrival_buffer_minutes, 20)
        self.assertEqual(assessment.feasibility, "LONG_JOURNEY")

    def test_invalid_route_and_overflow_become_unavailable(self):
        for duration in (-1, 1e100):
            with self.subTest(duration=duration):
                self.first.duration_minutes = duration
                self.service.get_transit_route.side_effect = [self.first]
                assessment, code = self.planner.plan("012345", "023456", self.start)
                self.assertEqual(code, "INVALID_INPUT")
                self.assertEqual(assessment.status, "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
