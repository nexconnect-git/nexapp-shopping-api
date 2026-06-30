from decimal import Decimal

from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address
from backend.actions.customer_flow.fulfillment_filters import (
    active_fulfillment_node_for_request,
    filter_products_for_fulfillment_node,
    should_enforce_fulfillment_node_for_request,
)
from helpers.delivery_quotes import quote_vendor_delivery
from helpers.cache_helpers import cached_api_response
from products.models import Product
from products.data.product_repository import ProductRepository
from products.serializers import ProductSerializer
from vendors.serializers.public import VendorListSerializer


def _search_terms(request) -> list[str]:
    raw_terms = request.query_params.getlist("terms")
    if not raw_terms:
        raw_terms = [request.query_params.get("q") or request.query_params.get("search") or ""]
    seen = set()
    terms = []
    for raw in raw_terms:
        for part in str(raw or "").split(","):
            value = " ".join(part.strip().split())
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                terms.append(value)
    return terms


def _product_search_q(terms: list[str]) -> Q:
    query = Q()
    for term in terms:
        query |= (
            Q(name__icontains=term)
            | Q(search_keywords__icontains=term)
            | Q(description__icontains=term)
            | Q(brand__icontains=term)
            | Q(category__name__icontains=term)
        )
    return query


def _product_matched_terms(product, terms: list[str]) -> set[str]:
    haystack = " ".join(
        str(value or "")
        for value in [
            product.name,
            product.search_keywords,
            product.description,
            product.brand,
            getattr(product.category, "name", ""),
        ]
    ).lower()
    return {term for term in terms if term.lower() in haystack}


def _request_address(request) -> Address | None:
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


class ProductSearchByLocationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return cached_api_response(
            request,
            'products:search_by_location',
            60,
            lambda: self._get_uncached(request),
            include_user=False,
        )

    def _get_uncached(self, request):
        terms = _search_terms(request)
        if not terms:
            return Response({"count": 0, "results": []})
        address = _request_address(request)
        fulfillment_node = active_fulfillment_node_for_request(request)
        if not fulfillment_node and should_enforce_fulfillment_node_for_request(request):
            return Response({"count": 0, "results": []})
        products = (
            Product.objects
            .filter(
                **ProductRepository.customer_visible_filter(),
                vendor__status="approved",
                vendor__is_accepting_orders=True,
            )
            .select_related("vendor", "category")
            .filter(_product_search_q(terms))
        )
        products = filter_products_for_fulfillment_node(products, fulfillment_node)
        store_matches = {}
        store_vendors = {}
        for product in products:
            vendor = product.vendor
            store_vendors[str(vendor.id)] = vendor
            match = store_matches.setdefault(str(vendor.id), {
                "store": VendorListSerializer(vendor, context={"request": request}).data,
                "matching_products": [],
                "available": True,
                "distance_km": None,
                "estimated_delivery_minutes": None,
                "min_price": product.price,
                "matched_terms": set(),
                "missing_terms": [],
                "matched_count": 0,
                "total_terms": len(terms),
            })
            match["matching_products"].append(ProductSerializer(product, context={"request": request}).data)
            match["min_price"] = min(match["min_price"], product.price)
            match["matched_terms"].update(_product_matched_terms(product, terms))
        for match in store_matches.values():
            if address:
                vendor = store_vendors[match["store"]["id"]]
                quote = quote_vendor_delivery(
                    vendor=vendor,
                    address=address,
                )
                match["available"] = quote.is_serviceable
                match["distance_km"] = quote.distance_km
                match["estimated_delivery_minutes"] = quote.estimated_delivery_minutes
                match["store"].update(quote.as_dict())
            match["min_price"] = str(match["min_price"])
            match["matched_terms"] = sorted(match["matched_terms"])
            match["missing_terms"] = [term for term in terms if term not in match["matched_terms"]]
            match["matched_count"] = len(match["matched_terms"])
        results = sorted(
            [
                match for match in store_matches.values()
                if not address or match["available"]
            ],
            key=lambda item: (
                -item["matched_count"],
                item["distance_km"] if item["distance_km"] is not None else 999999,
                item["estimated_delivery_minutes"] if item["estimated_delivery_minutes"] is not None else 999999,
                -float(item["store"].get("average_rating") or 0),
                Decimal(str(item["min_price"])),
            ),
        )
        return Response({"count": len(results), "results": results})
