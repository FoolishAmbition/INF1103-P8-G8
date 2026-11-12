"""Offline tests for GeoLocation input validation."""

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
        self.route = {"plan": {"itineraries": [{
            "duration": 1395,
            "startTime": self.start.timestamp() * 1000,
            "endTime": self.end.timestamp() * 1000,
            "legs": [{"distance": 450.9}, {"distance": 4000}],
        }]}}

    def response(self, data, status=200, raw=False):
        response = Mock()
        response.status = status
        response.read.return_value = data if raw else json.dumps(data).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def lookup(self, postal):
        return {"results": [{"POSTAL": postal, "LATITUDE": "1.3", "LONGITUDE": "103.8"}]}

    def prepare(self, route=None):
        self.opener.side_effect = [
            self.response(self.lookup("012345")),
            self.response(self.lookup("654321")),
            self.response(self.route if route is None else route),
        ]

    def get_route(self, departure=None):
        return self.service.get_transit_route(
            "012345", "654321", self.departure if departure is None else departure
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
        paths = [urlparse(call.args[0].full_url).path for call in self.opener.call_args_list]
        self.assertEqual(paths, ["/api/common/elastic/search"] * 2 + ["/api/public/routingsvc/route"])

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
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.service.get_transit_route(*args)
        self.opener.assert_not_called()

    def test_missing_token_sends_no_requests(self):
        service = GeoLocationService(token=" ", opener=self.opener)
        self.assert_error("AUTHENTICATION_ERROR", lambda: service.get_transit_route(
            "012345", "654321", self.departure
        ))
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
            with self.subTest(timeout=timeout), self.assertRaises(ValidationError):
                GeoLocationService(token="fake", timeout_seconds=timeout)

    def test_unrelated_search_result_is_ignored(self):
        self.prepare()
        first = self.lookup("012345")
        first["results"].insert(0, {"POSTAL": "999999"})
        self.opener.side_effect = [self.response(first), self.response(self.lookup("654321")), self.response(self.route)]
        self.assertAlmostEqual(self.get_route().distance_km, 4.4509)

    def test_nonexistent_postal_stops_before_routing(self):
        for data in ({"results": []}, self.lookup("999999")):
            with self.subTest(data=data):
                self.opener.reset_mock()
                self.opener.side_effect = [self.response(data)]
                self.assert_error("LOCATION_NOT_FOUND", self.get_route)
                self.assertEqual(self.opener.call_count, 1)

    def test_unresolved_destination_stops_before_routing(self):
        self.opener.side_effect = [self.response(self.lookup("012345")), self.response({"results": []})]
        self.assert_error("LOCATION_NOT_FOUND", self.get_route)
        self.assertEqual(self.opener.call_count, 2)

    def test_malformed_search_results_are_rejected(self):
        for data in ({}, {"results": None}, {"results": {}}, {"results": [None]}, {"results": [{"POSTAL": "012345"}]}):
            with self.subTest(data=data):
                self.opener.side_effect = [self.response(data)]
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_invalid_coordinates_are_rejected(self):
        for field, value in (("LATITUDE", None), ("LATITUDE", "abc"), ("LATITUDE", "nan"),
                             ("LONGITUDE", "inf"), ("LATITUDE", 91), ("LONGITUDE", 181),
                             ("LATITUDE", True)):
            with self.subTest(field=field, value=value):
                data = self.lookup("012345")
                data["results"][0][field] = value
                self.opener.side_effect = [self.response(data)]
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_http_failures_are_classified_at_search_and_route(self):
        for status, code in ((401, "AUTHENTICATION_ERROR"), (403, "AUTHENTICATION_ERROR"),
                             (429, "QUOTA_EXCEEDED"), (500, "PROVIDER_ERROR")):
            for stage in (0, 2):
                with self.subTest(status=status, stage=stage):
                    prefix = [self.response(self.lookup("012345")), self.response(self.lookup("654321"))][:stage]
                    error = HTTPError("https://example.invalid/private", status, "private", {}, io.BytesIO(b"private"))
                    self.opener.side_effect = prefix + [error]
                    caught = self.assert_error(code, self.get_route)
                    self.assertNotIn("example.invalid/private", "".join(traceback.format_exception(caught)))

    def test_non_200_response_status_is_checked(self):
        self.opener.side_effect = [self.response({}, status=429)]
        self.assert_error("QUOTA_EXCEEDED", self.get_route)

    def test_network_and_timeout_errors_are_safe(self):
        for error, code in ((TimeoutError("private"), "TIMEOUT"),
                            (URLError(TimeoutError("private")), "TIMEOUT"),
                            (URLError("private"), "NETWORK_ERROR"),
                            (ConnectionError("private"), "NETWORK_ERROR")):
            with self.subTest(code=code):
                self.opener.side_effect = [error]
                self.assert_error(code, self.get_route)

    def test_http_200_provider_errors_override_result_shaped_data(self):
        cases = (("Invalid token", "AUTHENTICATION_ERROR"), ("API limit exceeded", "QUOTA_EXCEEDED"),
                 ("Unsupported mode", "UNSUPPORTED_MODE"), ("No route found", "NO_ROUTE"),
                 ({"id": "PATH_NOT_FOUND"}, "NO_ROUTE"), ("Other rejection", "PROVIDER_ERROR"))
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
        for data in ({"plan": []}, {"plan": {}}, {"plan": {"itineraries": {}}},
                     {"plan": {"itineraries": [None]}}):
            with self.subTest(data=data):
                self.prepare(data)
                self.assert_error("INVALID_RESPONSE", self.get_route)

    def test_invalid_itinerary_fields_are_rejected(self):
        cases = (("duration", None), ("duration", 0), ("duration", -1), ("duration", True),
                 ("duration", "1395"), ("duration", float("nan")), ("duration", float("inf")),
                 ("duration", 10 ** 400),
                 ("startTime", None), ("startTime", True), ("startTime", 1e100),
                 ("endTime", None), ("endTime", 0), ("endTime", float("inf")),
                 ("legs", []), ("legs", None), ("legs", [None]),
                 ("legs", [{"distance": 10}, {}]),
                 ("legs", [{"distance": -1}]), ("legs", [{"distance": 0}]),
                 ("legs", [{"distance": True}]), ("legs", [{"distance": "20"}]),
                 ("legs", [{"distance": float("nan")}]),
                 ("legs", [{"distance": float("inf")}]))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.route)
                data["plan"]["itineraries"][0][field] = value
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
