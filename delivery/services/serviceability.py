from dataclasses import dataclass

from delivery.services.distance import (
    INSTANT, SCHEDULED, NOT_SERVICEABLE,
    compute_delivery_type, compute_distance_km, compute_eta,
)


@dataclass(frozen=True)
class ServiceabilityResult:
    delivery_type: str
    distance_km: float
    eta_min: int
    is_serviceable: bool


def check_serviceability(
    vendor_lat: float,
    vendor_lon: float,
    customer_lat: float,
    customer_lon: float,
    instant_radius_km: float,
    max_radius_km: float,
    base_prep_time_min: int,
    delivery_time_per_km_min: float,
    scheduled_buffer_min: int,
) -> ServiceabilityResult:
    distance_km = compute_distance_km(vendor_lat, vendor_lon, customer_lat, customer_lon)
    delivery_type = compute_delivery_type(distance_km, instant_radius_km, max_radius_km)
    is_serviceable = delivery_type != NOT_SERVICEABLE
    eta_min = (
        compute_eta(distance_km, base_prep_time_min, delivery_time_per_km_min, scheduled_buffer_min, delivery_type)
        if is_serviceable else 0
    )
    return ServiceabilityResult(
        delivery_type=delivery_type,
        distance_km=round(distance_km, 2),
        eta_min=eta_min,
        is_serviceable=is_serviceable,
    )
