from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from helpers.cache_helpers import cached_api_response
from orders.models import OrderItem
from vendors.data import VendorRepository
from vendors.helpers.public_vendor_helpers import (
    StandardPagination,
    build_request_address,
    serialize_vendor_cards,
    sort_vendor_cards,
)


class VendorListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get(self, request):
        return cached_api_response(
            request,
            'vendors:list',
            60,
            lambda: self._get_uncached(request),
            include_user=True,
        )

    def _get_uncached(self, request):
        repo = VendorRepository()
        address = build_request_address(request)
        search = request.query_params.get('search', '').strip()
        search_mode = request.query_params.get('search_mode', 'browse').strip() or 'browse'
        category = request.query_params.get('category')
        max_price = request.query_params.get('maxPrice') or request.query_params.get('max_price')
        min_rating = request.query_params.get('minRating') or request.query_params.get('min_rating')
        offers = request.query_params.get('offersOnly') or request.query_params.get('offers')
        state = request.query_params.get('state')
        city = request.query_params.get('city')
        sort_key = request.query_params.get('sort', 'relevance').strip() or 'relevance'
        area = request.query_params.get('area', '').strip()
        group_by_area = request.query_params.get('group_by_area', '').lower() == 'true'
        include_far_same_state = request.query_params.get('include_far_same_state', '').lower() == 'true'
        product_query = request.query_params.get('product_query', '').strip()

        vendors = self._vendor_queryset(
            repo,
            search_mode,
            product_query,
            search,
            state,
            category,
            max_price,
            min_rating,
            offers,
            include_far_same_state,
        )
        if isinstance(vendors, Response):
            return vendors

        if city:
            vendors = vendors.filter(city__iexact=city)
        vendors = vendors.filter(is_open=True, is_accepting_orders=True)

        previous_vendor_ids = set()
        if getattr(request.user, 'is_authenticated', False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)
            previous_vendor_ids = set(
                OrderItem.objects.filter(order__customer=request.user)
                .values_list('order__vendor_id', flat=True)
                .distinct()
            )
        vendors = repo.with_available_products(vendors)

        cards = serialize_vendor_cards(
            request,
            list(vendors.distinct()),
            address,
            product_query=product_query or search,
            previous_vendor_ids=previous_vendor_ids,
        )
        if search_mode not in {'manual_far', 'global_item'} and not include_far_same_state:
            cards = [card for card in cards if card.get('is_serviceable', True)]
        cards = sort_vendor_cards(cards, sort_key)
        grouped_cards = {
            'nearby': [card for card in cards if card.get('within_instant_radius')],
            'extended': [card for card in cards if card.get('within_instant_radius') is False],
        }

        if area == 'nearby' or (not area and search_mode == 'nearby' and address):
            cards = [card for card in cards if card.get('within_instant_radius')]
        elif area == 'extended':
            cards = [card for card in cards if card.get('within_instant_radius') is False]
        elif search_mode == 'global_item':
            cards = [card for card in cards if card.get('matched_products_preview')]

        summary = {
            'total': len(cards),
            'nearby': len(grouped_cards['nearby']),
            'extended': len(grouped_cards['extended']),
        }
        cities = repo.get_delivery_cities(state=state, category=category)

        if group_by_area:
            return Response({'count': len(cards), 'results': cards, 'groups': grouped_cards, 'summary': summary, 'cities': cities})

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(cards, request)
        if page is not None:
            response = paginator.get_paginated_response(page)
            response.data['summary'] = summary
            response.data['cities'] = cities
            return response
        return Response(cards)

    def _vendor_queryset(self, repo, search_mode, product_query, search, state, category, max_price, min_rating, offers, include_far_same_state):
        if search_mode == 'global_item':
            query = product_query or search
            if not query:
                return Response([])
            return (
                repo.get_vendors_selling_product_query(query, state=state)
                | repo.get_approved_vendors_in_state(state=state, search=query, category=category)
            )
        if search_mode == 'manual_far' or include_far_same_state:
            if not state:
                return Response([])
            return repo.get_approved_vendors_in_state(state=state, search=search, category=category)

        try:
            max_price_value = Decimal(str(max_price)) if max_price else None
        except Exception:
            max_price_value = None
        try:
            min_rating_value = Decimal(str(min_rating)) if min_rating else None
        except Exception:
            min_rating_value = None
        return repo.get_approved_vendors(
            search=search,
            category=category,
            max_price=max_price_value,
            min_rating=min_rating_value,
            offers=offers,
        )


class NearbyVendorsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return cached_api_response(
            request,
            'vendors:nearby',
            60,
            lambda: self._get_uncached(request),
            include_user=True,
        )

    def _get_uncached(self, request):
        address = build_request_address(request)
        if not address:
            return Response({'error': 'lat and lng reqd.'}, status=status.HTTP_400_BAD_REQUEST)

        category = request.query_params.get('category')
        repo = VendorRepository()
        vendors = repo.get_approved_vendors(category=category)
        if getattr(request.user, 'is_authenticated', False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)

        cards = serialize_vendor_cards(request, list(vendors.distinct()), address)
        cards = [card for card in cards if card.get('within_instant_radius')]
        return Response(cards)
