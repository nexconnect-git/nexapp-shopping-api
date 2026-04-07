"""
Shared utility functions for the NexConnect backend.

This module contains helpers reused across multiple Django apps
to honour the DRY principle and keep each app's code focused.
"""

import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two geographic points.

    Uses the haversine formula to compute the shortest over-surface distance
    between two latitude/longitude pairs on the Earth.

    Args:
        lat1: Latitude of point 1 in decimal degrees.
        lon1: Longitude of point 1 in decimal degrees.
        lat2: Latitude of point 2 in decimal degrees.
        lon2: Longitude of point 2 in decimal degrees.

    Returns:
        Distance in kilometres between the two points.
    """
    EARTH_RADIUS_KM = 6_371

    delta_lat_rad = math.radians(lat2 - lat1)
    delta_lon_rad = math.radians(lon2 - lon1)
    hav_sum = (
        math.sin(delta_lat_rad / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(delta_lon_rad / 2) ** 2
    )
    central_angle = 2 * math.asin(math.sqrt(hav_sum))
    return EARTH_RADIUS_KM * central_angle


def get_client_ip(request) -> str | None:
    """Extract the real client IP address from a Django HTTP request.

    Respects the ``X-Forwarded-For`` header set by load balancers and
    reverse proxies before falling back to ``REMOTE_ADDR``.

    Args:
        request: The Django ``HttpRequest`` object.

    Returns:
        The client IP as a string, or ``None`` when unavailable.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
