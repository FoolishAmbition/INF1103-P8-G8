"""Sanitized travel response data for the web interface."""

from datetime import timedelta

from src.exceptions import ValidationError
from src.travel_assessment import TravelAssessment
from src.travel_evaluator import TravelEvaluator


class TravelResult:
    """Convert a travel assessment into the stable, privacy-safe GUI schema."""

    _ERROR_MESSAGES = {
        "MISSING_ORIGIN": "Choose another postal code or add a saved home before planning travel.",
        "EVENT_PAST": "The event start time has already passed.",
        "DEPARTURE_PAST": "The estimated departure time has already passed.",
        "INVALID_INPUT": "Check the journey postal codes and timezone-aware event start time.",
        "TRAVEL_UNAVAILABLE": "Reliable transit information is unavailable.",
        "AUTHENTICATION_ERROR": "The transit service is temporarily unavailable.",
        "LOCATION_NOT_FOUND": "A postal-code location could not be found.",
        "TIMEOUT": "The transit service took too long to respond.",
        "NETWORK_ERROR": "Could not connect to the transit service.",
        "QUOTA_EXCEEDED": "The transit service request limit was reached.",
        "NO_ROUTE": "No public-transport journey was found.",
        "UNSUPPORTED_MODE": "Public transport is unavailable for this journey.",
        "INVALID_RESPONSE": "The transit service returned incomplete information.",
        "PROVIDER_ERROR": "The transit service could not provide a journey.",
    }

    def __init__(self, assessment: TravelAssessment | None = None):
        if assessment is not None and not isinstance(assessment, TravelAssessment):
            raise ValidationError("Assessment must be a TravelAssessment or None.")
        self._assessment = assessment

    def to_dict(self) -> dict:
        assessment = self._assessment
        status = "SKIPPED" if assessment is None else assessment.status
        if assessment is not None and status not in ("AVAILABLE", "UNAVAILABLE"):
            raise ValidationError("Assessment status must be AVAILABLE or UNAVAILABLE.")
        if (
            assessment is not None
            and assessment.error_code is not None
            and status != "UNAVAILABLE"
        ):
            raise ValidationError("Only unavailable travel can have an error code.")

        preferred_limit = (
            None if assessment is None else assessment.preferred_limit_minutes
        )
        if preferred_limit is not None:
            TravelEvaluator.validate_number(preferred_limit, "Preferred journey limit")

        result = {
            "schema_version": 1,
            "status": status,
            "transport_mode": "PUBLIC_TRANSPORT",
            "provider": None,
            "distance_km": None,
            "duration_minutes": None,
            "recommended_departure": None,
            "estimated_arrival": None,
            "arrival_buffer_minutes": None,
            "preferred_travel_limit_minutes": preferred_limit,
            "feasibility": None,
            "warning_codes": None,
            "legs": None,
            "alternatives": None,
            "error_code": None,
            "error_message": None,
        }
        if status == "SKIPPED":
            return result

        TravelEvaluator.validate_number(
            assessment.arrival_buffer_minutes, "Arrival buffer", allow_zero=True
        )
        result["arrival_buffer_minutes"] = assessment.arrival_buffer_minutes
        result["provider"] = "OneMap"

        if status == "UNAVAILABLE":
            error_code = assessment.error_code
            if not isinstance(error_code, str) or error_code not in self._ERROR_MESSAGES:
                error_code = "TRAVEL_UNAVAILABLE"
            result["feasibility"] = "UNAVAILABLE"
            result["error_code"] = error_code
            result["error_message"] = self._ERROR_MESSAGES[error_code]
            return result

        if assessment.feasibility not in ("WITHIN_LIMIT", "LONG_JOURNEY"):
            raise ValidationError("Available travel must have a valid feasibility.")
        TravelEvaluator.validate_number(assessment.distance_km, "Journey distance")
        TravelEvaluator.validate_number(assessment.duration_minutes, "Journey duration")
        departure = TravelEvaluator.to_singapore_datetime(
            assessment.recommended_departure, "Departure"
        )
        arrival = TravelEvaluator.to_singapore_datetime(
            assessment.estimated_arrival, "Arrival"
        )
        result.update(
            distance_km=assessment.distance_km,
            duration_minutes=assessment.duration_minutes,
            recommended_departure=departure.isoformat(),
            estimated_arrival=arrival.isoformat(),
            feasibility=assessment.feasibility,
        )

        if assessment.event_start is not None:
            event_start = TravelEvaluator.to_singapore_datetime(
                assessment.event_start, "Event start"
            )
            try:
                target_arrival = event_start - timedelta(
                    minutes=assessment.arrival_buffer_minutes
                )
            except OverflowError:
                raise ValidationError(
                    "Arrival buffer exceeds the supported date range."
                ) from None
            warnings = []
            if arrival > event_start:
                warnings.append("EVENT_START_MISSED")
            elif arrival > target_arrival:
                warnings.append("BUFFER_MISSED")
            result["warning_codes"] = warnings

        return result
