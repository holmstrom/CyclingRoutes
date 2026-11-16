"""
Nominatim geocoding with rate limiting.

Enforces max 1 request/second as required by Nominatim usage policy.
"""

import logging
import time

from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

_geolocator = Nominatim(user_agent="RouteFinder/1.0", timeout=10)
_last_request_time: float = 0.0


def _rate_limit() -> None:
    """Enforce minimum 1-second interval between Nominatim requests."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < 1.0 and _last_request_time > 0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.monotonic()


def geocode(query: str) -> dict | None:
    """Geocode an address string.

    Returns {'lat': float, 'lon': float, 'display_name': str} or None on failure.
    """
    _rate_limit()
    try:
        location = _geolocator.geocode(query, exactly_one=True)
        if location is None:
            return None
        return {
            "lat": location.latitude,
            "lon": location.longitude,
            "display_name": location.address,
        }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding failed for '%s': %s", query, e)
        return None


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Reverse geocode coordinates to a display name.

    Returns display name string or None on failure.
    """
    _rate_limit()
    try:
        location = _geolocator.reverse((lat, lon), exactly_one=True)
        if location is None:
            return None
        return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Reverse geocoding failed for (%s, %s): %s", lat, lon, e)
        return None
