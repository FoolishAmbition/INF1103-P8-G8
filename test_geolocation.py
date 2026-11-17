"""Offline unit tests for geolocation service, journey evaluation, and travel results."""

import unittest
from datetime import datetime, timedelta

from src.exceptions import GeoLocationError, ValidationError
from src.geolocation_service import GeoLocationService
from src.journey_planner import JourneyPlanner
from src.transit_routing_service import TransitRoutingService
from src.travel_result import TravelResult


class TestPostalCodeValidation(unittest.TestCase):
    def test_valid_singapore_postal_codes(self):
        self.assertEqual(TransitRoutingService.validate_singapore_postal_code("123456"), "123456")
        self.assertEqual(TransitRoutingService.validate_singapore_postal_code("018956"), "018956")
        # Ensure inherited method on GeoLocationService also works
        self.assertEqual(GeoLocationService.validate_singapore_postal_code("123456"), "123456")
        self.assertEqual(GeoLocationService.validate_singapore_postal_code("018956"), "018956")

    def test_invalid_singapore_postal_codes(self):
        with self.assertRaises(ValidationError):
            TransitRoutingService.validate_singapore_postal_code("12345")  # 5 digits
        with self.assertRaises(ValidationError):
            TransitRoutingService.validate_singapore_postal_code("1234567")  # 7 digits
        with self.assertRaises(ValidationError):
            TransitRoutingService.validate_singapore_postal_code("ABC456")  # alphabetic
        with self.assertRaises(ValidationError):
            TransitRoutingService.validate_singapore_postal_code(123456)  # integer
        with self.assertRaises(ValidationError):
            GeoLocationService.validate_singapore_postal_code("12345")


class TestJourneyPlannerEvaluation(unittest.TestCase):
    def setUp(self):
        self.planner = JourneyPlanner(arrival_buffer_minutes=15, preferred_limit_minutes=60)
        self.tz = GeoLocationService.SINGAPORE_TIMEZONE
        self.event_start = datetime(2026, 12, 1, 10, 0, tzinfo=self.tz)

    def test_departure_calculation_includes_buffer(self):
        departure_time = self.event_start - timedelta(minutes=50)
        arrival_time = departure_time + timedelta(minutes=35)
        route = TravelResult(
            distance_km=5.0,
            duration_minutes=35,
            departure_time=departure_time,
            estimated_arrival=arrival_time,
        )
        assessment = self.planner.evaluate(self.event_start, route)
        # Expected departure = 10:00 - 35 min travel - 15 min buffer = 09:10
        expected = self.event_start - timedelta(minutes=50)
        self.assertEqual(assessment.recommended_departure, expected)
        self.assertEqual(assessment.feasibility, "WITHIN_LIMIT")

    def test_feasibility_long_journey(self):
        departure_time = self.event_start - timedelta(minutes=90)
        arrival_time = departure_time + timedelta(minutes=75)
        route = TravelResult(
            distance_km=15.0,
            duration_minutes=75,
            departure_time=departure_time,
            estimated_arrival=arrival_time,
        )
        assessment = self.planner.evaluate(self.event_start, route)
        self.assertEqual(assessment.feasibility, "LONG_JOURNEY")

    def test_evaluate_none_route_returns_unavailable(self):
        assessment = self.planner.evaluate(self.event_start, route=None)
        self.assertEqual(assessment.status, "UNAVAILABLE")
        self.assertEqual(assessment.error_code, "TRAVEL_UNAVAILABLE")


class TestTravelResult(unittest.TestCase):
    def test_skipped_result(self):
        result = TravelResult(None).to_dict()
        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(result["schema_version"], 1)

    def test_available_result(self):
        tz = GeoLocationService.SINGAPORE_TIMEZONE
        assessment = TravelResult(
            status="AVAILABLE",
            feasibility="WITHIN_LIMIT",
            arrival_buffer_minutes=15,
            duration_minutes=40,
            distance_km=8.5,
            recommended_departure=datetime(2026, 12, 1, 9, 5, tzinfo=tz),
            estimated_arrival=datetime(2026, 12, 1, 9, 45, tzinfo=tz),
            event_start=datetime(2026, 12, 1, 10, 0, tzinfo=tz),
        )
        result = TravelResult(assessment).to_dict()
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["duration_minutes"], 40)
        self.assertEqual(result["distance_km"], 8.5)

    def test_unavailable_result_with_error_code(self):
        assessment = TravelResult(
            status="UNAVAILABLE",
            feasibility="UNAVAILABLE",
            arrival_buffer_minutes=15,
            error_code="TIMEOUT",
        )
        result = TravelResult(assessment).to_dict()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["error_code"], "TIMEOUT")
        self.assertIn("too long", result["error_message"].lower())


class TestGeoLocationServiceOffline(unittest.TestCase):
    def test_invalid_postal_code_raises_validation_before_network(self):
        service = GeoLocationService(token="dummy-token")
        dep_time = datetime(2026, 12, 1, 9, 0, tzinfo=GeoLocationService.SINGAPORE_TIMEZONE)
        with self.assertRaises(ValidationError):
            service.get_transit_route("invalid", "654321", dep_time)

    def test_empty_token_raises_authentication_error(self):
        service = GeoLocationService(token="")
        dep_time = datetime(2026, 12, 1, 9, 0, tzinfo=GeoLocationService.SINGAPORE_TIMEZONE)
        with self.assertRaises(GeoLocationError) as ctx:
            service.get_transit_route("123456", "654321", dep_time)
        self.assertEqual(ctx.exception.code, "AUTHENTICATION_ERROR")


if __name__ == "__main__":
    unittest.main()
