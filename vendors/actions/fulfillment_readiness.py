from django.db.models import Count, Exists, F, OuterRef, Q

from products.models import Product
from vendors.actions.base import BaseAction
from vendors.models import FulfillmentNode, FulfillmentNodeInventory, FulfillmentNodeServiceArea, Vendor


class FulfillmentReadinessAuditAction(BaseAction):
    """Read-only launch readiness audit for fulfillment-node operations."""

    def execute(self, sample_limit=20) -> dict:
        sample_limit = self._normalize_limit(sample_limit)
        approved_vendors = Vendor.objects.filter(status="approved")
        active_vendor_node = FulfillmentNode.objects.filter(
            vendor=OuterRef("pk"),
            node_type="vendor_store",
            status="active",
            is_accepting_orders=True,
        )
        vendors_missing_active_node = approved_vendors.annotate(
            has_active_node=Exists(active_vendor_node)
        ).filter(has_active_node=False)

        sellable_products = Product.objects.filter(
            vendor__status="approved",
            status="active",
            approval_status=Product.APPROVAL_STATUS_APPROVED,
            is_available=True,
            stock__gt=0,
            catalog_product__isnull=False,
        )
        sellable_inventory = FulfillmentNodeInventory.objects.filter(
            product=OuterRef("pk"),
            node__status="active",
            node__is_accepting_orders=True,
            is_available=True,
            stock__gt=0,
            reserved_stock__lt=F("stock"),
        )
        products_missing_node_inventory = sellable_products.annotate(
            has_sellable_node_inventory=Exists(sellable_inventory)
        ).filter(has_sellable_node_inventory=False)

        active_nodes = FulfillmentNode.objects.filter(status="active", is_accepting_orders=True)
        active_rollout_areas = self._rollout_area_samples(active_nodes, sample_limit)
        nodes_without_sellable_stock = active_nodes.annotate(
            sellable_items=Count(
                "inventory_items",
                filter=Q(
                    inventory_items__is_available=True,
                    inventory_items__stock__gt=0,
                    inventory_items__reserved_stock__lt=F("inventory_items__stock"),
                    inventory_items__product__status="active",
                    inventory_items__product__approval_status=Product.APPROVAL_STATUS_APPROVED,
                    inventory_items__product__is_available=True,
                    inventory_items__product__catalog_product__isnull=False,
                ),
                distinct=True,
            )
        ).filter(sellable_items=0)

        over_reserved_inventory = FulfillmentNodeInventory.objects.select_related(
            "node",
            "product",
            "product__vendor",
        ).filter(reserved_stock__gt=F("stock"))
        vendor_node_mismatches = FulfillmentNodeInventory.objects.select_related(
            "node",
            "product",
            "product__vendor",
        ).filter(
            node__node_type="vendor_store",
            node__vendor__isnull=False,
        ).exclude(node__vendor_id=F("product__vendor_id"))
        visible_inventory_for_unsellable_products = FulfillmentNodeInventory.objects.select_related(
            "node",
            "product",
            "product__vendor",
        ).filter(is_available=True).filter(
            Q(product__status="archived")
            | Q(product__status="draft")
            | Q(product__status="sold_out")
            | Q(product__approval_status__in=[
                Product.APPROVAL_STATUS_DRAFT,
                Product.APPROVAL_STATUS_PENDING,
                Product.APPROVAL_STATUS_REJECTED,
            ])
            | Q(product__is_available=False)
            | Q(product__catalog_product__isnull=True)
        )

        summary = {
            "approved_vendor_count": approved_vendors.count(),
            "active_fulfillment_node_count": active_nodes.count(),
            "active_rollout_area_count": len(active_rollout_areas),
            "sellable_product_count": sellable_products.count(),
            "vendors_missing_active_node_count": vendors_missing_active_node.count(),
            "sellable_products_missing_node_inventory_count": products_missing_node_inventory.count(),
            "active_nodes_without_sellable_stock_count": nodes_without_sellable_stock.count(),
            "over_reserved_inventory_count": over_reserved_inventory.count(),
            "vendor_node_inventory_mismatch_count": vendor_node_mismatches.count(),
            "visible_inventory_for_unsellable_product_count": visible_inventory_for_unsellable_products.count(),
        }
        critical_issue_count = (
            summary["vendors_missing_active_node_count"]
            + summary["sellable_products_missing_node_inventory_count"]
            + summary["over_reserved_inventory_count"]
            + summary["vendor_node_inventory_mismatch_count"]
        )
        warning_count = (
            summary["active_nodes_without_sellable_stock_count"]
            + summary["visible_inventory_for_unsellable_product_count"]
        )
        status = "ready" if critical_issue_count == 0 else "blocked"
        if status == "ready" and warning_count:
            status = "ready_with_warnings"

        return {
            "status": status,
            "critical_issue_count": critical_issue_count,
            "warning_count": warning_count,
            "summary": summary,
            "samples": {
                "vendors_missing_active_node": self._vendor_samples(vendors_missing_active_node, sample_limit),
                "sellable_products_missing_node_inventory": self._product_samples(
                    products_missing_node_inventory,
                    sample_limit,
                ),
                "active_nodes_without_sellable_stock": self._node_samples(
                    nodes_without_sellable_stock,
                    sample_limit,
                ),
                "over_reserved_inventory": self._inventory_samples(over_reserved_inventory, sample_limit),
                "vendor_node_inventory_mismatches": self._inventory_samples(vendor_node_mismatches, sample_limit),
                "visible_inventory_for_unsellable_products": self._inventory_samples(
                    visible_inventory_for_unsellable_products,
                    sample_limit,
                ),
                "active_rollout_areas": active_rollout_areas,
            },
        }

    def _vendor_samples(self, queryset, limit):
        return [
            {
                "vendor_id": str(vendor.id),
                "store_name": vendor.store_name,
                "city": vendor.city,
                "state": vendor.state,
                "is_open": vendor.is_open,
                "is_accepting_orders": vendor.is_accepting_orders,
            }
            for vendor in queryset.order_by("store_name", "id")[:limit]
        ]

    def _product_samples(self, queryset, limit):
        return [
            {
                "product_id": str(product.id),
                "product_name": product.name,
                "vendor_id": str(product.vendor_id),
                "vendor_name": product.vendor.store_name if product.vendor else "",
                "stock": product.stock,
                "status": product.status,
                "approval_status": product.approval_status,
            }
            for product in queryset.select_related("vendor").order_by("vendor__store_name", "name", "id")[:limit]
        ]

    def _node_samples(self, queryset, limit):
        return [
            {
                "node_id": str(node.id),
                "node_name": node.name,
                "node_type": node.node_type,
                "vendor_id": str(node.vendor_id) if node.vendor_id else None,
                "city": node.city,
                "state": node.state,
            }
            for node in queryset.order_by("name", "id")[:limit]
        ]

    def _inventory_samples(self, queryset, limit):
        return [
            {
                "inventory_id": str(item.id),
                "node_id": str(item.node_id),
                "node_name": item.node.name,
                "product_id": str(item.product_id),
                "product_name": item.product.name,
                "vendor_id": str(item.product.vendor_id),
                "vendor_name": item.product.vendor.store_name if item.product.vendor else "",
                "stock": item.stock,
                "reserved_stock": item.reserved_stock,
                "is_available": item.is_available,
            }
            for item in queryset.order_by("node__name", "product__name", "id")[:limit]
        ]

    def _rollout_area_samples(self, active_nodes, limit):
        areas = []
        seen = set()
        service_areas = FulfillmentNodeServiceArea.objects.select_related("node").filter(
            node__in=active_nodes,
            is_active=True,
        ).order_by("priority", "city", "state", "postal_code")
        for area in service_areas:
            key = (
                str(area.node_id),
                (area.city or "").lower(),
                (area.state or "").lower(),
                area.postal_code or "",
            )
            if key in seen:
                continue
            seen.add(key)
            areas.append({
                "node_id": str(area.node_id),
                "node_name": area.node.name,
                "city": area.city,
                "state": area.state,
                "postal_code": area.postal_code,
                "source": "service_area",
            })
            if len(areas) >= limit:
                return areas

        for node in active_nodes.order_by("city", "state", "postal_code", "name"):
            key = (str(node.id), (node.city or "").lower(), (node.state or "").lower(), node.postal_code or "")
            if key in seen:
                continue
            seen.add(key)
            areas.append({
                "node_id": str(node.id),
                "node_name": node.name,
                "city": node.city,
                "state": node.state,
                "postal_code": node.postal_code,
                "source": "node",
            })
            if len(areas) >= limit:
                return areas
        return areas

    def _normalize_limit(self, value):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 20
        return max(1, min(parsed, 100))
