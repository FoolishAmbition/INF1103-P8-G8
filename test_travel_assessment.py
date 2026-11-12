"""Deterministic offline tests for departure and feasibility calculations."""

import unittest
from copy import copy
from datetime import datetime, timedelta, timezone

from src.exceptions import ValidationError
from src.geolocation import SINGAPORE_TIMEZONE, TransitRoute
from src.travel_assessment import TravelEvaluator


class TestTravelEvaluator(unittest.TestCase):
    def setUp(self):
        self.event_start = datetime(2026, 11, 13, 9, tzinfo=SINGAPORE_TIMEZONE)
        self.route = TransitRoute(
            distance_km=12.5,
            duration_minutes=32,
            departure_time=datetime(2026, 11, 13, 8, 13, tzinfo=SINGAPORE_TIMEZONE),
            estimated_arrival=datetime(2026, 11, 13, 8, 45, tzinfo=SINGAPORE_TIMEZONE),
        )
        self.evaluator = TravelEvaluator()

    def test_prd_example_leaves_at_0813(self):
        result = self.evaluator.evaluate(self.event_start, self.route)
        self.assertEqual(result.recommended_departure, self.route.departure_time)
        self.assertEqual(result.status, "AVAILABLE")
        self.assertEqual(result.feasibility, "WITHIN_LIMIT")
        self.assertEqual(result.arrival_buffer_minutes, 15)
        self.assertEqual(result.distance_km, 12.5)
        self.assertEqual(result.duration_minutes, 32)
        self.assertEqual(result.estimated_arrival, self.route.estimated_arrival)
        self.assertEqual(result.provider, "OneMap")
        self.assertIsNone(result.error_message)

    def test_departure_crosses_midnight(self):
        event_start = self.event_start.replace(hour=0, minute=20)
        result = self.evaluator.evaluate(event_start, self.route)
        self.assertEqual(
            result.recommended_departure,
            datetime(2026, 11, 12, 23, 33, tzinfo=SINGAPORE_TIMEZONE),
        )

    def test_departure_crosses_year_boundary(self):
        event_start = datetime(2027, 1, 1, 0, 20, tzinfo=SINGAPORE_TIMEZONE)
        result = self.evaluator.evaluate(event_start, self.route)
        self.assertEqual(
            result.recommended_departure,
            datetime(2026, 12, 31, 23, 33, tzinfo=SINGAPORE_TIMEZONE),
        )

    def test_departure_crosses_into_leap_day(self):
        event_start = datetime(2028, 3, 1, 0, 20, tzinfo=SINGAPORE_TIMEZONE)
        result = self.evaluator.evaluate(event_start, self.route)
        self.assertEqual(
            result.recommended_departure,
            datetime(2028, 2, 29, 23, 33, tzinfo=SINGAPORE_TIMEZONE),
        )

    def test_utc_event_and_itinerary_convert_to_singapore(self):
        route = copy(self.route)
        route.departure_time = self.route.departure_time.astimezone(timezone.utc)
        route.estimated_arrival = self.route.estimated_arrival.astimezone(timezone.utc)
        event_start_utc = self.event_start.astimezone(timezone.utc)
        result = self.evaluator.evaluate(event_start_utc, route)
        self.assertEqual(result.recommended_departure, self.route.departure_time)
        self.assertEqual(result.recommended_departure.tzinfo, SINGAPORE_TIMEZONE)
        self.assertEqual(result.estimated_arrival.tzinfo, SINGAPORE_TIMEZONE)

    def test_exact_limit_is_within_limit(self):
        route = copy(self.route)
        route.duration_minutes = 60
        result = self.evaluator.evaluate(self.event_start, route)
        self.assertEqual(result.feasibility, "WITHIN_LIMIT")

    def test_above_limit_is_long_journey(self):
        route = copy(self.route)
        route.duration_minutes = 60.01
        result = self.evaluator.evaluate(self.event_start, route)
        self.assertEqual(result.feasibility, "LONG_JOURNEY")
        self.assertEqual(result.status, "AVAILABLE")

    def test_configured_buffer_and_limit_are_used(self):
        evaluator = TravelEvaluator(arrival_buffer_minutes=10, preferred_limit_minutes=30)
        result = evaluator.evaluate(self.event_start, self.route)
        self.assertEqual(result.recommended_departure, self.event_start - timedelta(minutes=42))
        self.assertEqual(result.feasibility, "LONG_JOURNEY")
        self.assertEqual(result.arrival_buffer_minutes, 10)

    def test_zero_buffer_is_supported(self):
        evaluator = TravelEvaluator(arrival_buffer_minutes=0)
        result = evaluator.evaluate(self.event_start, self.route)
        self.assertEqual(result.recommended_departure, self.event_start - timedelta(minutes=32))

    def test_fractional_minutes_preserve_seconds(self):
        route = copy(self.route)
        route.duration_minutes = 32.5
        result = self.evaluator.evaluate(self.event_start, route)
        self.assertEqual(result.recommended_departure.second, 30)
        self.assertEqual(result.recommended_departure.minute, 12)

    def test_unavailable_route_has_none_for_journey_values(self):
        result = self.evaluator.evaluate(self.event_start)
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertEqual(result.feasibility, "UNAVAILABLE")
        self.assertIsNone(result.distance_km)
        self.assertIsNone(result.duration_minutes)
        self.assertIsNone(result.recommended_departure)
        self.assertIsNone(result.estimated_arrival)
        self.assertTrue(result.error_message)

    def test_original_arrival_is_retained_even_when_after_event(self):
        route = copy(self.route)
        route.estimated_arrival = self.event_start + timedelta(minutes=20)
        result = self.evaluator.evaluate(self.event_start, route)
        self.assertEqual(result.estimated_arrival, route.estimated_arrival)
        self.assertEqual(result.recommended_departure, self.route.departure_time)

    def test_route_is_not_mutated(self):
        original = copy(self.route)
        self.evaluator.evaluate(self.event_start, self.route)
        self.assertEqual(self.route, original)

    def test_invalid_configuration_is_rejected(self):
        invalid_numbers = (None, "15", True, -1, float("nan"), float("inf"), 10 ** 400)
        for value in invalid_numbers:
            with self.subTest(setting="buffer", value=value):
                with self.assertRaises(ValidationError):
                    TravelEvaluator(arrival_buffer_minutes=value)
            with self.subTest(setting="limit", value=value):
                with self.assertRaises(ValidationError):
                    TravelEvaluator(preferred_limit_minutes=value)
        with self.assertRaises(ValidationError):
            TravelEvaluator(preferred_limit_minutes=0)

    def test_invalid_event_start_is_rejected_even_without_route(self):
        for value in (None, "2026-11-13 09:00", datetime(2026, 11, 13, 9)):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(value)

    def test_wrong_route_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(self.event_start, {"duration_minutes": 32})

    def test_invalid_route_numbers_are_rejected(self):
        invalid_values = (None, "32", True, 0, -1, float("nan"), float("inf"), 10 ** 400)
        for value in invalid_values:
            with self.subTest(field="duration", value=value):
                route = copy(self.route)
                route.duration_minutes = value
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(self.event_start, route)
            with self.subTest(field="distance", value=value):
                route = copy(self.route)
                route.distance_km = value
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(self.event_start, route)

    def test_invalid_itinerary_times_are_rejected(self):
        invalid_times = (None, "08:13", datetime(2026, 11, 13, 8, 13))
        for value in invalid_times:
            with self.subTest(field="departure", value=value):
                route = copy(self.route)
                route.departure_time = value
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(self.event_start, route)
            with self.subTest(field="arrival", value=value):
                route = copy(self.route)
                route.estimated_arrival = value
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(self.event_start, route)
        for arrival in (self.route.departure_time, self.route.departure_time - timedelta(minutes=1)):
            with self.subTest(arrival=arrival):
                route = copy(self.route)
                route.estimated_arrival = arrival
                with self.assertRaises(ValidationError):
                    self.evaluator.evaluate(self.event_start, route)

    def test_out_of_range_departure_becomes_validation_error(self):
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(datetime(1, 1, 1, tzinfo=SINGAPORE_TIMEZONE), self.route)
        with self.assertRaises(ValidationError):
            evaluator = TravelEvaluator(arrival_buffer_minutes=1e100)
            evaluator.evaluate(self.event_start, self.route)


if __name__ == "__main__":
    unittest.main()
