"""
Geographic utility functions.

Provides helpers for distance calculation and geo-search operations that
are reused across the vendors and delivery apps.
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
