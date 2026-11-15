"""Offline tests for postal validation and mocked OneMap HTTP responses."""

import unittest
import copy
import io
import json
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from src.exceptions import ValidationError
from src.geolocation import (
    GeoLocationError,
    GeoLocationService,
    TransitRoute,
    SINGAPORE_TIMEZONE,
    validate_singapore_postal_code,
)


class TestSingaporePostalCodeValidation(unittest.TestCase):
    def test_accepts_six_digit_postal_code(self):
        self.assertEqual(validate_singapore_postal_code("828761"), "828761")

    def test_preserves_leading_zero(self):
        self.assertEqual(validate_singapore_postal_code("012345"), "012345")

    def test_rejects_invalid_postal_codes(self):
        invalid_values = ("", "12345", "1234567", "ABC123", "12 456", "１２３４５６")
        for postal_code in invalid_values:
            with self.subTest(postal_code=postal_code):
                with self.assertRaises(ValidationError):
                    validate_singapore_postal_code(postal_code)

    def test_rejects_non_string_postal_code(self):
        with self.assertRaises(ValidationError):
            validate_singapore_postal_code(123456)


class TestOneMapTransitService(unittest.TestCase):
    """All provider data is synthetic; the opener never accesses the internet."""

    def setUp(self):
        self.opener = Mock()
        self.service = GeoLocationService(token="fake-secret", opener=self.opener)
        self.departure = datetime(2026, 11, 12, 16, tzinfo=SINGAPORE_TIMEZONE)
        self.start = datetime(2026, 11, 12, 16, 1, 45, tzinfo=SINGAPORE_TIMEZONE)
        self.end = datetime(2026, 11, 12, 16, 25, tzinfo=SINGAPORE_TIMEZONE)
        itinerary = {
            "duration": 1395,
            "startTime": self.start.timestamp() * 1000,
            "endTime": self.end.timestamp() * 1000,
            "legs": [{"distance": 450.9}, {"distance": 4000}],
        }
        self.route = {"plan": {"itineraries": [itinerary]}}

    def response(self, data, status=200, raw=False):
        """Build a fake response for the service's with statement and read call."""
        response = Mock()
        response.status = status
        if raw:
            response.read.return_value = data
        else:
            response.read.return_value = json.dumps(data).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def lookup(self, postal):
        location = {
            "POSTAL": postal,
            "LATITUDE": "1.3",
            "LONGITUDE": "103.8",
        }
        return {"results": [location]}

    def prepare(self, route=None):
        """Queue two postal search responses followed by one routing response."""
        if route is None:
            route = self.route
        self.opener.side_effect = [
            self.response(self.lookup("012345")),
            self.response(self.lookup("654321")),
            self.response(route),
        ]

    def get_route(self, departure=None):
        if departure is None:
            departure = self.departure
        return self.service.get_transit_route(
            "012345", "654321", departure
        )

    def assert_error(self, code, action):
        with self.assertRaises(GeoLocationError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_success_converts_all_units_and_timestamps(self):
        self.prepare()
        result = self.get_route()
        self.assertAlmostEqual(result.distance_km, 4.4509)
        self.assertEqual(result.duration_minutes, 23.25)
        self.assertEqual(result.departure_time, self.start)
        self.assertEqual(result.estimated_arrival, self.end)
        self.assertEqual(result.estimated_arrival.tzinfo, SINGAPORE_TIMEZONE)
        self.assertEqual(result.provider, "OneMap")

    def test_requests_use_exact_postals_transit_auth_and_timeout(self):
        self.prepare()
        self.get_route()
        self.assertEqual(self.opener.call_count, 3)
        queries = []
        for call in self.opener.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_header("Authorization"), "fake-secret")
            self.assertEqual(call.kwargs, {"timeout": 25})
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(urlparse(request.full_url).netloc, "www.onemap.gov.sg")
            queries.append(parse_qs(urlparse(request.full_url).query))
        self.assertEqual(queries[0]["searchVal"], ["012345"])
        self.assertEqual(queries[1]["searchVal"], ["654321"])
        self.assertEqual(queries[0]["getAddrDetails"], ["Y"])
        self.assertEqual(queries[0]["returnGeom"], ["Y"])
        self.assertEqual(queries[2], {
            "start": ["1.3,103.8"], "end": ["1.3,103.8"],
            "routeType": ["pt"], "mode": ["TRANSIT"], "date": ["11-12-2026"],
            "time": ["16:00:00"], "maxWalkDistance": ["1000"], "numItineraries": ["1"],
        })
        paths = []
        for call in self.opener.call_args_list:
            request_path = urlparse(call.args[0].full_url).path
            paths.append(request_path)
        self.assertEqual(paths, ["/api/common/elastic/search"] * 2 + ["/api/public/routingsvc/route"])

    def test_leg_details_preserve_order_units_and_selected_fields(self):
        data = copy.deepcopy(self.route)
        legs = []
        for mode, seconds, metres in (("WALK", 60, 100), ("BUS", 600, 3000), ("SUBWAY", 735, 1350.9)):
            legs.append({
                "mode": mode, "duration": seconds, "distance": metres,
                "route": "  Example service  ",
                "from": {"name": " Example start ", "lat": 1.3},
                "to": {"name": "Example end"},
                "legGeometry": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"},
                "untrusted_extra": "not copied",
            })
        data["plan"]["itineraries"][0]["legs"] = legs
        result = self.service._parse_transit_route(data)
        self.assertEqual([leg["mode"] for leg in result.legs], ["WALK", "BUS", "SUBWAY"])
        self.assertEqual(result.legs[0]["duration_minutes"], 1)
        self.assertEqual(result.legs[1]["distance_km"], 3)
        self.assertEqual(result.legs[1]["route"], "Example service")
        self.assertEqual(result.legs[0]["from_name"], "Example start")
        self.assertEqual(result.legs[0]["to_name"], "Example end")
        self.assertEqual(result.legs[0]["geometry_points"], legs[0]["legGeometry"]["points"])
        self.assertEqual(set(result.legs[0]), {"mode", "duration_minutes", "distance_km", "route", "from_name", "to_name", "geometry_points"})
        self.assertAlmostEqual(result.distance_km, 4.4509)
        self.assertEqual(result.duration_minutes, 23.25)
        self.assertEqual(result.estimated_arrival, self.end)
        legs[0]["from"]["name"] = "changed provider payload"
        self.assertEqual(result.legs[0]["from_name"], "Example start")

    def test_legacy_minimal_legs_have_unknown_optional_details(self):
        result = self.service._parse_transit_route(self.route)
        self.assertEqual(len(result.legs), 2)
        self.assertAlmostEqual(result.legs[0]["distance_km"], 0.4509)
        self.assertEqual(result.legs[0], {
            "mode": None, "duration_minutes": None, "distance_km": 450.9 / 1000,
            "route": None, "from_name": None, "to_name": None, "geometry_points": None,
        })

    def test_malformed_optional_leg_fields_preserve_valid_summary(self):
        invalid_details = [
            {"mode": {}, "duration": True, "route": 123, "from": [], "to": {"name": []}, "legGeometry": []},
            {"mode": "UNKNOWN", "duration": -1, "route": "  ", "from": None, "to": None, "legGeometry": {"points": "bad space"}},
            {"duration": float("nan"), "legGeometry": {"points": 123}},
            {"duration": float("inf"), "legGeometry": {"points": "\u00e9"}},
            {"duration": "60", "legGeometry": {"points": ""}},
            {"duration": 10 ** 400, "legGeometry": {"points": "\n"}},
        ]
        for details in invalid_details:
            with self.subTest(details=details):
                data = copy.deepcopy(self.route)
                data["plan"]["itineraries"][0]["legs"][0].update(details)
                result = self.service._parse_transit_route(data)
                self.assertAlmostEqual(result.distance_km, 4.4509)
                for key in ("mode", "duration_minutes", "route", "from_name", "to_name", "geometry_points"):
                    self.assertIsNone(result.legs[0][key])

    def test_zero_duration_and_distance_are_valid_for_an_optional_leg(self):
        data = copy.deepcopy(self.route)
        data["plan"]["itineraries"][0]["legs"][0].update(distance=0, duration=0, mode="WALK")
        result = self.service._parse_transit_route(data)
        self.assertEqual(result.legs[0]["duration_minutes"], 0)
        self.assertEqual(result.legs[0]["distance_km"], 0)

    def test_route_constructor_keeps_legacy_calls_and_copies_leg_details(self):
        legacy = TransitRoute(1, 2, self.start, self.end)
        self.assertIsNone(legacy.legs)
        legs = [{"mode": "WALK"}]
        route = TransitRoute(1, 2, self.start, self.end, legs=legs)
        legs[0]["mode"] = "BUS"
        self.assertEqual(route.legs, [{"mode": "WALK"}])

    def test_utc_departure_converts_to_next_singapore_date(self):
        self.prepare()
        self.get_route(datetime(2026, 11, 12, 18, 30, tzinfo=timezone.utc))
        query = parse_qs(urlparse(self.opener.call_args.args[0].full_url).query)
        self.assertEqual(query["date"], ["11-13-2026"])
        self.assertEqual(query["time"], ["02:30:00"])

    def test_invalid_inputs_send_no_requests(self):
        cases = [
            ("12345", "654321", self.departure),
            ("012345", "ABC123", self.departure),
            ("012345", "654321", datetime(2026, 11, 12)),
            ("012345", "654321", "2026-11-12"),
        ]
        for args in cases:
            with self.subTest(args=args):
                home_postal, destination_postal, departure = args
                with self.assertRaises(ValidationError):
                    self.service.get_transit_route(home_postal, destination_postal, departure)
        self.opener.assert_not_called()

    def test_missing_token_sends_no_requests(self):
        service = GeoLocationService(token=" ", opener=self.opener)
        with self.assertRaises(GeoLocationError) as caught:
            service.get_transit_route("012345", "654321", self.departure)
        self.assertEqual(caught.exception.code, "AUTHENTICATION_ERROR")
        self.opener.assert_not_called()

    def test_token_can_come_from_environment(self):
        with patch.dict("os.environ", {"ONEMAP_ACCESS_TOKEN": " environment-token "}):
            self.service = GeoLocationService(opener=self.opener)
        self.prepare()
        self.get_route()
        request = self.opener.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "environment-token")

    def test_invalid_timeout_is_rejected(self):
        for timeout in (0, -1, True, "25", float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValidationError):
                    GeoLocationService(token="fake", timeout_seconds=timeout)

    def test_unrelated_search_result_is_ignored(self):
        self.prepare()
        first = self.lookup("012345")
        first["results"].insert(0, {"POSTAL": "999999"})
        self.opener.side_effect = [
            self.response(first),
            self.response(self.lookup("654321")),
            self.response(self.route),
        ]
        self.assertAlmostEqual(self.get_route().distance_km, 4.4509)

    def test_nonexistent_postal_stops_before_routing(self):
        for data in ({"results": []}, self.lookup("999999")):
            with self.subTest(data=data):
                self.opener.reset_mock()
                self.opener.side_effect = [self.response(data)]
                self.assert_error("LOCATION_NOT_FOUND", self.get_route)
                self.assertEqual(self.opener.call_count, 1)

    def test_unresolved_destination_stops_before_routing(self):
        self.opener.side_effect = [
            self.response(self.lookup("012345")),
            self.response({"results": []}),
        ]
        self.assert_error("LOCATION_NOT_FOUND", self.get_route)
        self.assertEqual(self.opener.call_count, 2)

    def test_malformed_search_results_are_rejected(self):
        invalid_responses = (
            {},
            {"results": None},
            {"results": {}},
            {"results": [None]},
            {"results": [{"POSTAL": "012345"}]},
        )
        for data in invalid_responses:
            with self.subTest(data=data):
                self.opener.side_effect = [self.response(data)]
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_invalid_coordinates_are_rejected(self):
        invalid_coordinates = (
            ("LATITUDE", None),
            ("LATITUDE", "abc"),
            ("LATITUDE", "nan"),
            ("LONGITUDE", "inf"),
            ("LATITUDE", 91),
            ("LONGITUDE", 181),
            ("LATITUDE", True),
        )
        for field, value in invalid_coordinates:
            with self.subTest(field=field, value=value):
                data = self.lookup("012345")
                data["results"][0][field] = value
                self.opener.side_effect = [self.response(data)]
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_http_failures_are_classified_at_search_and_route(self):
        http_failures = (
            (401, "AUTHENTICATION_ERROR"),
            (403, "AUTHENTICATION_ERROR"),
            (429, "QUOTA_EXCEEDED"),
            (500, "PROVIDER_ERROR"),
        )
        for status, code in http_failures:
            for stage in (0, 2):
                with self.subTest(status=status, stage=stage):
                    prefix = []
                    if stage == 2:
                        prefix.append(self.response(self.lookup("012345")))
                        prefix.append(self.response(self.lookup("654321")))
                    error = HTTPError("https://example.invalid/private", status, "private", {}, io.BytesIO(b"private"))
                    self.opener.side_effect = prefix + [error]
                    caught = self.assert_error(code, self.get_route)
                    error_traceback = "".join(traceback.format_exception(caught))
                    self.assertNotIn("example.invalid/private", error_traceback)

    def test_non_200_response_status_is_checked(self):
        self.opener.side_effect = [self.response({}, status=429)]
        self.assert_error("QUOTA_EXCEEDED", self.get_route)

    def test_network_and_timeout_errors_are_safe(self):
        network_failures = (
            (TimeoutError("private"), "TIMEOUT"),
            (URLError(TimeoutError("private")), "TIMEOUT"),
            (URLError("private"), "NETWORK_ERROR"),
            (ConnectionError("private"), "NETWORK_ERROR"),
        )
        for error, code in network_failures:
            with self.subTest(code=code):
                self.opener.side_effect = [error]
                self.assert_error(code, self.get_route)

    def test_http_200_provider_errors_override_result_shaped_data(self):
        cases = (
            ("Invalid token", "AUTHENTICATION_ERROR"),
            ("API limit exceeded", "QUOTA_EXCEEDED"),
            ("Unsupported mode", "UNSUPPORTED_MODE"),
            ("No route found", "NO_ROUTE"),
            ({"id": "PATH_NOT_FOUND"}, "NO_ROUTE"),
            ("Other rejection", "PROVIDER_ERROR"),
        )
        for message, code in cases:
            for field in ("error", "message"):
                with self.subTest(message=message, field=field):
                    data = self.lookup("012345")
                    data[field] = message
                    self.opener.side_effect = [self.response(data)]
                    self.assert_error(code, self.get_route)

    def test_invalid_json_encoding_and_top_level_types(self):
        for raw in (b"not json", b"\xff", b"[]", b"null", b'"text"'):
            with self.subTest(raw=raw):
                self.opener.side_effect = [self.response(raw, raw=True)]
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_no_itinerary_is_unavailable(self):
        for data in ({"plan": None}, {"plan": {"itineraries": []}}):
            with self.subTest(data=data):
                self.prepare(data)
                self.assert_error("NO_ROUTE", self.get_route)

    def test_malformed_route_structure_is_rejected(self):
        invalid_responses = (
            {"plan": []},
            {"plan": {}},
            {"plan": {"itineraries": {}}},
            {"plan": {"itineraries": [None]}},
        )
        for data in invalid_responses:
            with self.subTest(data=data):
                self.prepare(data)
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_invalid_itinerary_fields_are_rejected(self):
        cases = (
            ("duration", None),
            ("duration", 0),
            ("duration", -1),
            ("duration", True),
            ("duration", "1395"),
            ("duration", float("nan")),
            ("duration", float("inf")),
            ("duration", 10 ** 400),
            ("startTime", None),
            ("startTime", True),
            ("startTime", 1e100),
            ("endTime", None),
            ("endTime", 0),
            ("endTime", float("inf")),
            ("legs", []),
            ("legs", None),
            ("legs", [None]),
            ("legs", [{"distance": 10}, {}]),
            ("legs", [{"distance": -1}]),
            ("legs", [{"distance": 0}]),
            ("legs", [{"distance": True}]),
            ("legs", [{"distance": "20"}]),
            ("legs", [{"distance": float("nan")}]),
            ("legs", [{"distance": float("inf")}]),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.route)
                itinerary = data["plan"]["itineraries"][0]
                itinerary[field] = value
                self.prepare(data)
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_success_and_failure_do_not_print_private_data(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.prepare()
            self.get_route()
            self.opener.side_effect = [URLError("fake-secret 012345 654321")]
            error = self.assert_error("NETWORK_ERROR", self.get_route)
            self.opener.side_effect = [self.response({"error": "fake-secret 012345 654321"})]
            provider_error = self.assert_error("PROVIDER_ERROR", self.get_route)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        for error in (error, provider_error):
            for secret in ("fake-secret", "012345", "654321"):
                self.assertNotIn(secret, str(error))


if __name__ == "__main__":
    unittest.main()
