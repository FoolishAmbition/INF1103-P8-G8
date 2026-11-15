"""Postal validation and departure-based OneMap transit routing."""

import json
import math
import os
from copy import deepcopy
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


class TransitRoute:
    """Store the distance, duration and scheduled times returned by OneMap."""

    def __init__(
        self,
        distance_km,
        duration_minutes,
        departure_time,
        estimated_arrival,
        provider="OneMap",
        legs=None,
    ):
        self.distance_km = distance_km
        self.duration_minutes = duration_minutes
        self.departure_time = departure_time
        self.estimated_arrival = estimated_arrival
        self.provider = provider
        # Service details stay in memory; callers must not persist origin geometry.
        self.legs = deepcopy(legs)

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)


class GeoLocationError(EventWiseError):
    """A safe service failure, with a code callers can handle separately."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class GeoLocationService:
    """Resolve postal codes and retrieve departure-based public transport routes."""

    BASE_URL = "https://www.onemap.gov.sg"

    def __init__(self, token=None, opener=None, timeout_seconds=25):
        """Accept a token and an HTTP opener that tests can replace with a mock."""
        if token is None:
            token = os.environ.get("ONEMAP_ACCESS_TOKEN", "")
        self._token = ""
        if isinstance(token, str):
            self._token = token.strip()

        self._opener = opener
        if opener is None:
            self._opener = urlopen
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
            try:
                # Search returns coordinates as strings, unlike itinerary numbers.
                latitude = float(result["LATITUDE"])
                longitude = float(result["LONGITUDE"])
            except (KeyError, TypeError, ValueError, OverflowError):
                raise self._invalid_response() from None
            if isinstance(result["LATITUDE"], bool) or isinstance(result["LONGITUDE"], bool):
                raise self._invalid_response()
            if not math.isfinite(latitude) or not math.isfinite(longitude):
                raise self._invalid_response()
            if not -90 <= latitude <= 90:
                raise self._invalid_response()
            if not -180 <= longitude <= 180:
                raise self._invalid_response()
            return f"{latitude},{longitude}"
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

    @staticmethod
    def _check_http_status(status):
        if status in (401, 403):
            raise GeoLocationError("AUTHENTICATION_ERROR", "OneMap authentication failed.") from None
        if status == 429:
            raise GeoLocationError("QUOTA_EXCEEDED", "OneMap request limit was exceeded.") from None
        if status != 200:
            raise GeoLocationError("PROVIDER_ERROR", "OneMap request failed.") from None

    @staticmethod
    def _raise_provider_error(response):
        # Inspect provider text for classification only; never return it to callers.
        text = str(response.get("error") or response.get("message")).lower()
        authentication_words = ("token", "unauthor", "authentic", "access denied")
        for word in authentication_words:
            if word in text:
                raise GeoLocationError("AUTHENTICATION_ERROR", "OneMap authentication failed.")

        quota_words = ("quota", "limit exceeded", "too many requests")
        for word in quota_words:
            if word in text:
                raise GeoLocationError("QUOTA_EXCEEDED", "OneMap request limit was exceeded.")

        if "mode" in text:
            for word in ("unsupported", "invalid", "not supported"):
                if word in text:
                    raise GeoLocationError("UNSUPPORTED_MODE", "OneMap could not provide public transport.")

        for word in ("no route", "no transit", "path_not_found"):
            if word in text:
                raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        raise GeoLocationError("PROVIDER_ERROR", "OneMap rejected the request.")

    def _parse_transit_route(self, response):
        """Validate the first itinerary and convert its units for EventWise."""
        plan = response.get("plan")
        if plan is None:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        if not isinstance(plan, dict) or not isinstance(plan.get("itineraries"), list):
            raise self._invalid_response()
        itineraries = plan["itineraries"]
        if not itineraries:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        itinerary = itineraries[0]
        if not isinstance(itinerary, dict):
            raise self._invalid_response()
        duration_seconds = itinerary.get("duration")
        start_time_ms = itinerary.get("startTime")
        end_time_ms = itinerary.get("endTime")
        legs = itinerary.get("legs")
        if not self._is_number(duration_seconds) or duration_seconds <= 0:
            raise self._invalid_response()
        if not self._is_number(start_time_ms):
            raise self._invalid_response()
        if not self._is_number(end_time_ms):
            raise self._invalid_response()
        if end_time_ms <= start_time_ms:
            raise self._invalid_response()
        if not isinstance(legs, list) or not legs:
            raise self._invalid_response()
        distance_meters = 0.0
        for leg in legs:
            if not isinstance(leg, dict):
                raise self._invalid_response()
            leg_distance_meters = leg.get("distance")
            if not self._is_number(leg_distance_meters) or leg_distance_meters < 0:
                raise self._invalid_response()
            distance_meters += leg_distance_meters
        if not math.isfinite(distance_meters) or distance_meters <= 0:
            raise self._invalid_response()
        try:
            departure = datetime.fromtimestamp(start_time_ms / 1000, tz=SINGAPORE_TIMEZONE)
            arrival = datetime.fromtimestamp(end_time_ms / 1000, tz=SINGAPORE_TIMEZONE)
        except (ValueError, OverflowError, OSError):
            raise self._invalid_response() from None
        return TransitRoute(
            distance_km=distance_meters / 1000,
            duration_minutes=duration_seconds / 60,
            departure_time=departure,
            estimated_arrival=arrival,
            legs=[self._parse_leg(leg) for leg in legs],
        )

    def _parse_leg(self, leg):
        """Keep selected optional fields; bad detail must not discard a valid summary."""
        mode = leg.get("mode")
        if mode not in ("WALK", "BUS", "SUBWAY", "RAIL", "TRAM", "FERRY"):
            mode = None
        duration = leg.get("duration")
        duration_minutes = None
        if self._is_number(duration) and duration >= 0:
            duration_minutes = duration / 60
        geometry = leg.get("legGeometry")
        points = None
        if isinstance(geometry, dict):
            candidate = geometry.get("points")
            # Encoded polylines use ASCII 63..126. This checks encoding shape,
            # not decoded coordinates; map rendering needs separate validation.
            if isinstance(candidate, str) and candidate and all(63 <= ord(c) <= 126 for c in candidate):
                points = candidate
        return {
            "mode": mode,
            "distance_km": leg["distance"] / 1000,
            "duration_minutes": duration_minutes,
            "route": self._optional_text(leg.get("route")),
            "from_name": self._place_name(leg.get("from")),
            "to_name": self._place_name(leg.get("to")),
            "geometry_points": points,
        }

    @staticmethod
    def _optional_text(value):
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _place_name(self, place):
        if isinstance(place, dict):
            return self._optional_text(place.get("name"))
        return None

    @staticmethod
    def _is_number(value):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    @staticmethod
    def _invalid_response():
        return GeoLocationError("INVALID_RESPONSE", "OneMap returned invalid or incomplete data.")
