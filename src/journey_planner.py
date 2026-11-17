"""Shared departure-based journey orchestration and transit schedule evaluation."""

import math
from datetime import datetime, timedelta

from src.exceptions import ValidationError, GeoLocationError
from src.geolocation_service import GeoLocationService
from src.transit_routing_service import TransitRoutingService
from src.travel_result import TravelResult


class JourneyPlanner:
    """Coordinate transit routing and evaluate travel advice with a two-pass schedule check."""

    def __init__(
        self,
        geolocation_service: TransitRoutingService | None = None,
        arrival_buffer_minutes=15,
        preferred_limit_minutes=60,
        clock=None,
    ):
        if hasattr(arrival_buffer_minutes, "arrival_buffer_minutes"):
            if hasattr(arrival_buffer_minutes, "preferred_limit_minutes"):
                preferred_limit_minutes = arrival_buffer_minutes.preferred_limit_minutes
            arrival_buffer_minutes = arrival_buffer_minutes.arrival_buffer_minutes

        self.validate_number(arrival_buffer_minutes, "Arrival buffer", allow_zero=True)
        self.validate_number(preferred_limit_minutes, "Preferred journey limit")
        self._service = geolocation_service
        self._arrival_buffer_minutes = arrival_buffer_minutes
        self._preferred_limit_minutes = preferred_limit_minutes
        self._clock = clock or self._now

    @property
    def arrival_buffer_minutes(self):
        return self._arrival_buffer_minutes

    @property
    def preferred_limit_minutes(self):
        return self._preferred_limit_minutes

    @staticmethod
    def _now():
        return datetime.now(GeoLocationService.SINGAPORE_TIMEZONE)

    def _unavailable_assessment(self, error_code=None, message=None, event_start=None):
        return TravelResult(
            status="UNAVAILABLE",
            feasibility="UNAVAILABLE",
            arrival_buffer_minutes=self.arrival_buffer_minutes,
            error_message=message or "Travel details could not be assessed reliably.",
            error_code=error_code,
            event_start=event_start,
            preferred_limit_minutes=self.preferred_limit_minutes,
        )

    def evaluate(self, event_start, route=None) -> TravelResult:
        """Calculate departure estimates and journey feasibility from a transit route."""
        event_start = self.to_singapore_datetime(event_start, "Event start")
        if route is None:
            return TravelResult(
                status="UNAVAILABLE",
                feasibility="UNAVAILABLE",
                arrival_buffer_minutes=self.arrival_buffer_minutes,
                error_message="Reliable transit information is unavailable.",
                error_code="TRAVEL_UNAVAILABLE",
                event_start=event_start,
                preferred_limit_minutes=self.preferred_limit_minutes,
            )
        if not isinstance(route, TravelResult):
            raise ValidationError("Route must be a TravelResult or None.")
        self.validate_number(route.duration_minutes, "Journey duration")
        self.validate_number(route.distance_km, "Journey distance")
        dep_val = route.departure_time or route.recommended_departure
        departure = self.to_singapore_datetime(dep_val, "Itinerary departure")
        arrival = self.to_singapore_datetime(route.estimated_arrival, "Estimated arrival")
        if arrival <= departure:
            raise ValidationError("Estimated arrival must follow itinerary departure.")

        try:
            journey_duration = timedelta(minutes=route.duration_minutes)
            arrival_buffer = timedelta(minutes=self.arrival_buffer_minutes)
            recommended_departure = event_start - journey_duration - arrival_buffer
        except OverflowError:
            raise ValidationError(
                "Journey duration or buffer exceeds the supported date range."
            ) from None

        feasibility = "WITHIN_LIMIT"
        if route.duration_minutes > self.preferred_limit_minutes:
            feasibility = "LONG_JOURNEY"

        return TravelResult(
            status="AVAILABLE",
            feasibility=feasibility,
            arrival_buffer_minutes=self.arrival_buffer_minutes,
            distance_km=route.distance_km,
            duration_minutes=route.duration_minutes,
            departure_time=departure,
            recommended_departure=recommended_departure,
            estimated_arrival=arrival,
            provider=route.provider,
            event_start=event_start,
            preferred_limit_minutes=self.preferred_limit_minutes,
        )

    @staticmethod
    def to_singapore_datetime(value, name):
        """Require an explicit timezone so local computer timezones do not affect advice."""
        if not isinstance(value, datetime):
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        try:
            return value.astimezone(GeoLocationService.SINGAPORE_TIMEZONE)
        except (OverflowError, ValueError):
            raise ValidationError(f"{name} exceeds the supported date range.") from None

    @staticmethod
    def validate_number(value, name, allow_zero=False):
        """Validate that value is a finite number within the allowable range."""
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

    def plan(
        self,
        origin_postal_code=None,
        destination_postal_code=None,
        event_start=None,
        *,
        enabled=True,
    ):
        """Return (assessment, error_code), or (None, None) for an explicit skip.

        An origin is a journey input, never a profile edit. The caller selects
        saved home or an alternate origin before calling. Provider errors retain
        their codes; the JSON adapter supplies fixed safe messages for web users.
        """
        if not isinstance(enabled, bool):
            raise ValidationError("Travel enabled must be a boolean.")
        if not enabled:
            return None, None

        event_start_singapore = None
        try:
            event_start_singapore = self.to_singapore_datetime(
                event_start, "Event start"
            )
            if not origin_postal_code:
                code = "MISSING_ORIGIN"
                return (
                    self._unavailable_assessment(
                        code,
                        "Add a home postal code in Profile to get travel advice.",
                        event_start_singapore,
                    ),
                    code,
                )
            GeoLocationService.validate_singapore_postal_code(origin_postal_code)
            GeoLocationService.validate_singapore_postal_code(destination_postal_code)
            now = self._clock()
            if event_start_singapore <= now:
                code = "EVENT_PAST"
                return (
                    self._unavailable_assessment(
                        code,
                        "The event start time has already passed.",
                        event_start_singapore,
                    ),
                    code,
                )

            initial_departure = event_start_singapore - timedelta(
                minutes=60 + self.arrival_buffer_minutes
            )
            if initial_departure < now:
                initial_departure = now
            first_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, initial_departure
            )
            first_assessment = self.evaluate(event_start_singapore, first_route)
            if first_assessment.status == "UNAVAILABLE":
                return first_assessment, first_assessment.error_code
            proposed_departure = first_assessment.recommended_departure
            if proposed_departure <= self._clock():
                code = "DEPARTURE_PAST"
                return (
                    self._unavailable_assessment(
                        code,
                        "The calculated departure time has already passed.",
                        event_start_singapore,
                    ),
                    code,
                )

            checked_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, proposed_departure
            )
            assessment = self.evaluate(event_start_singapore, checked_route)
            if assessment.status == "UNAVAILABLE":
                return assessment, assessment.error_code
            return assessment.with_recommended_departure(proposed_departure), None
        except GeoLocationError as error:
            return (
                self._unavailable_assessment(
                    error.code, str(error), event_start_singapore
                ),
                error.code,
            )
        except (ValidationError, OverflowError):
            code = "INVALID_INPUT"
            return (
                self._unavailable_assessment(
                    code, event_start=event_start_singapore
                ),
                code,
            )
