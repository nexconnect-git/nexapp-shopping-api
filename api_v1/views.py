import hashlib
import json

from django.core.cache import cache
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models.address import Address
from delivery.services.distance import NOT_SERVICEABLE
from delivery.services.serviceability import check_serviceability
from orders.models import Cart
from vendors.data import VendorRepository
from vendors.models import Vendor
from api_v1.serializers import VendorV1Serializer

NEARBY_VENDORS_TTL = 120  # 2 minutes


def _serviceability_for_vendor(vendor, customer_lat: float, customer_lon: float) -> dict:
    result = check_serviceability(
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
    return result


class NearbyVendorsV1View(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
        except (KeyError, TypeError, ValueError):
            return Response({"error": "lat and lng are required."}, status=400)

        category = request.query_params.get("category")

        # geohash-like cache key (1 decimal place ≈ 11 km grid)
        cache_key = f"v1:nearby:{round(lat, 1)}:{round(lng, 1)}:{category or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        vendors = VendorRepository().get_approved_vendors(category=category)
        results = []
        for v in vendors:
            svc = _serviceability_for_vendor(v, lat, lng)
            if svc.delivery_type == NOT_SERVICEABLE:
                continue
            data = VendorV1Serializer(v).data
            data["distance_km"] = svc.distance_km
            data["eta_min"] = svc.eta_min
            data["delivery_type"] = svc.delivery_type
            results.append(data)

        results.sort(key=lambda x: x["distance_km"])
        cache.set(cache_key, results, NEARBY_VENDORS_TTL)
        return Response(results)


class VendorServiceabilityV1View(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
        except (KeyError, TypeError, ValueError):
            return Response({"error": "lat and lng are required."}, status=400)

        from vendors.models import Vendor
        try:
            vendor = Vendor.objects.get(pk=pk, status="approved")
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=404)

        svc = _serviceability_for_vendor(vendor, lat, lng)
        return Response({
            "vendor_id": str(vendor.id),
            "delivery_type": svc.delivery_type,
            "distance_km": svc.distance_km,
            "eta_min": svc.eta_min,
            "is_serviceable": svc.is_serviceable,
        })


DELIVERY_QUOTE_TTL = 300  # 5 minutes


def _cart_hash(cart) -> str:
    items = sorted(
        [(str(item.product_id), item.quantity) for item in cart.items.all()]
    )
    return hashlib.md5(json.dumps(items).encode()).hexdigest()


class CartDeliveryQuoteV1View(APIView):
    """
    GET /api/v1/cart/delivery-quote/?address_id=<uuid>

    Returns per-vendor serviceability + ETA for every vendor in the user's cart.
    Blocked vendors (NOT_SERVICEABLE) are flagged, not filtered, so the client
    can warn before checkout.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        address_id = request.query_params.get("address_id")
        if not address_id:
            return Response({"error": "address_id is required."}, status=400)

        try:
            address = Address.objects.get(pk=address_id, user=request.user)
        except Address.DoesNotExist:
            return Response({"error": "Address not found."}, status=404)

        if not address.latitude or not address.longitude:
            return Response({"error": "Address has no coordinates."}, status=422)

        try:
            cart = Cart.objects.prefetch_related("items__product__vendor").get(user=request.user)
        except Cart.DoesNotExist:
            return Response({"vendors": [], "all_serviceable": True})

        cache_key = f"v1:quote:{request.user.id}:{_cart_hash(cart)}:{address_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Collect distinct vendors from cart items
        vendor_ids = set(
            item.product.vendor_id
            for item in cart.items.all()
            if hasattr(item.product, "vendor_id")
        )
        vendors = Vendor.objects.filter(pk__in=vendor_ids, status="approved")

        customer_lat = float(address.latitude)
        customer_lon = float(address.longitude)

        vendor_quotes = []
        all_serviceable = True
        for vendor in vendors:
            svc = _serviceability_for_vendor(vendor, customer_lat, customer_lon)
            if not svc.is_serviceable:
                all_serviceable = False
            vendor_quotes.append({
                "vendor_id": str(vendor.id),
                "store_name": vendor.store_name,
                "delivery_type": svc.delivery_type,
                "distance_km": svc.distance_km,
                "eta_min": svc.eta_min,
                "is_serviceable": svc.is_serviceable,
            })

        result = {"vendors": vendor_quotes, "all_serviceable": all_serviceable}
        cache.set(cache_key, result, DELIVERY_QUOTE_TTL)
        return Response(result)
