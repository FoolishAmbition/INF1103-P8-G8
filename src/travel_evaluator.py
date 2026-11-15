"""Calculate travel advice from an already retrieved transit itinerary."""

import math
from datetime import datetime, timedelta

from src.exceptions import ValidationError
from src.geolocation_utils import GeoLocationUtils
from src.transit_route import TransitRoute
from src.travel_assessment import TravelAssessment


class TravelEvaluator:
    """Calculate departure estimates and journey feasibility."""

    def __init__(self, arrival_buffer_minutes=15, preferred_limit_minutes=60):
        self.validate_number(arrival_buffer_minutes, "Arrival buffer", allow_zero=True)
        self.validate_number(preferred_limit_minutes, "Preferred journey limit")
        self._arrival_buffer_minutes = arrival_buffer_minutes
        self._preferred_limit_minutes = preferred_limit_minutes

    @property
    def arrival_buffer_minutes(self):
        return self._arrival_buffer_minutes

    @property
    def preferred_limit_minutes(self):
        return self._preferred_limit_minutes

    def evaluate(self, event_start, route=None):
        """Return an assessment, using None when a reliable route is unavailable.

        The recommendation subtracts journey duration and buffer from event start.
        Estimated arrival retains the supplied itinerary's time. A later routing
        request at the recommended departure can produce a different itinerary.
        """
        event_start = self.to_singapore_datetime(event_start, "Event start")
        if route is None:
            return TravelAssessment(
                status="UNAVAILABLE",
                feasibility="UNAVAILABLE",
                arrival_buffer_minutes=self.arrival_buffer_minutes,
                error_message="Reliable transit information is unavailable.",
                error_code="TRAVEL_UNAVAILABLE",
                event_start=event_start,
                preferred_limit_minutes=self.preferred_limit_minutes,
            )
        if not isinstance(route, TransitRoute):
            raise ValidationError("Route must be a TransitRoute or None.")
        self.validate_number(route.duration_minutes, "Journey duration")
        self.validate_number(route.distance_km, "Journey distance")
        departure = self.to_singapore_datetime(route.departure_time, "Itinerary departure")
        arrival = self.to_singapore_datetime(route.estimated_arrival, "Estimated arrival")
        if arrival <= departure:
            raise ValidationError("Estimated arrival must follow itinerary departure.")

        try:
            journey_duration = timedelta(minutes=route.duration_minutes)
            arrival_buffer = timedelta(minutes=self.arrival_buffer_minutes)
            recommended_departure = event_start - journey_duration - arrival_buffer
        except OverflowError:
            raise ValidationError("Journey duration or buffer exceeds the supported date range.") from None

        feasibility = "WITHIN_LIMIT"
        if route.duration_minutes > self.preferred_limit_minutes:
            feasibility = "LONG_JOURNEY"
        return TravelAssessment(
            status="AVAILABLE",
            feasibility=feasibility,
            arrival_buffer_minutes=self.arrival_buffer_minutes,
            distance_km=route.distance_km,
            duration_minutes=route.duration_minutes,
            recommended_departure=recommended_departure,
            estimated_arrival=arrival,
            provider=route.provider,
            event_start=event_start,
            preferred_limit_minutes=self.preferred_limit_minutes,
        )

    @staticmethod
    def to_singapore_datetime(value, name):
        """Require an explicit timezone so the computer's timezone cannot affect advice."""
        if not isinstance(value, datetime):
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        try:
            return value.astimezone(GeoLocationUtils.SINGAPORE_TIMEZONE)
        except (OverflowError, ValueError):
            raise ValidationError(f"{name} exceeds the supported date range.") from None

    @staticmethod
    def validate_number(value, name, allow_zero=False):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValidationError(f"{name} must be a finite number.")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValidationError(f"{name} must be a finite number.")
        if value < 0:
            raise ValidationError(f"{name} is outside the allowed range.")
        if value == 0 and not allow_zero:
            raise ValidationError(f"{name} is outside the allowed range.")
