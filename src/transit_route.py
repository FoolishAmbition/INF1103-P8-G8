"""Validated transit route data returned by OneMap."""

from datetime import datetime
import math

from src.geolocation_error import GeoLocationError
from src.geolocation_utils import GeoLocationUtils


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
        self._distance_km = distance_km
        self._duration_minutes = duration_minutes
        self._departure_time = departure_time
        self._estimated_arrival = estimated_arrival
        self._provider = provider

    @property
    def distance_km(self):
        return self._distance_km

    @property
    def duration_minutes(self):
        return self._duration_minutes

    @property
    def departure_time(self):
        return self._departure_time

    @property
    def estimated_arrival(self):
        return self._estimated_arrival

    @property
    def provider(self):
        return self._provider

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)

    @classmethod
    def from_onemap_response(cls, response: dict) -> "TransitRoute":
        """Validate and construct a route from OneMap API JSON."""
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
            departure = datetime.fromtimestamp(
                start_time_ms / 1000, tz=GeoLocationUtils.SINGAPORE_TIMEZONE
            )
            arrival = datetime.fromtimestamp(
                end_time_ms / 1000, tz=GeoLocationUtils.SINGAPORE_TIMEZONE
            )
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
        """Sum distance across route legs, ensuring non-negative finite values."""
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