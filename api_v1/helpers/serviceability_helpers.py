from delivery.services.serviceability import check_serviceability


def serviceability_for_vendor(vendor, customer_lat: float, customer_lon: float):
    return check_serviceability(
        vendor_lat=float(vendor.latitude),
        vendor_lon=float(vendor.longitude),
        customer_lat=customer_lat,
        customer_lon=customer_lon,
        instant_radius_km=float(vendor.instant_delivery_radius_km),
        max_radius_km=float(vendor.max_delivery_radius_km),
        base_prep_time_min=vendor.base_prep_time_min,
        delivery_time_per_km_min=float(vendor.delivery_time_per_km_min),
        scheduled_buffer_min=vendor.scheduled_buffer_min,
    )
