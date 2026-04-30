from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from math import ceil
from typing import Iterable

from accounts.models import Address
from helpers.geo_helpers import haversine
from helpers.state_normalization import normalize_state_identifier
from orders.models.operations import DeliveryZone
from orders.models.setting import PlatformSetting
from products.models import Product
from vendors.models import Vendor


CUSTOMER_DISCOVERY_RADIUS_KM = 10.0
DEFAULT_MAX_FAR_DISTANCE_KM = 20.0


@dataclass
class DeliveryQuote:
    vendor_id: str
    vendor_name: str
    vendor_state: str
    address_state: str
    distance_km: float
    estimated_delivery_minutes: int
    estimated_delivery_label: str
    delivery_fee: Decimal
    vehicle_type: str
    vehicle_reason: str
    is_far_delivery: bool
    requires_far_delivery_confirmation: bool
    within_instant_radius: bool
    same_state: bool
    is_serviceable: bool
    serviceability_error: str
    max_supported_distance_km: float

    def as_dict(self) -> dict:
        return {
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "vendor_state": self.vendor_state,
            "address_state": self.address_state,
            "distance_km": round(self.distance_km, 2),
            "estimated_delivery_minutes": self.estimated_delivery_minutes,
            "estimated_delivery_label": self.estimated_delivery_label,
            "delivery_fee": str(self.delivery_fee.quantize(Decimal("0.01"))),
            "vehicle_type": self.vehicle_type,
            "vehicle_reason": self.vehicle_reason,
            "is_far_delivery": self.is_far_delivery,
            "requires_far_delivery_confirmation": self.requires_far_delivery_confirmation,
            "within_instant_radius": self.within_instant_radius,
            "same_state": self.same_state,
            "is_serviceable": self.is_serviceable,
            "serviceability_error": self.serviceability_error,
            "max_supported_distance_km": round(self.max_supported_distance_km, 2),
            "far_order_eta_label": self.estimated_delivery_label,
        }


class FarDeliveryConfirmationRequired(Exception):
    def __init__(self, quotes: list[dict]):
        super().__init__("Far delivery confirmation required.")
        self.quotes = quotes


class DeliveryServiceabilityError(ValueError):
    def __init__(self, quote: DeliveryQuote):
        super().__init__(quote.serviceability_error)
        self.quote = quote


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def is_same_state(vendor: Vendor, address: Address) -> bool:
    address_state = normalize_state_identifier(address.state)
    if not address_state:
        return True
    return normalize_state_identifier(vendor.state) == address_state


def get_max_supported_distance_km(address: Address, vendor: Vendor) -> float:
    zone = DeliveryZone.objects.filter(
        is_active=True,
        city__iexact=address.city or vendor.city,
    ).order_by("radius_km").first()
    if zone:
        return float(zone.max_delivery_distance_km)
    return DEFAULT_MAX_FAR_DISTANCE_KM


def _parse_weight_to_kg(weight: str | None) -> float:
    if not weight:
        return 0.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", weight)
    if not match:
        return 0.0
    value = float(match.group(1))
    text = weight.lower()
    if "kg" in text:
        return value
    if "g" in text:
        return value / 1000.0
    if "mg" in text:
        return value / 1_000_000.0
    if "lb" in text:
        return value * 0.453592
    return value


def determine_vehicle_for_products(products: Iterable[Product], quantities: dict[str, int] | None = None) -> tuple[str, str]:
    total_weight_kg = 0.0
    total_units = 0
    has_fragile = False
    has_cold_items = False

    for product in products:
        qty = (quantities or {}).get(str(product.id), 1)
        total_units += qty
        total_weight_kg += _parse_weight_to_kg(product.weight) * qty
        has_fragile = has_fragile or bool(product.is_fragile)
        has_cold_items = has_cold_items or bool(product.requires_cold_storage)

    if total_weight_kg >= 40 or total_units >= 35:
        return "van", "Large basket size needs a van-sized delivery capacity."
    if total_weight_kg >= 15 or total_units >= 16 or has_fragile:
        return "car", "Basket needs safer handling because of size or fragile items."
    if total_weight_kg >= 5 or total_units >= 8 or has_cold_items:
        return "motorcycle", "Basket size fits a faster motorcycle delivery run."
    return "bicycle", "Small everyday basket can be delivered with a compact vehicle."


def format_eta_label(minutes: int) -> str:
    if minutes < 90:
        return f"{minutes} mins"
    if minutes < 1440:
        hours = max(2, round(minutes / 60))
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = max(1, ceil(minutes / 1440))
    return f"{days} day{'s' if days != 1 else ''}"


def quote_vendor_delivery(
    vendor: Vendor,
    address: Address,
    products: Iterable[Product] | None = None,
    quantities: dict[str, int] | None = None,
    subtotal: Decimal | None = None,
    platform: PlatformSetting | None = None,
) -> DeliveryQuote:
    platform = platform or PlatformSetting.get_setting()
    distance_km = 0.0
    if address.latitude and address.longitude:
        distance_km = haversine(
            float(vendor.latitude),
            float(vendor.longitude),
            float(address.latitude),
            float(address.longitude),
        )

    same_state = is_same_state(vendor, address)
    max_supported_distance_km = get_max_supported_distance_km(address, vendor)
    within_instant_radius = distance_km <= CUSTOMER_DISCOVERY_RADIUS_KM
    is_far_delivery = distance_km > CUSTOMER_DISCOVERY_RADIUS_KM

    product_list = list(products or [])
    vehicle_type, vehicle_reason = determine_vehicle_for_products(product_list, quantities)

    eta_minutes = int(
        max(
            20,
            round(
                vendor.base_prep_time_min
                + float(vendor.delivery_time_per_km_min) * distance_km
                + (15 if vehicle_type in {"car", "van"} else 0)
                + (30 if is_far_delivery else 0)
            ),
        )
    )
    eta_label = format_eta_label(eta_minutes)

    effective_subtotal = subtotal if subtotal is not None else Decimal("0")
    if platform.free_delivery_above > 0 and effective_subtotal >= platform.free_delivery_above:
        delivery_fee = Decimal("0")
    else:
        delivery_fee = platform.delivery_base_fee + (
            platform.delivery_per_km_fee * Decimal(str(round(distance_km, 2)))
        )
        if is_far_delivery:
            delivery_fee += Decimal("25.00")
        if vehicle_type == "car":
            delivery_fee += Decimal("20.00")
        elif vehicle_type == "van":
            delivery_fee += Decimal("45.00")

    if not same_state:
        return DeliveryQuote(
            vendor_id=str(vendor.id),
            vendor_name=vendor.store_name,
            vendor_state=vendor.state or "",
            address_state=address.state or "",
            distance_km=distance_km,
            estimated_delivery_minutes=eta_minutes,
            estimated_delivery_label=eta_label,
            delivery_fee=delivery_fee,
            vehicle_type=vehicle_type,
            vehicle_reason=vehicle_reason,
            is_far_delivery=is_far_delivery,
            requires_far_delivery_confirmation=False,
            within_instant_radius=within_instant_radius,
            same_state=same_state,
            is_serviceable=False,
            serviceability_error=(
                f"{vendor.store_name} cannot deliver to the selected address because the store is in "
                f"'{vendor.state or 'Unknown'}' while your selected address is in '{address.state or 'Unknown'}'."
            ),
            max_supported_distance_km=max_supported_distance_km,
        )

    if distance_km > max_supported_distance_km:
        return DeliveryQuote(
            vendor_id=str(vendor.id),
            vendor_name=vendor.store_name,
            vendor_state=vendor.state or "",
            address_state=address.state or "",
            distance_km=distance_km,
            estimated_delivery_minutes=eta_minutes,
            estimated_delivery_label=eta_label,
            delivery_fee=delivery_fee,
            vehicle_type=vehicle_type,
            vehicle_reason=vehicle_reason,
            is_far_delivery=is_far_delivery,
            requires_far_delivery_confirmation=False,
            within_instant_radius=within_instant_radius,
            same_state=same_state,
            is_serviceable=False,
            serviceability_error=(
                f"This store is {round(distance_km, 1)} km away, beyond the current supported delivery range."
            ),
            max_supported_distance_km=max_supported_distance_km,
        )

    return DeliveryQuote(
        vendor_id=str(vendor.id),
        vendor_name=vendor.store_name,
        vendor_state=vendor.state or "",
        address_state=address.state or "",
        distance_km=distance_km,
        estimated_delivery_minutes=eta_minutes,
        estimated_delivery_label=eta_label,
        delivery_fee=delivery_fee,
        vehicle_type=vehicle_type,
        vehicle_reason=vehicle_reason,
        is_far_delivery=is_far_delivery,
        requires_far_delivery_confirmation=is_far_delivery,
        within_instant_radius=within_instant_radius,
        same_state=same_state,
        is_serviceable=True,
        serviceability_error="",
        max_supported_distance_km=max_supported_distance_km,
    )
