"""Postal validation and departure-based OneMap transit routing."""

import json
import math
import os
from dataclasses import dataclass
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


@dataclass
class TransitRoute:
    """Provider itinerary only; arrival is an estimate, not a guarantee."""

    distance_km: float
    duration_minutes: float
    departure_time: datetime
    estimated_arrival: datetime
    provider: str = "OneMap"


class GeoLocationError(EventWiseError):
    """A safe service failure, with a code callers can handle separately."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class GeoLocationService:
    BASE_URL = "https://www.onemap.gov.sg"

    def __init__(self, token=None, opener=None, timeout_seconds=25):
        if token is None:
            token = os.environ.get("ONEMAP_ACCESS_TOKEN", "")
        self._token = token.strip() if isinstance(token, str) else ""
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
        response = self._request_json(
            "/api/common/elastic/search",
            {"searchVal": postal_code, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
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
            if (
                isinstance(result["LATITUDE"], bool)
                or isinstance(result["LONGITUDE"], bool)
                or not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise self._invalid_response()
            return f"{latitude},{longitude}"
        raise GeoLocationError("LOCATION_NOT_FOUND", "No exact postal-code location was found.")

    def _request_json(self, path, params):
        request = Request(
            f"{self.BASE_URL}{path}?{urlencode(params)}",
            headers={"Authorization": self._token},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                self._check_http_status(response.status)
                data = json.loads(response.read().decode("utf-8"))
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
        if any(word in text for word in ("token", "unauthor", "authentic", "access denied")):
            raise GeoLocationError("AUTHENTICATION_ERROR", "OneMap authentication failed.")
        if any(word in text for word in ("quota", "limit exceeded", "too many requests")):
            raise GeoLocationError("QUOTA_EXCEEDED", "OneMap request limit was exceeded.")
        if "mode" in text and any(word in text for word in ("unsupported", "invalid", "not supported")):
            raise GeoLocationError("UNSUPPORTED_MODE", "OneMap could not provide public transport.")
        if any(word in text for word in ("no route", "no transit", "path_not_found")):
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        raise GeoLocationError("PROVIDER_ERROR", "OneMap rejected the request.")

    def _parse_transit_route(self, response):
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
        duration = itinerary.get("duration")
        start = itinerary.get("startTime")
        end = itinerary.get("endTime")
        legs = itinerary.get("legs")
        if (
            not self._is_number(duration) or duration <= 0
            or not self._is_number(start) or not self._is_number(end) or end <= start
            or not isinstance(legs, list) or not legs
        ):
            raise self._invalid_response()
        distance_meters = 0.0
        for leg in legs:
            if not isinstance(leg, dict):
                raise self._invalid_response()
            distance = leg.get("distance")
            if not self._is_number(distance) or distance < 0:
                raise self._invalid_response()
            distance_meters += distance
        if not math.isfinite(distance_meters) or distance_meters <= 0:
            raise self._invalid_response()
        try:
            departure = datetime.fromtimestamp(start / 1000, tz=SINGAPORE_TIMEZONE)
            arrival = datetime.fromtimestamp(end / 1000, tz=SINGAPORE_TIMEZONE)
        except (ValueError, OverflowError, OSError):
            raise self._invalid_response() from None
        return TransitRoute(distance_meters / 1000, duration / 60, departure, arrival)

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
