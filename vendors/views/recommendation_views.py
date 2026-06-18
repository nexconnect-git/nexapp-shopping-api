from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from helpers.cache_helpers import cached_api_response
from orders.models import OrderItem
from products.data.product_repository import ProductRepository
from products.models import Product
from products.serializers import ProductSerializer
from vendors.models import Vendor


class VendorRecommendationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        return cached_api_response(
            request,
            f'vendors:recommendations:{pk}',
            90,
            lambda: self._get_uncached(request, pk),
            include_user=True,
        )

    def _get_uncached(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk, status='approved')
        except Vendor.DoesNotExist:
            return Response({'error': 'Store not found.'}, status=status.HTTP_404_NOT_FOUND)

        base_queryset = Product.objects.filter(
            vendor=vendor,
            **ProductRepository.customer_visible_filter(),
            category__is_active=True,
            category__show_in_customer_ui=True,
        ).select_related('category')
        previous_ids = self._previous_product_ids(request, vendor)
        selected = self._selected_products(base_queryset, previous_ids)
        return Response({
            'store_id': str(vendor.id),
            'store_name': vendor.store_name,
            'results': self._results(request, vendor, selected, previous_ids),
            'recommended_categories': self._categories(base_queryset),
        })

    def _previous_product_ids(self, request, vendor):
        if not getattr(request.user, 'is_authenticated', False):
            return set()
        return set(
            OrderItem.objects.filter(
                order__customer=request.user,
                order__vendor=vendor,
                product__isnull=False,
            ).values_list('product_id', flat=True)
        )

    def _selected_products(self, base_queryset, previous_ids):
        previous = list(base_queryset.filter(id__in=previous_ids).order_by('-total_orders', '-average_rating')[:8])
        featured = list(base_queryset.filter(is_featured=True).exclude(id__in=[product.id for product in previous]).order_by('-average_rating', '-total_orders')[:8])
        popular = list(base_queryset.exclude(id__in=[product.id for product in previous + featured]).order_by('-total_orders', '-average_rating')[:12])
        return (previous + featured + popular)[:16]

    def _results(self, request, vendor, selected, previous_ids):
        results = []
        hour = timezone.localtime(timezone.now()).hour
        time_reason = 'morning_pick' if 5 <= hour < 12 else 'evening_pick' if 17 <= hour < 22 else 'popular_now'
        for product in selected:
            if product.id in previous_ids:
                reason = 'previously_bought'
            elif product.is_featured:
                reason = 'vendor_promoted'
            elif product.total_orders > 0:
                reason = 'popular_in_store'
            else:
                reason = time_reason
            results.append({
                'product': ProductSerializer(product, context={'request': request}).data,
                'reason': reason,
                'store_id': str(vendor.id),
                'store_name': vendor.store_name,
            })
        return results

    def _categories(self, base_queryset):
        categories = list(
            base_queryset.exclude(category__isnull=True)
            .values('category_id', 'category__name')
            .distinct()[:8]
        )
        return [
            {'id': str(item['category_id']), 'name': item['category__name']}
            for item in categories
        ]
