from decimal import Decimal

from django.db import models
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.actions.customer_flow.fulfillment_filters import (
    active_fulfillment_node_for_request,
    should_enforce_fulfillment_node_for_request,
)
from backend.services import RecommendationServiceClient
from helpers.cache_helpers import cached_api_response
from orders.models import OrderItem
from products.data.product_repository import ProductRepository
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
        fulfillment_node = active_fulfillment_node_for_request(request)
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

        vendors = self._filter_vendors_for_fulfillment_node(vendors, fulfillment_node, request)
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
            fulfillment_node=fulfillment_node,
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
        if sort_key == 'relevance':
            cards = _rank_vendor_cards_with_ml(request, cards)

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

    def _filter_vendors_for_fulfillment_node(self, vendors, fulfillment_node, request):
        if fulfillment_node:
            if fulfillment_node.vendor_id:
                return vendors.filter(id=fulfillment_node.vendor_id)
            return vendors.filter(
                products__fulfillment_inventory__node=fulfillment_node,
                products__fulfillment_inventory__is_available=True,
                products__fulfillment_inventory__stock__gt=0,
                products__fulfillment_inventory__reserved_stock__lt=models.F(
                    "products__fulfillment_inventory__stock"
                ),
                **{
                    f"products__{key}": value
                    for key, value in ProductRepository.customer_visible_filter().items()
                },
            ).distinct()
        if should_enforce_fulfillment_node_for_request(request):
            return Response({'count': 0, 'results': []})
        return vendors

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

        fulfillment_node = active_fulfillment_node_for_request(request)
        if not fulfillment_node and should_enforce_fulfillment_node_for_request(request):
            return Response([])

        category = request.query_params.get('category')
        repo = VendorRepository()
        vendors = repo.get_approved_vendors(category=category)
        if fulfillment_node:
            if fulfillment_node.vendor_id:
                vendors = vendors.filter(id=fulfillment_node.vendor_id)
            else:
                visible_filter = {
                    f"products__{key}": value
                    for key, value in ProductRepository.customer_visible_filter().items()
                }
                vendors = vendors.filter(
                    products__fulfillment_inventory__node=fulfillment_node,
                    products__fulfillment_inventory__is_available=True,
                    products__fulfillment_inventory__stock__gt=0,
                    products__fulfillment_inventory__reserved_stock__lt=models.F(
                        "products__fulfillment_inventory__stock"
                    ),
                    **visible_filter,
                )
        if getattr(request.user, 'is_authenticated', False):
            vendors = repo.annotate_previous_order_flag(vendors, request.user)

        cards = serialize_vendor_cards(request, list(vendors.distinct()), address, fulfillment_node=fulfillment_node)
        cards = [card for card in cards if card.get('within_instant_radius')]
        cards = _rank_vendor_cards_with_ml(request, cards)
        return Response(cards)


def _recommendation_location(request) -> dict:
    return {
        'lat': request.query_params.get('lat') or None,
        'lng': request.query_params.get('lng') or None,
        'city': request.query_params.get('city') or '',
        'state': request.query_params.get('state') or '',
        'postal_code': request.query_params.get('postal_code') or '',
    }


def _rank_vendor_cards_with_ml(request, cards: list[dict]) -> list[dict]:
    if not cards:
        return cards
    ranked_items = RecommendationServiceClient().store_recommendations(
        user_id=str(request.user.id) if getattr(request.user, 'is_authenticated', False) else None,
        limit=max(len(cards), 12),
        location=_recommendation_location(request),
    )
    ranked_ids = [item['store_id'] for item in ranked_items if item.get('store_id')]
    if not ranked_ids:
        return cards

    allowed_cards = {
        str(card.get('id')): card
        for card in cards
        if card.get('id')
    }
    ranked_cards = [
        allowed_cards[store_id]
        for store_id in ranked_ids
        if store_id in allowed_cards
    ]
    used_ids = {str(card.get('id')) for card in ranked_cards}
    ranked_cards.extend([
        card
        for card in cards
        if str(card.get('id')) not in used_ids
    ])
    return ranked_cards
