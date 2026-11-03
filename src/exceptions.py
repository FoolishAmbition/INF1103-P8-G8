"""Domain-specific exceptions used across EventWise."""


class EventWiseError(Exception):
    """Base class for all EventWise errors."""


class APIError(EventWiseError):
    """Raised when the AI API call fails or times out."""


class ResponseValidationError(EventWiseError):
    """Raised when an AI response fails schema validation."""


class DataCorruptionError(EventWiseError):
    """Raised when a persistence file is missing or corrupt."""