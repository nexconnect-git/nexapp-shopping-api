from rest_framework import generics
from rest_framework.permissions import AllowAny

from backend.actions.customer_flow.fulfillment_filters import (
    active_fulfillment_node_for_request,
    request_address_from_query,
    should_enforce_fulfillment_node_for_request,
)
from helpers.cache_helpers import cached_api_response
from products.serializers.category_serializers import CategorySerializer
from products.data.category_repository import CategoryRepository


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
        address = request_address_from_query(self.request)
        fulfillment_node = active_fulfillment_node_for_request(self.request)
        if not fulfillment_node and should_enforce_fulfillment_node_for_request(self.request):
            self.available_category_ids = set()
            return CategoryRepository.get_customer_visible(self.available_category_ids)
        vendor_id = self.request.query_params.get("vendor_id") or self.request.query_params.get("store_id")
        self.available_category_ids = CategoryRepository.get_available_customer_category_ids(
            vendor_id=vendor_id,
            address=address,
            fulfillment_node=fulfillment_node,
        )
        return CategoryRepository.get_customer_visible(self.available_category_ids)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["available_category_ids"] = getattr(self, "available_category_ids", None)
        return context
