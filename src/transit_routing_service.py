"""Contract for services that retrieve public-transit routes."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.geolocation import TransitRoute


class TransitRoutingService(ABC):
    """Provide a route between two postal codes at a requested departure time."""

    @abstractmethod
    def get_transit_route(
        self,
        origin_postal_code: str,
        destination_postal_code: str,
        departure_time: datetime,
    ) -> "TransitRoute":
        """Return the itinerary requested for the supplied departure time."""
        raise NotImplementedError
