from decimal import Decimal

from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from backend.actions.customer_flow.fulfillment_filters import (
    active_fulfillment_node_for_request,
    filter_products_for_fulfillment_node,
)
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
        fulfillment_node = active_fulfillment_node_for_request(request)
        vendor_data = VendorSerializer(vendor, context={'request': request}).data
        address = build_request_address(request)
        quote = quote_vendor_delivery(vendor, address) if address else None
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
        if fulfillment_node:
            if fulfillment_node.vendor_id and str(fulfillment_node.vendor_id) != str(vendor.id):
                available_products = available_products.none()
            else:
                available_products = filter_products_for_fulfillment_node(available_products, fulfillment_node)
        if quote and not quote.is_serviceable:
            available_products = available_products.none()
        available_categories = self._available_categories(
            vendor,
            fulfillment_node,
            is_serviceable=not quote or quote.is_serviceable,
        )
        vendor_data['products'] = ProductSerializer(available_products, many=True, context={'request': request}).data
        vendor_data['available_categories'] = CategorySerializer(available_categories, many=True, context={'request': request}).data

        if quote:
            vendor_data.update(quote.as_dict())
        return Response(vendor_data)

    def _available_categories(self, vendor, fulfillment_node=None, is_serviceable=True):
        if not is_serviceable:
            return []
        category_products = VendorProductRepository().get_customer_visible_for_vendor(vendor=vendor)
        if fulfillment_node:
            if fulfillment_node.vendor_id and str(fulfillment_node.vendor_id) != str(vendor.id):
                category_products = category_products.none()
            else:
                category_products = filter_products_for_fulfillment_node(category_products, fulfillment_node)
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
