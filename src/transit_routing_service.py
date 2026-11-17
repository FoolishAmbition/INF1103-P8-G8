"""Contract for services that retrieve public-transit routes."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from src.exceptions import ValidationError

if TYPE_CHECKING:
    from src.travel_result import TravelResult


class TransitRoutingService(ABC):
    """Provide a route between two postal codes at a requested departure time."""

    SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")

    @staticmethod
    def validate_singapore_postal_code(postal_code: str) -> str:
        """Return a valid six-digit postal code, preserving any leading zero."""
        if not isinstance(postal_code, str):
            raise ValidationError("Singapore postal code must be a string.")

        if len(postal_code) != 6 or not postal_code.isascii() or not postal_code.isdigit():
            raise ValidationError("Singapore postal code must contain exactly six digits.")

        return postal_code

    @abstractmethod
    def get_transit_route(
        self,
        origin_postal_code: str,
        destination_postal_code: str,
        departure_time: datetime,
    ) -> "TravelResult":
        """Return the itinerary requested for the supplied departure time."""
        raise NotImplementedError

