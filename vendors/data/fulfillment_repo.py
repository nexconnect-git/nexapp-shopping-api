from django.db.models import Q

from helpers.geo_helpers import haversine
from helpers.state_normalization import normalize_state_identifier
from vendors.data.base import BaseRepository
from vendors.models import FulfillmentNode, FulfillmentNodeInventory, FulfillmentNodeServiceArea


class FulfillmentNodeRepository(BaseRepository):
    model = FulfillmentNode

    @classmethod
    def active_nodes(cls):
        return (
            cls.model.objects.filter(status="active", is_accepting_orders=True)
            .select_related("vendor")
            .prefetch_related("service_areas")
        )

    @classmethod
    def list(cls, status_filter=None, node_type=None, vendor_id=None, city=None, search=None):
        queryset = cls.model.objects.select_related("vendor").all().order_by("name")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if node_type:
            queryset = queryset.filter(node_type=node_type)
        if vendor_id:
            queryset = queryset.filter(vendor_id=vendor_id)
        if city:
            queryset = queryset.filter(city__iexact=city)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(vendor__store_name__icontains=search)
                | Q(city__icontains=search)
                | Q(state__icontains=search)
                | Q(postal_code__icontains=search)
            )
        return queryset

    @classmethod
    def active_nodes_for_address(cls, address):
        nodes = []
        for node in cls.active_nodes():
            if cls.node_can_serve_address(node, address):
                nodes.append(node)
        return nodes

    @classmethod
    def active_nodes_for_rollout_area(cls, address):
        nodes = []
        for node in cls.active_nodes():
            if cls.node_is_in_rollout_area(node, address):
                nodes.append(node)
        return nodes

    @staticmethod
    def node_can_serve_address(node, address) -> bool:
        if not address or not address.latitude or not address.longitude:
            return False
        address_state = normalize_state_identifier(address.state)
        node_state = normalize_state_identifier(node.state)
        if address_state and node_state and address_state != node_state:
            return False

        active_areas = [area for area in node.service_areas.all() if area.is_active]
        if active_areas:
            return any(FulfillmentNodeRepository.area_can_serve_address(area, address) for area in active_areas)

        distance = haversine(
            float(node.latitude),
            float(node.longitude),
            float(address.latitude),
            float(address.longitude),
        )
        return distance <= float(node.max_delivery_radius_km or 0)

    @staticmethod
    def node_is_in_rollout_area(node, address) -> bool:
        if not address:
            return False
        if FulfillmentNodeRepository.node_can_serve_address(node, address):
            return True

        address_state = normalize_state_identifier(address.state)
        node_state = normalize_state_identifier(node.state)
        if address_state and node_state and address_state != node_state:
            return False

        active_areas = [area for area in node.service_areas.all() if area.is_active]
        if active_areas:
            return any(FulfillmentNodeRepository.area_matches_rollout_location(area, address) for area in active_areas)

        if node.postal_code and address.postal_code:
            return str(node.postal_code).strip() == str(address.postal_code).strip()
        if node.city and address.city:
            return node.city.strip().lower() == address.city.strip().lower()
        return bool(address_state and node_state and address_state == node_state)

    @staticmethod
    def area_can_serve_address(area, address) -> bool:
        if area.postal_code and str(area.postal_code).strip() != str(address.postal_code or "").strip():
            return False
        area_state = normalize_state_identifier(area.state)
        address_state = normalize_state_identifier(address.state)
        if area_state and address_state and area_state != address_state:
            return False
        if area.city and address.city and area.city.strip().lower() != address.city.strip().lower():
            return False
        if area.center_latitude is not None and area.center_longitude is not None and area.radius_km:
            distance = haversine(
                float(area.center_latitude),
                float(area.center_longitude),
                float(address.latitude),
                float(address.longitude),
            )
            return distance <= float(area.radius_km)
        return True

    @staticmethod
    def area_matches_rollout_location(area, address) -> bool:
        area_state = normalize_state_identifier(area.state)
        address_state = normalize_state_identifier(address.state)
        if area_state and address_state and area_state != address_state:
            return False
        if area.postal_code and address.postal_code:
            return str(area.postal_code).strip() == str(address.postal_code).strip()
        if area.city and address.city:
            return area.city.strip().lower() == address.city.strip().lower()
        return bool(area_state and address_state and area_state == address_state)


class FulfillmentInventoryRepository(BaseRepository):
    model = FulfillmentNodeInventory

    @classmethod
    def list(cls, node_id=None, product_id=None, low_stock=None, search=None):
        queryset = cls.model.objects.select_related("node", "product").all().order_by("node__name", "product__name")
        if node_id:
            queryset = queryset.filter(node_id=node_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if str(low_stock).lower() in {"1", "true", "yes"}:
            queryset = queryset.filter(stock__lte=5)
        if search:
            queryset = queryset.filter(
                Q(node__name__icontains=search)
                | Q(product__name__icontains=search)
                | Q(product__sku__icontains=search)
            )
        return queryset

    @classmethod
    def available_for_nodes(cls, node_ids):
        return cls.model.objects.filter(
            node_id__in=node_ids,
            is_available=True,
            product__status="active",
            product__approval_status="approved",
            product__is_available=True,
            product__stock__gt=0,
        ).filter(Q(stock__gt=0) | Q(product__stock__gt=0))

    @classmethod
    def available_product_count_for_nodes(cls, node_ids) -> int:
        return cls.available_for_nodes(node_ids).values("product_id").distinct().count()


class FulfillmentServiceAreaRepository(BaseRepository):
    model = FulfillmentNodeServiceArea

    @classmethod
    def list(cls, node_id=None, is_active=None, city=None, search=None):
        queryset = cls.model.objects.select_related("node").all()
        if node_id:
            queryset = queryset.filter(node_id=node_id)
        if is_active is not None and str(is_active) != "":
            queryset = queryset.filter(is_active=str(is_active).lower() in {"1", "true", "yes"})
        if city:
            queryset = queryset.filter(city__iexact=city)
        if search:
            queryset = queryset.filter(
                Q(label__icontains=search)
                | Q(node__name__icontains=search)
                | Q(city__icontains=search)
                | Q(state__icontains=search)
                | Q(postal_code__icontains=search)
            )
        return queryset
