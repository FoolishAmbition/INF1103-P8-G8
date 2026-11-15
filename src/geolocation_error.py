from src.exceptions import EventWiseError


class GeoLocationError(EventWiseError):
    """A safe service failure, with a code callers can handle separately."""

    def __init__(self, code, message):
        super().__init__(message)
        self._code = code

    @property
    def code(self):
        return self._code
