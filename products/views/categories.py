from decimal import Decimal

from rest_framework import generics
from rest_framework.permissions import AllowAny

from accounts.models import Address
from helpers.cache_helpers import cached_api_response
from products.serializers.category_serializers import CategorySerializer
from products.data.category_repository import CategoryRepository


def _build_request_address(request) -> Address | None:
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


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer

    def list(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            'products:categories',
            300,
            lambda: super(CategoryListView, self).list(request, *args, **kwargs),
            include_user=False,
        )

    def get_queryset(self):
        address = _build_request_address(self.request)
        vendor_id = self.request.query_params.get("vendor_id") or self.request.query_params.get("store_id")
        self.available_category_ids = CategoryRepository.get_available_customer_category_ids(
            vendor_id=vendor_id,
            address=address,
        )
        return CategoryRepository.get_customer_visible(self.available_category_ids)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["available_category_ids"] = getattr(self, "available_category_ids", None)
        return context
