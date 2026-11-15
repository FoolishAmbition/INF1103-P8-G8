"""Convert travel assessments into a small, privacy-safe GUI response."""

from datetime import timedelta

from src.exceptions import ValidationError
from src.travel_assessment import TravelAssessment, TravelEvaluator


ERROR_MESSAGES = {
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


def serialize_travel_result(
    assessment=None, *, preferred_limit_minutes=None, error_code=None, event_start=None
):
    """Return JSON-compatible data; None means the user skipped travel.

    Pass the evaluator's actual preferred limit when known. No route request is
    performed here. Error text comes from a fixed list, never exception messages.
    Supply event_start to assess lateness against the returned itinerary arrival.
    Without it, warnings remain unknown. Leg geometry is excluded; alternatives
    remain unimplemented. Current leg endpoint names must not be saved in history.
    """
    if assessment is not None and not isinstance(assessment, TravelAssessment):
        raise ValidationError("Assessment must be a TravelAssessment or None.")
    if preferred_limit_minutes is not None:
        TravelEvaluator._validate_number(preferred_limit_minutes, "Preferred journey limit")
    if event_start is not None:
        event_start = TravelEvaluator._singapore_datetime(event_start, "Event start")

    status = "SKIPPED"
    if assessment is not None:
        status = assessment.status
        if status not in ("AVAILABLE", "UNAVAILABLE"):
            raise ValidationError("Assessment status must be AVAILABLE or UNAVAILABLE.")
    if error_code is not None and status != "UNAVAILABLE":
        raise ValidationError("Only unavailable travel can have an error code.")

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
        "preferred_travel_limit_minutes": preferred_limit_minutes,
        "feasibility": None,
        "warning_codes": None,
        "legs": None,
        "alternatives": None,
        "error_code": None,
        "error_message": None,
    }
    if status == "SKIPPED":
        return result

    TravelEvaluator._validate_number(assessment.arrival_buffer_minutes, "Arrival buffer", allow_zero=True)
    result["arrival_buffer_minutes"] = assessment.arrival_buffer_minutes
    # This integration supports OneMap only; do not expose arbitrary model text.
    result["provider"] = "OneMap"
    if status == "UNAVAILABLE":
        if not isinstance(error_code, str) or error_code not in ERROR_MESSAGES:
            error_code = "TRAVEL_UNAVAILABLE"
        result["feasibility"] = "UNAVAILABLE"
        result["error_code"] = error_code
        result["error_message"] = ERROR_MESSAGES[error_code]
        return result

    if assessment.feasibility not in ("WITHIN_LIMIT", "LONG_JOURNEY"):
        raise ValidationError("Available travel must have a valid feasibility.")
    TravelEvaluator._validate_number(assessment.distance_km, "Journey distance")
    TravelEvaluator._validate_number(assessment.duration_minutes, "Journey duration")
    departure = TravelEvaluator._singapore_datetime(assessment.recommended_departure, "Departure")
    arrival = TravelEvaluator._singapore_datetime(assessment.estimated_arrival, "Arrival")
    result.update(
        distance_km=assessment.distance_km,
        duration_minutes=assessment.duration_minutes,
        recommended_departure=departure.isoformat(),
        estimated_arrival=arrival.isoformat(),
        feasibility=assessment.feasibility,
    )
    if isinstance(assessment.legs, list):
        result["legs"] = []
        for leg in assessment.legs:
            if not isinstance(leg, dict):
                continue
            mode = leg.get("mode")
            if mode not in ("WALK", "BUS", "SUBWAY", "RAIL", "TRAM", "FERRY"):
                mode = None
            detail = {"mode": mode}
            for key in ("distance_km", "duration_minutes"):
                value = leg.get(key)
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    value = None
                else:
                    try:
                        TravelEvaluator._validate_number(value, key, allow_zero=True)
                    except ValidationError:
                        value = None
                detail[key] = value
            for key in ("route", "from_name", "to_name"):
                value = leg.get(key)
                detail[key] = value.strip() if isinstance(value, str) and value.strip() else None
            result["legs"].append(detail)
    if event_start is not None:
        try:
            target_arrival = event_start - timedelta(minutes=assessment.arrival_buffer_minutes)
        except OverflowError:
            raise ValidationError("Arrival buffer exceeds the supported date range.") from None
        warnings = []
        # Use the stronger warning when both the buffer and event start are missed.
        if arrival > event_start:
            warnings.append("EVENT_START_MISSED")
        elif arrival > target_arrival:
            warnings.append("BUFFER_MISSED")
        result["warning_codes"] = warnings
    return result
