"""
test_geolocation.py - Geolocation, Transit Routing & Schedule Tests.

PURPOSE:
Validates public-transport routing and scheduling without needing live network calls:
- Postal Code Validation: Enforces Singapore 6-digit postal code format before network requests.
- JourneyPlanner: Calculates recommended departure time including the 15-minute early-arrival buffer.
- Feasibility Assessment: Flags journeys exceeding preferred limits (WITHIN_LIMIT vs LONG_JOURNEY).
- TravelResult Model: Safe parsing of OneMap transit responses (bus/MRT/walk legs, warning codes).
"""

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

    def test_journey_planner_preserves_legs(self):
        tz = GeoLocationService.SINGAPORE_TIMEZONE
        legs = [{"mode": "SUBWAY", "distance_km": 5.0, "duration_minutes": 12.0}]
        route = TravelResult(
            distance_km=5.0,
            duration_minutes=12.0,
            departure_time=datetime(2026, 12, 1, 9, 30, tzinfo=tz),
            estimated_arrival=datetime(2026, 12, 1, 9, 42, tzinfo=tz),
            legs=legs,
        )
        assessment = self.planner.evaluate(datetime(2026, 12, 1, 10, 0, tzinfo=tz), route)
        self.assertEqual(assessment.legs, legs)
        self.assertIsNot(assessment.legs, legs)

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

    def test_travel_result_with_legs_and_geometry(self):
        tz = GeoLocationService.SINGAPORE_TIMEZONE
        legs = [
            {
                "mode": "WALK",
                "distance_km": 0.5,
                "duration_minutes": 6.0,
                "route": None,
                "from_name": "Home",
                "to_name": "Bus Stop A",
                "geometry_points": "_||F_mpxRgEoKgEfE",
            },
            {
                "mode": "BUS",
                "distance_km": 3.0,
                "duration_minutes": 15.0,
                "route": "147",
                "from_name": "Bus Stop A",
                "to_name": "Campus",
                "geometry_points": None,
            },
        ]
        assessment = TravelResult(
            status="AVAILABLE",
            feasibility="WITHIN_LIMIT",
            arrival_buffer_minutes=15,
            duration_minutes=21.0,
            distance_km=3.5,
            recommended_departure=datetime(2026, 12, 1, 9, 20, tzinfo=tz),
            estimated_arrival=datetime(2026, 12, 1, 9, 45, tzinfo=tz),
            event_start=datetime(2026, 12, 1, 10, 0, tzinfo=tz),
            legs=legs,
        )
        d = assessment.to_dict()
        self.assertEqual(d["status"], "AVAILABLE")
        self.assertEqual(len(d["legs"]), 2)
        self.assertEqual(d["legs"][0]["mode"], "WALK")
        self.assertEqual(d["legs"][0]["route"], None)
        self.assertEqual(d["legs"][0]["from_name"], "Home")
        self.assertIsInstance(d["legs"][0]["geometry"], list)
        self.assertGreater(len(d["legs"][0]["geometry"]), 0)
        self.assertEqual(d["legs"][1]["mode"], "BUS")
        self.assertEqual(d["legs"][1]["route"], "147")
        self.assertIsNone(d["legs"][1]["geometry"])

    def test_from_onemap_response_with_legs(self):
        response = {
            "plan": {
                "itineraries": [
                    {
                        "duration": 1800,
                        "startTime": 1700000000000,
                        "endTime": 1700001800000,
                        "legs": [
                            {
                                "mode": "WALK",
                                "duration": 300,
                                "distance": 250,
                                "from": {"name": "Origin"},
                                "to": {"name": "Bus Stop"},
                                "legGeometry": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                            },
                            {
                                "mode": "BUS",
                                "duration": 1500,
                                "distance": 5000,
                                "route": "10",
                                "from": {"name": "Bus Stop"},
                                "to": {"name": "Destination"},
                            },
                        ],
                    }
                ]
            }
        }
        res = TravelResult.from_onemap_response(response)
        self.assertEqual(res.duration_minutes, 30.0)
        self.assertEqual(res.distance_km, 5.25)
        self.assertEqual(len(res.legs), 2)
        self.assertEqual(res.legs[0]["mode"], "WALK")
        self.assertEqual(res.legs[0]["geometry_points"], "_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        self.assertEqual(res.legs[1]["mode"], "BUS")
        self.assertEqual(res.legs[1]["route"], "10")


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
