from helpers.geo_helpers import haversine

INSTANT    = "INSTANT"
SCHEDULED  = "SCHEDULED"
NOT_SERVICEABLE = "NOT_SERVICEABLE"


def compute_delivery_type(distance_km: float, instant_radius_km: float, max_radius_km: float) -> str:
    if distance_km <= instant_radius_km:
        return INSTANT
    if distance_km <= max_radius_km:
        return SCHEDULED
    return NOT_SERVICEABLE


def compute_eta(
    distance_km: float,
    base_prep_time_min: int,
    delivery_time_per_km_min: float,
    scheduled_buffer_min: int,
    delivery_type: str,
) -> int:
    travel = distance_km * delivery_time_per_km_min
    eta = base_prep_time_min + travel
    if delivery_type == SCHEDULED:
        eta += scheduled_buffer_min
    return round(eta)


def compute_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine(lat1, lon1, lat2, lon2)
