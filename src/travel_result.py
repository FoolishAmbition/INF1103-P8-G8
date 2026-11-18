"""Consolidated travel domain model, OneMap transit parser, and presentation serializer."""

import math
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.exceptions import ValidationError, GeoLocationError
from src.route_geometry import decode_route_geometry


class TravelResult:
    """Unified transit route, journey assessment, and safe GUI response model."""

    SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")

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

    def __init__(
        self,
        *args,
        status=None,
        feasibility=None,
        arrival_buffer_minutes=None,
        distance_km=None,
        duration_minutes=None,
        departure_time=None,
        recommended_departure=None,
        estimated_arrival=None,
        provider="OneMap",
        error_message=None,
        error_code=None,
        event_start=None,
        preferred_limit_minutes=None,
        legs=None,
    ):
        # Support wrapping / copying an existing TravelResult or None (skipped)
        if len(args) == 1:
            arg0 = args[0]
            if arg0 is None:
                status = status or "SKIPPED"
            elif isinstance(arg0, TravelResult):
                status = status or arg0.status
                feasibility = feasibility or arg0.feasibility
                arrival_buffer_minutes = (
                    arrival_buffer_minutes
                    if arrival_buffer_minutes is not None
                    else arg0.arrival_buffer_minutes
                )
                distance_km = (
                    distance_km if distance_km is not None else arg0.distance_km
                )
                duration_minutes = (
                    duration_minutes
                    if duration_minutes is not None
                    else arg0.duration_minutes
                )
                departure_time = departure_time or arg0.departure_time
                recommended_departure = (
                    recommended_departure or arg0.recommended_departure
                )
                estimated_arrival = estimated_arrival or arg0.estimated_arrival
                provider = (
                    provider
                    if provider != "OneMap" or arg0.provider is None
                    else arg0.provider
                )
                error_message = error_message or arg0.error_message
                error_code = error_code or arg0.error_code
                event_start = event_start or arg0.event_start
                preferred_limit_minutes = (
                    preferred_limit_minutes
                    if preferred_limit_minutes is not None
                    else arg0.preferred_limit_minutes
                )
                legs = legs if legs is not None else getattr(arg0, "legs", None)
            elif isinstance(arg0, str):
                status = arg0
            elif isinstance(arg0, (int, float)) and not isinstance(arg0, bool):
                distance_km = float(arg0)
                status = status or "AVAILABLE"
            else:
                raise ValidationError("Invalid argument for TravelResult.")
        elif len(args) > 1:
            # Handle positional arguments from previous TransitRoute:
            # (distance_km, duration_minutes, departure_time, estimated_arrival, [provider], [legs])
            if isinstance(args[0], (int, float)) and not isinstance(args[0], bool):
                distance_km = float(args[0])
                status = status or "AVAILABLE"
                if len(args) > 1:
                    duration_minutes = float(args[1])
                if len(args) > 2:
                    departure_time = args[2]
                if len(args) > 3:
                    estimated_arrival = args[3]
                if len(args) > 4:
                    provider = args[4]
                if len(args) > 5:
                    legs = args[5]
            # Handle positional arguments from previous TravelAssessment:
            # (status, feasibility, arrival_buffer_minutes, distance_km, ...)
            elif isinstance(args[0], str):
                status = args[0]
                if len(args) > 1:
                    feasibility = args[1]
                if len(args) > 2:
                    arrival_buffer_minutes = args[2]
                if len(args) > 3:
                    distance_km = args[3]
                if len(args) > 4:
                    duration_minutes = args[4]
                if len(args) > 5:
                    recommended_departure = args[5]
                if len(args) > 6:
                    estimated_arrival = args[6]
                if len(args) > 7:
                    provider = args[7]
                if len(args) > 8:
                    error_message = args[8]
                if len(args) > 9:
                    error_code = args[9]
                if len(args) > 10:
                    event_start = args[10]
                if len(args) > 11:
                    preferred_limit_minutes = args[11]
                if len(args) > 12:
                    legs = args[12]

        self._status = status or "AVAILABLE"
        self._feasibility = feasibility
        self._arrival_buffer_minutes = arrival_buffer_minutes
        self._distance_km = distance_km
        self._duration_minutes = duration_minutes
        self._departure_time = departure_time
        self._recommended_departure = recommended_departure
        self._estimated_arrival = estimated_arrival
        self._provider = provider
        self._error_message = error_message
        self._error_code = error_code
        self._event_start = event_start
        self._preferred_limit_minutes = preferred_limit_minutes
        self._legs = deepcopy(legs) if legs is not None else None

    @property
    def status(self):
        return self._status

    @property
    def feasibility(self):
        return self._feasibility

    @property
    def arrival_buffer_minutes(self):
        return self._arrival_buffer_minutes

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
    def recommended_departure(self):
        return self._recommended_departure

    @property
    def estimated_arrival(self):
        return self._estimated_arrival

    @property
    def provider(self):
        return self._provider

    @property
    def error_message(self):
        return self._error_message

    @property
    def error_code(self):
        return self._error_code

    @property
    def event_start(self):
        return self._event_start

    @property
    def preferred_limit_minutes(self):
        return self._preferred_limit_minutes

    @property
    def legs(self):
        return self._legs

    def with_recommended_departure(self, departure):
        """Return a copy with the departure time used for the final route check."""
        return TravelResult(
            status=self.status,
            feasibility=self.feasibility,
            arrival_buffer_minutes=self.arrival_buffer_minutes,
            distance_km=self.distance_km,
            duration_minutes=self.duration_minutes,
            departure_time=self.departure_time,
            recommended_departure=departure,
            estimated_arrival=self.estimated_arrival,
            provider=self.provider,
            error_message=self.error_message,
            error_code=self.error_code,
            event_start=self.event_start,
            preferred_limit_minutes=self.preferred_limit_minutes,
            legs=self.legs,
        )

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)

    @classmethod
    def from_onemap_response(cls, response: dict) -> "TravelResult":
        """Validate and construct a route from OneMap API JSON."""
        if not isinstance(response, dict):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )

        plan = response.get("plan")
        if plan is None:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")
        if not isinstance(plan, dict):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )

        itineraries = plan.get("itineraries")
        if not isinstance(itineraries, list):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )
        if not itineraries:
            raise GeoLocationError("NO_ROUTE", "OneMap returned no transit itinerary.")

        itinerary = itineraries[0]
        if not isinstance(itinerary, dict):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )

        duration_seconds = itinerary.get("duration")
        start_time_ms = itinerary.get("startTime")
        end_time_ms = itinerary.get("endTime")
        legs = itinerary.get("legs")

        if not cls._is_valid_number(duration_seconds, min_val=0, allow_zero=False):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )
        if not cls._is_valid_number(start_time_ms) or not cls._is_valid_number(
            end_time_ms
        ):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )
        if end_time_ms <= start_time_ms:
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )
        if not isinstance(legs, list) or not legs:
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )

        distance_meters = cls._sum_leg_distances(legs)

        try:
            departure = datetime.fromtimestamp(
                start_time_ms / 1000, tz=cls.SINGAPORE_TIMEZONE
            )
            arrival = datetime.fromtimestamp(
                end_time_ms / 1000, tz=cls.SINGAPORE_TIMEZONE
            )
        except (ValueError, OverflowError, OSError):
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            ) from None

        parsed_legs = [cls._parse_leg(leg) for leg in legs]

        return cls(
            status="AVAILABLE",
            distance_km=distance_meters / 1000,
            duration_minutes=duration_seconds / 60,
            departure_time=departure,
            estimated_arrival=arrival,
            provider="OneMap",
            legs=parsed_legs,
        )

    @classmethod
    def _parse_leg(cls, leg: dict) -> dict:
        """Keep selected optional fields; bad detail must not discard a valid summary."""
        if not isinstance(leg, dict):
            return {}
        mode = leg.get("mode")
        if mode not in ("WALK", "BUS", "SUBWAY", "RAIL", "TRAM", "FERRY"):
            mode = None
        duration = leg.get("duration")
        duration_minutes = None
        if cls._is_valid_number(duration, min_val=0, allow_zero=True):
            duration_minutes = duration / 60
        geometry = leg.get("legGeometry")
        points = None
        if isinstance(geometry, dict):
            candidate = geometry.get("points")
            if isinstance(candidate, str) and candidate and all(63 <= ord(c) <= 126 for c in candidate):
                points = candidate
        distance = leg.get("distance", 0)
        distance_km = distance / 1000 if cls._is_valid_number(distance, min_val=0, allow_zero=True) else 0.0
        return {
            "mode": mode,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "route": cls._optional_text(leg.get("route")),
            "from_name": cls._place_name(leg.get("from")),
            "to_name": cls._place_name(leg.get("to")),
            "geometry_points": points,
        }

    @staticmethod
    def _optional_text(value):
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _place_name(cls, place):
        if isinstance(place, dict):
            return cls._optional_text(place.get("name"))
        return None

    @classmethod
    def _sum_leg_distances(cls, legs: list) -> float:
        """Sum distance across route legs, ensuring non-negative finite values."""
        total_meters = 0.0
        for leg in legs:
            if not isinstance(leg, dict):
                raise GeoLocationError(
                    "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
                )
            leg_distance = leg.get("distance")
            if not cls._is_valid_number(leg_distance, min_val=0, allow_zero=True):
                raise GeoLocationError(
                    "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
                )
            total_meters += leg_distance

        if not math.isfinite(total_meters) or total_meters <= 0:
            raise GeoLocationError(
                "INVALID_RESPONSE", "OneMap returned invalid or incomplete data."
            )
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

    @classmethod
    def _to_singapore_datetime(cls, value, name):
        """Ensure datetime has timezone and convert to Singapore Standard Time."""
        if not isinstance(value, datetime):
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError(f"{name} must be a timezone-aware datetime.")
        try:
            return value.astimezone(cls.SINGAPORE_TIMEZONE)
        except (OverflowError, ValueError):
            raise ValidationError(f"{name} exceeds the supported date range.") from None

    def to_dict(self) -> dict:
        """Convert travel result into the stable, privacy-safe GUI schema."""
        status = self._status
        if status not in ("AVAILABLE", "UNAVAILABLE", "SKIPPED"):
            raise ValidationError(
                "Assessment status must be AVAILABLE, UNAVAILABLE, or SKIPPED."
            )
        if self._error_code is not None and status != "UNAVAILABLE":
            raise ValidationError("Only unavailable travel can have an error code.")

        preferred_limit = self._preferred_limit_minutes
        if preferred_limit is not None:
            self._validate_number(preferred_limit, "Preferred journey limit")

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

        if self._arrival_buffer_minutes is not None:
            self._validate_number(
                self._arrival_buffer_minutes, "Arrival buffer", allow_zero=True
            )
            result["arrival_buffer_minutes"] = self._arrival_buffer_minutes
        result["provider"] = self._provider or "OneMap"

        if status == "UNAVAILABLE":
            error_code = self._error_code
            if not isinstance(error_code, str) or error_code not in self._ERROR_MESSAGES:
                error_code = "TRAVEL_UNAVAILABLE"
            result["feasibility"] = "UNAVAILABLE"
            result["error_code"] = error_code
            result["error_message"] = self._ERROR_MESSAGES[error_code]
            return result

        if self._feasibility not in ("WITHIN_LIMIT", "LONG_JOURNEY"):
            raise ValidationError("Available travel must have a valid feasibility.")
        self._validate_number(self._distance_km, "Journey distance")
        self._validate_number(self._duration_minutes, "Journey duration")

        dep_dt = self._recommended_departure or self._departure_time
        departure = self._to_singapore_datetime(dep_dt, "Departure")
        arrival = self._to_singapore_datetime(self._estimated_arrival, "Arrival")

        result.update(
            distance_km=self._distance_km,
            duration_minutes=self._duration_minutes,
            recommended_departure=departure.isoformat(),
            estimated_arrival=arrival.isoformat(),
            feasibility=self._feasibility,
        )

        if isinstance(self._legs, list):
            result["legs"] = []
            for leg in self._legs:
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
                            self._validate_number(value, key, allow_zero=True)
                        except ValidationError:
                            value = None
                    detail[key] = value
                for key in ("route", "from_name", "to_name"):
                    value = leg.get(key)
                    detail[key] = value.strip() if isinstance(value, str) and value.strip() else None
                detail["geometry"] = decode_route_geometry(leg.get("geometry_points"))
                result["legs"].append(detail)

        if self._event_start is not None:
            event_start = self._to_singapore_datetime(self._event_start, "Event start")
            buffer_mins = self._arrival_buffer_minutes or 0
            try:
                target_arrival = event_start - timedelta(minutes=buffer_mins)
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
