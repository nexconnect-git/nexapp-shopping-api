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


def calculate_eta_minutes(
    partner_lat: float,
    partner_lng: float,
    vendor_lat: float,
    vendor_lng: float,
    customer_lat: float,
    customer_lng: float,
    avg_speed_kmh: float = 25.0,
    prep_buffer_minutes: int = 5,
) -> int:
    """Estimate delivery time in minutes.

    Sums the partner→vendor leg and vendor→customer leg, converts to minutes
    at the given average speed, then adds a preparation buffer.

    Returns at least 5 minutes regardless of distance.
    """
    dist_to_vendor = haversine(partner_lat, partner_lng, vendor_lat, vendor_lng)
    dist_to_customer = haversine(vendor_lat, vendor_lng, customer_lat, customer_lng)
    total_km = dist_to_vendor + dist_to_customer
    travel_minutes = int((total_km / avg_speed_kmh) * 60)
    return max(5, travel_minutes + prep_buffer_minutes)
