"""Travel assessment data returned by the journey evaluator."""


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
        error_code=None,
        event_start=None,
        preferred_limit_minutes=None,
    ):
        self._status = status
        self._feasibility = feasibility
        self._arrival_buffer_minutes = arrival_buffer_minutes
        self._distance_km = distance_km
        self._duration_minutes = duration_minutes
        self._recommended_departure = recommended_departure
        self._estimated_arrival = estimated_arrival
        self._provider = provider
        self._error_message = error_message
        self._error_code = error_code
        self._event_start = event_start
        self._preferred_limit_minutes = preferred_limit_minutes

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

    def with_recommended_departure(self, departure):
        """Return a copy with the departure time used for the final route check."""
        return TravelAssessment(
            status=self.status,
            feasibility=self.feasibility,
            arrival_buffer_minutes=self.arrival_buffer_minutes,
            distance_km=self.distance_km,
            duration_minutes=self.duration_minutes,
            recommended_departure=departure,
            estimated_arrival=self.estimated_arrival,
            provider=self.provider,
            error_message=self.error_message,
            error_code=self.error_code,
            event_start=self.event_start,
            preferred_limit_minutes=self.preferred_limit_minutes,
        )

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)
