"""Shared departure-based journey orchestration, independent of any UI or storage."""

from datetime import datetime, timedelta

from src.exceptions import ValidationError
from src.geolocation import GeoLocationError
from src.geolocation_utils import GeoLocationUtils
from src.travel_assessment import TravelAssessment
from src.travel_evaluator import TravelEvaluator
from src.transit_routing_service import TransitRoutingService


class JourneyPlanner(GeoLocationUtils):
    """Coordinate an existing routing service and evaluator with one route recheck."""

    def __init__(
        self,
        geolocation_service: TransitRoutingService,
        evaluator: TravelEvaluator,
        clock=None,
    ):
        self._service = geolocation_service
        self._evaluator = evaluator
        self._clock = clock or self._now

    @property
    def arrival_buffer_minutes(self):
        return self._evaluator.arrival_buffer_minutes

    @property
    def preferred_limit_minutes(self):
        return self._evaluator.preferred_limit_minutes

    @staticmethod
    def _now():
        return datetime.now(GeoLocationUtils.SINGAPORE_TIMEZONE)

    def _unavailable_assessment(self, error_code=None, message=None, event_start=None):
        return TravelAssessment(
            status="UNAVAILABLE",
            feasibility="UNAVAILABLE",
            arrival_buffer_minutes=self._evaluator.arrival_buffer_minutes,
            error_message=message or "Travel details could not be assessed reliably.",
            error_code=error_code,
            event_start=event_start,
            preferred_limit_minutes=self._evaluator.preferred_limit_minutes,
        )

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

        event_start_singapore = None
        try:
            event_start_singapore = self._evaluator.to_singapore_datetime(
                event_start, "Event start"
            )
            if not origin_postal_code:
                code = "MISSING_ORIGIN"
                return self._unavailable_assessment(
                    code,
                    "Add a home postal code in Profile to get travel advice.",
                    event_start_singapore,
                ), code
            self.validate_singapore_postal_code(origin_postal_code)
            self.validate_singapore_postal_code(destination_postal_code)
            now = self._clock()
            if event_start_singapore <= now:
                code = "EVENT_PAST"
                return self._unavailable_assessment(
                    code, "The event start time has already passed.", event_start_singapore
                ), code

            initial_departure = event_start_singapore - timedelta(
                minutes=60 + self._evaluator.arrival_buffer_minutes
            )
            if initial_departure < now:
                initial_departure = now
            first_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, initial_departure
            )
            first_assessment = self._evaluator.evaluate(event_start_singapore, first_route)
            if first_assessment.status == "UNAVAILABLE":
                return first_assessment, first_assessment.error_code
            proposed_departure = first_assessment.recommended_departure
            if proposed_departure <= self._clock():
                code = "DEPARTURE_PAST"
                return self._unavailable_assessment(
                    code,
                    "The calculated departure time has already passed.",
                    event_start_singapore,
                ), code

            checked_route = self._service.get_transit_route(
                origin_postal_code, destination_postal_code, proposed_departure
            )
            assessment = self._evaluator.evaluate(event_start_singapore, checked_route)
            if assessment.status == "UNAVAILABLE":
                return assessment, assessment.error_code
            return assessment.with_recommended_departure(proposed_departure), None
        except GeoLocationError as error:
            return self._unavailable_assessment(
                error.code, str(error), event_start_singapore
            ), error.code
        except (ValidationError, OverflowError):
            code = "INVALID_INPUT"
            return self._unavailable_assessment(
                code, event_start=event_start_singapore
            ), code
