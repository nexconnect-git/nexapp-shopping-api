from decimal import Decimal

from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from helpers.cache_helpers import cached_api_response
from helpers.delivery_quotes import quote_vendor_delivery
from products.serializers import CategorySerializer, ProductSerializer
from vendors.data import VendorProductRepository, VendorRepository
from vendors.helpers.public_vendor_helpers import build_request_address
from vendors.serializers.public import VendorSerializer


class VendorDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get_queryset(self):
        return VendorRepository().filter(status='approved')

    def retrieve(self, request, *args, **kwargs):
        return cached_api_response(
            request,
            f'vendors:detail:{kwargs.get("pk")}',
            90,
            lambda: self._retrieve_uncached(request, *args, **kwargs),
            include_user=False,
        )

    def _retrieve_uncached(self, request, *args, **kwargs):
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor, context={'request': request}).data
        available_products = VendorProductRepository().get_customer_visible_for_vendor(
            vendor=vendor,
            search=(request.query_params.get('product_search') or request.query_params.get('q') or '').strip(),
            category=(request.query_params.get('product_category') or request.query_params.get('category') or '').strip(),
            min_rating=self._decimal_or_none(request.query_params.get('min_rating')),
            min_price=self._decimal_or_none(request.query_params.get('min_price')),
            max_price=self._decimal_or_none(request.query_params.get('max_price')),
            availability=request.query_params.get('availability') or request.query_params.get('in_stock'),
            offers=request.query_params.get('offers'),
            product_type=request.query_params.get('product_type'),
            sort=request.query_params.get('product_sort') or request.query_params.get('sort'),
        )
        available_categories = self._available_categories(vendor)
        vendor_data['products'] = ProductSerializer(available_products, many=True, context={'request': request}).data
        vendor_data['available_categories'] = CategorySerializer(available_categories, many=True, context={'request': request}).data

        address = build_request_address(request)
        if address:
            quote = quote_vendor_delivery(vendor, address)
            vendor_data.update(quote.as_dict())
        return Response(vendor_data)

    def _available_categories(self, vendor):
        category_products = VendorProductRepository().get_customer_visible_for_vendor(vendor=vendor)
        available_categories = []
        seen_category_ids = set()
        for product in category_products:
            category = product.category
            if not category or category.id in seen_category_ids:
                continue
            seen_category_ids.add(category.id)
            available_categories.append(category)
        return available_categories

    def _decimal_or_none(self, value):
        try:
            return Decimal(str(value)) if value else None
        except Exception:
            return None
