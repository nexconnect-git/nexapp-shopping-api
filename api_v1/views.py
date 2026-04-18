import hashlib
import json

from django.core.cache import cache
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.services.distance import NOT_SERVICEABLE
from delivery.services.serviceability import check_serviceability
from vendors.data import VendorRepository
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
