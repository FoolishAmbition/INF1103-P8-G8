"""Departure estimates and journey-length assessments for EventWise."""

import math
from datetime import datetime, timedelta

from src.exceptions import ValidationError
from src.geolocation import SINGAPORE_TIMEZONE, TransitRoute


class TravelAssessment:
    """Travel details ready for the later application display."""

    def __init__(
        self,
        status,
        feasibility,
        arrival_buffer_minutes,
        distance_km=None,
        duration_minutes=None,
        recommended_departure=None,
        estimated_arrival=None,
        provider="OneMap",
        error_message=None,
    ):
        self.status = status
        self.feasibility = feasibility
        self.arrival_buffer_minutes = arrival_buffer_minutes
        self.distance_km = distance_km
        self.duration_minutes = duration_minutes
        self.recommended_departure = recommended_departure
        self.estimated_arrival = estimated_arrival
        self.provider = provider
        self.error_message = error_message

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)


class TravelEvaluator:
    """Calculate travel advice using an already retrieved transit itinerary."""

    def __init__(self, arrival_buffer_minutes=15, preferred_limit_minutes=60):
        self._validate_number(arrival_buffer_minutes, "Arrival buffer", allow_zero=True)
        self._validate_number(preferred_limit_minutes, "Preferred journey limit")
        self.arrival_buffer_minutes = arrival_buffer_minutes
        self.preferred_limit_minutes = preferred_limit_minutes

    def evaluate(self, event_start, route=None):
        """Return an assessment, using None when a reliable route is unavailable.

        The recommendation subtracts journey duration and buffer from event start.
        Estimated arrival retains the supplied itinerary's time. A later routing
        request at the recommended departure can produce a different itinerary.
        """
        event_start = self._singapore_datetime(event_start, "Event start")
        if route is None:
            return TravelAssessment(
                status="UNAVAILABLE",
                feasibility="UNAVAILABLE",
                arrival_buffer_minutes=self.arrival_buffer_minutes,
                error_message="Reliable transit information is unavailable.",
            )
        if not isinstance(route, TransitRoute):
            raise ValidationError("Route must be a TransitRoute or None.")
        self._validate_number(route.duration_minutes, "Journey duration")
        self._validate_number(route.distance_km, "Journey distance")
        departure = self._singapore_datetime(route.departure_time, "Itinerary departure")
        arrival = self._singapore_datetime(route.estimated_arrival, "Estimated arrival")
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
        )

    @staticmethod
    def _singapore_datetime(value, name):
        """Require an explicit timezone so the computer's timezone cannot affect advice."""
        if not isinstance(value, datetime):
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        try:
            return value.astimezone(SINGAPORE_TIMEZONE)
        except (OverflowError, ValueError):
            raise ValidationError(f"{name} exceeds the supported date range.") from None

    @staticmethod
    def _validate_number(value, name, allow_zero=False):
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
