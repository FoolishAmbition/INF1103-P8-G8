"""Shared departure-based journey orchestration, independent of any UI or storage."""

from datetime import datetime, timedelta

from src.exceptions import ValidationError
from src.geolocation import GeoLocationError, SINGAPORE_TIMEZONE, validate_singapore_postal_code
from src.travel_assessment import TravelAssessment


class JourneyPlanner:
    """Coordinate an existing routing service and evaluator with one route recheck."""

    def __init__(self, geolocation_service, evaluator, clock=None):
        self._service = geolocation_service
        self._evaluator = evaluator
        self._clock = clock or self._now

    @staticmethod
    def _now():
        return datetime.now(SINGAPORE_TIMEZONE)

    def plan(self, origin_postal_code=None, destination_postal_code=None, event_start=None, *, enabled=True):
        """Return (assessment, error_code), or (None, None) for an explicit skip.

        An origin is a journey input, never a profile edit. The caller selects
        saved home or an alternate origin before calling. Provider errors retain
        their codes; the JSON adapter supplies fixed safe messages for web users.
        """
        if not isinstance(enabled, bool):
            raise ValidationError("Travel enabled must be a boolean.")
        if not enabled:
            return None, None

        unavailable = TravelAssessment(
            status="UNAVAILABLE", feasibility="UNAVAILABLE",
            arrival_buffer_minutes=self._evaluator.arrival_buffer_minutes,
            error_message="Travel details could not be assessed reliably.",
        )
        try:
            event_start = self._evaluator._singapore_datetime(event_start, "Event start")
            if not origin_postal_code:
                unavailable.error_message = "Add a home postal code in Profile to get travel advice."
                return unavailable, "MISSING_ORIGIN"
            validate_singapore_postal_code(origin_postal_code)
            validate_singapore_postal_code(destination_postal_code)
            now = self._clock()
            if event_start <= now:
                unavailable.error_message = "The event start time has already passed."
                return unavailable, "EVENT_PAST"

            initial_departure = event_start - timedelta(
                minutes=60 + self._evaluator.arrival_buffer_minutes
            )
            if initial_departure < now:
                initial_departure = now
            first_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, initial_departure
            )
            first_assessment = self._evaluator.evaluate(event_start, first_route)
            proposed_departure = first_assessment.recommended_departure
            if proposed_departure <= self._clock():
                unavailable.error_message = "The calculated departure time has already passed."
                return unavailable, "DEPARTURE_PAST"

            checked_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, proposed_departure
            )
            assessment = self._evaluator.evaluate(event_start, checked_route)
            # Pair the returned arrival with the departure actually requested.
            assessment.recommended_departure = proposed_departure
            return assessment, None
        except GeoLocationError as error:
            unavailable.error_message = str(error)
            return unavailable, error.code
        except (ValidationError, OverflowError):
            return unavailable, "INVALID_INPUT"
