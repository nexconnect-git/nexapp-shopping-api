from decimal import Decimal

from django.db.models import F, Q

from accounts.models import Address
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.vendor_hours import is_vendor_open_now
from vendors.data import FulfillmentNodeRepository
from vendors.models import Vendor


def request_address_from_query(request) -> Address | None:
    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")
    if lat is None or lng is None:
        return None
    try:
        return Address(
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            full_name="Customer",
            phone="",
            address_line1="Selected location",
            city=request.query_params.get("city", ""),
            state=request.query_params.get("state", ""),
            postal_code=request.query_params.get("postal_code", ""),
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
        )
    except Exception:
        return None


def active_fulfillment_node_for_request(request):
    explicit_node_id = request.query_params.get("fulfillment_node_id")
    if explicit_node_id:
        return FulfillmentNodeRepository.active_nodes().filter(id=explicit_node_id).first()
    address = request_address_from_query(request)
    if not address:
        return None
    nodes = FulfillmentNodeRepository.active_nodes_for_address(address)
    return nodes[0] if nodes else None


def should_enforce_fulfillment_node_for_request(request) -> bool:
    if request.query_params.get("fulfillment_node_id"):
        return True
    address = request_address_from_query(request)
    if not address:
        return False
    return bool(FulfillmentNodeRepository.active_nodes_for_rollout_area(address))


def filter_products_for_fulfillment_node(queryset, node):
    if not node:
        return queryset
    return queryset.filter(
        fulfillment_inventory__node=node,
        fulfillment_inventory__is_available=True,
        fulfillment_inventory__stock__gt=0,
    ).filter(
        Q(fulfillment_inventory__reserved_stock__lt=F("fulfillment_inventory__stock"))
        | Q(fulfillment_inventory__reserved_stock=0)
    ).distinct()


def filter_products_for_serviceable_vendors(queryset, address):
    if not address:
        return queryset

    vendor_ids = list(queryset.values_list("vendor_id", flat=True).distinct())
    if not vendor_ids:
        return queryset.none()

    serviceable_vendor_ids = []
    vendors = Vendor.objects.filter(
        id__in=vendor_ids,
        status="approved",
        is_open=True,
        is_accepting_orders=True,
    )
    for vendor in vendors:
        if not is_vendor_open_now(vendor):
            continue
        if quote_vendor_delivery(vendor, address).is_serviceable:
            serviceable_vendor_ids.append(vendor.id)

    if not serviceable_vendor_ids:
        return queryset.none()
    return queryset.filter(vendor_id__in=serviceable_vendor_ids)
