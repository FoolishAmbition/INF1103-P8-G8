"""Postal validation and departure-based OneMap transit routing."""

import json
import math
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from src.exceptions import EventWiseError, ValidationError


SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")


def validate_singapore_postal_code(postal_code: str) -> str:
    """Return a valid six-digit postal code, preserving any leading zero."""
    if not isinstance(postal_code, str):
        raise ValidationError("Singapore postal code must be a string.")

    if len(postal_code) != 6 or not postal_code.isascii() or not postal_code.isdigit():
        raise ValidationError("Singapore postal code must contain exactly six digits.")

    return postal_code


class GeoLocationError(EventWiseError):
    """A safe service failure, with a code callers can handle separately."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class TransitRoute:
    """Store the distance, duration and scheduled times returned by OneMap."""

    def __init__(
        self,
        distance_km,
        duration_minutes,
        departure_time,
        estimated_arrival,
        provider="OneMap",
    ):
        self.distance_km = distance_km
        self.duration_minutes = duration_minutes
        self.departure_time = departure_time
        self.estimated_arrival = estimated_arrival
        self.provider = provider

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)

    @classmethod
    def from_onemap_response(cls, response: dict) -> "TransitRoute":
        """Factory Method: Validate and construct a TransitRoute from OneMap API JSON.

        Encapsulates response schema validation, leg distance accumulation,
        and unit conversion (meters->km, seconds->minutes, timestamps->datetimes).
        """
        if not isinstance(response, dict):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")

        plan = response.get("plan")
        if plan is None:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        if not isinstance(plan, dict):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")

        itineraries = plan.get("itineraries")
        if not isinstance(itineraries, list):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
        if not itineraries:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")

        itinerary = itineraries[0]
        if not isinstance(itinerary, dict):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")

        duration_seconds = itinerary.get("duration")
        start_time_ms = itinerary.get("startTime")
        end_time_ms = itinerary.get("endTime")
        legs = itinerary.get("legs")

        # Validate numeric bounds and itinerary structure
        if not cls._is_valid_number(duration_seconds, min_val=0, allow_zero=False):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
        if not cls._is_valid_number(start_time_ms) or not cls._is_valid_number(end_time_ms):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
        if end_time_ms <= start_time_ms:
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
        if not isinstance(legs, list) or not legs:
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")

        distance_meters = cls._sum_leg_distances(legs)

        try:
            departure = datetime.fromtimestamp(start_time_ms / 1000, tz=SINGAPORE_TIMEZONE)
            arrival = datetime.fromtimestamp(end_time_ms / 1000, tz=SINGAPORE_TIMEZONE)
        except (ValueError, OverflowError, OSError):
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.") from None

        return cls(
            distance_km=distance_meters / 1000,
            duration_minutes=duration_seconds / 60,
            departure_time=departure,
            estimated_arrival=arrival,
            provider="OneMap",
        )

    @classmethod
    def _sum_leg_distances(cls, legs: list) -> float:
        """Sum distance across all route legs, ensuring non-negative finite values."""
        total_meters = 0.0
        for leg in legs:
            if not isinstance(leg, dict):
                raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
            leg_distance = leg.get("distance")
            if not cls._is_valid_number(leg_distance, min_val=0, allow_zero=True):
                raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
            total_meters += leg_distance

        if not math.isfinite(total_meters) or total_meters <= 0:
            raise GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
        return total_meters

    @staticmethod
    def _is_valid_number(value, min_val=None, allow_zero=True) -> bool:
        """Return True if value is a real finite number (rejecting booleans)."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            if not math.isfinite(value):
                return False
        except OverflowError:
            return False

        if min_val is not None:
            if allow_zero and value < min_val:
                return False
            if not allow_zero and value <= min_val:
                return False
        return True


class GeoLocationService:
    """Resolve postal codes and retrieve departure-based public transport routes."""

    BASE_URL = "https://www.onemap.gov.sg"

    # Declarative HTTP status code mapping (Open/Closed Principle)
    _HTTP_STATUS_ERRORS = {
        401: ("AUTHENTICATION_ERROR", "OneMap authentication failed."),
        403: ("AUTHENTICATION_ERROR", "OneMap authentication failed."),
        429: ("QUOTA_EXCEEDED", "OneMap request limit was exceeded."),
    }

    # Declarative keyword matching rules for provider error classification
    _PROVIDER_ERROR_RULES = [
        (("token", "unauthor", "authentic", "access denied"), "AUTHENTICATION_ERROR", "OneMap authentication failed."),
        (("quota", "limit exceeded", "too many requests"), "QUOTA_EXCEEDED", "OneMap request limit was exceeded."),
        (("no route", "no transit", "path_not_found"), "NO_ROUTE", "OneMap returned no transit itinerary."),
    ]

    validate_postal_code = staticmethod(validate_singapore_postal_code)

    def __init__(self, token=None, opener=None, timeout_seconds=25):
        """Accept a token and an HTTP opener that tests can replace with a mock."""
        if token is None:
            token = os.environ.get("ONEMAP_ACCESS_TOKEN", "")
        self._token = ""
        if isinstance(token, str):
            self._token = token.strip()

        self._opener = opener if opener is not None else urlopen
        if not self._is_number(timeout_seconds) or timeout_seconds <= 0:
            raise ValidationError("Request timeout must be a positive number.")
        self._timeout_seconds = timeout_seconds

    def get_transit_route(self, home_postal_code, destination_postal_code, departure_time):
        """Resolve two postals and request one itinerary at the supplied departure."""
        validate_singapore_postal_code(home_postal_code)
        validate_singapore_postal_code(destination_postal_code)
        if (
            not isinstance(departure_time, datetime)
            or departure_time.tzinfo is None
            or departure_time.utcoffset() is None
        ):
            raise ValidationError("Departure must be a timezone-aware datetime.")
        if not self._token:
            raise GeoLocationError("AUTHENTICATION_ERROR", "OneMap access token is missing.")

        departure_time = departure_time.astimezone(SINGAPORE_TIMEZONE)
        origin = self._resolve_postal_code(home_postal_code)
        destination = self._resolve_postal_code(destination_postal_code)
        response = self._request_json(
            "/api/public/routingsvc/route",
            {
                "start": origin,
                "end": destination,
                "routeType": "pt",
                "date": departure_time.strftime("%m-%d-%Y"),
                "time": departure_time.strftime("%H:%M:%S"),
                "mode": "TRANSIT",
                "maxWalkDistance": 1000,
                "numItineraries": 1,
            },
        )
        return self._parse_transit_route(response)

    def _resolve_postal_code(self, postal_code):
        """Return latitude and longitude for an exact postal-code match."""
        response = self._request_json(
            "/api/common/elastic/search",
            {
                "searchVal": postal_code,
                "returnGeom": "Y",
                "getAddrDetails": "Y",
                "pageNum": 1,
            },
        )
        results = response.get("results")
        if not isinstance(results, list):
            raise self._invalid_response()

        for result in results:
            if not isinstance(result, dict):
                raise self._invalid_response()
            if result.get("POSTAL") != postal_code:
                continue

            lat_val = result.get("LATITUDE")
            lon_val = result.get("LONGITUDE")
            if isinstance(lat_val, bool) or isinstance(lon_val, bool):
                raise self._invalid_response()

            try:
                lat = float(lat_val)
                lon = float(lon_val)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180 and math.isfinite(lat) and math.isfinite(lon)):
                    raise ValueError
                return f"{lat},{lon}"
            except (KeyError, TypeError, ValueError, OverflowError):
                raise self._invalid_response() from None

        raise GeoLocationError("LOCATION_NOT_FOUND", "No exact postal-code location was found.")

    def _request_json(self, path, params):
        """Send one HTTP request and translate failures into safe service errors."""
        request = Request(
            f"{self.BASE_URL}{path}?{urlencode(params)}",
            headers={"Authorization": self._token},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                self._check_http_status(response.status)
                response_bytes = response.read()
                response_text = response_bytes.decode("utf-8")
                data = json.loads(response_text)
        except HTTPError as error:
            # Do not include provider bodies or exception URLs in public errors.
            status = error.code
            error.close()
            self._check_http_status(status)
            raise GeoLocationError("PROVIDER_ERROR", "OneMap request failed.") from None
        except TimeoutError:
            raise GeoLocationError("TIMEOUT", "OneMap request timed out.") from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise GeoLocationError("TIMEOUT", "OneMap request timed out.") from None
            raise GeoLocationError("NETWORK_ERROR", "Could not connect to OneMap.") from None
        except OSError:
            raise GeoLocationError("NETWORK_ERROR", "Could not connect to OneMap.") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise self._invalid_response() from None

        if not isinstance(data, dict):
            raise self._invalid_response()
        if data.get("error") or data.get("message"):
            self._raise_provider_error(data)
        return data

    @classmethod
    def _check_http_status(cls, status):
        """Map HTTP error status codes to safe domain exceptions."""
        if status == 200:
            return
        code, message = cls._HTTP_STATUS_ERRORS.get(
            status, ("PROVIDER_ERROR", "OneMap request failed.")
        )
        raise GeoLocationError(code, message)

    @classmethod
    def _raise_provider_error(cls, response):
        """Classify provider error payload into a sanitized domain exception."""
        text = str(response.get("error") or response.get("message")).lower()

        for keywords, code, message in cls._PROVIDER_ERROR_RULES:
            if any(keyword in text for keyword in keywords):
                raise GeoLocationError(code, message)

        if "mode" in text and any(w in text for w in ("unsupported", "invalid", "not supported")):
            raise GeoLocationError("UNSUPPORTED_MODE", "OneMap could not provide public transport.")

        raise GeoLocationError("PROVIDER_ERROR", "OneMap rejected the request.")

    def _parse_transit_route(self, response):
        """Delegate route parsing to TransitRoute factory method."""
        return TransitRoute.from_onemap_response(response)

    @staticmethod
    def _is_number(value):
        """Check if value is a finite number, excluding booleans."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    @staticmethod
    def _invalid_response():
        return GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
