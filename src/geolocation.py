"""Small validation helpers for the GeoLocation feature."""

from src.exceptions import ValidationError


def validate_singapore_postal_code(postal_code: str) -> str:
    """Return a valid six-digit postal code, preserving any leading zero."""
    if not isinstance(postal_code, str):
        raise ValidationError("Singapore postal code must be a string.")

    if len(postal_code) != 6 or not postal_code.isascii() or not postal_code.isdigit():
        raise ValidationError("Singapore postal code must contain exactly six digits.")

    return postal_code
