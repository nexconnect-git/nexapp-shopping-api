from dataclasses import asdict, dataclass

from django.db import transaction

from products.models import Product
from vendors.actions.base import BaseAction
from vendors.models import FulfillmentNode, FulfillmentNodeInventory, Vendor


@dataclass
class FulfillmentBackfillSummary:
    vendors_seen: int = 0
    nodes_created: int = 0
    nodes_updated: int = 0
    inventories_created: int = 0
    inventories_updated: int = 0
    skipped_products: int = 0

    def to_dict(self):
        return asdict(self)


class BackfillVendorFulfillmentNodesAction(BaseAction):
    """Create vendor-store fulfillment nodes and node inventory from existing store data."""

    def execute(
        self,
        vendor_id=None,
        include_unapproved=False,
        sync_existing=False,
        dry_run=False,
    ) -> dict:
        summary = FulfillmentBackfillSummary()
        vendors = Vendor.objects.all().order_by("store_name", "id")
        if vendor_id:
            vendors = vendors.filter(id=vendor_id)
        elif not include_unapproved:
            vendors = vendors.filter(status="approved")

        with transaction.atomic():
            for vendor in vendors.iterator():
                summary.vendors_seen += 1
                node = self._find_existing_node(vendor)
                if node is None:
                    if not dry_run:
                        node = FulfillmentNode.objects.create(**self._node_payload(vendor))
                    summary.nodes_created += 1
                elif sync_existing:
                    summary.nodes_updated += 1
                    if not dry_run:
                        self._sync_node(node, vendor)

                if dry_run and node is None:
                    products = self._vendor_products(vendor)
                    summary.inventories_created += products.count()
                    continue
                if node is None:
                    continue

                self._sync_inventory(
                    node=node,
                    vendor=vendor,
                    summary=summary,
                    sync_existing=sync_existing,
                    dry_run=dry_run,
                )

            if dry_run:
                transaction.set_rollback(True)

        return summary.to_dict()

    def _find_existing_node(self, vendor):
        return (
            FulfillmentNode.objects.filter(vendor=vendor, node_type="vendor_store").first()
            or FulfillmentNode.objects.filter(code=self._node_code(vendor)).first()
        )

    def _node_payload(self, vendor):
        return {
            "vendor": vendor,
            "code": self._node_code(vendor),
            "name": vendor.store_name,
            "node_type": "vendor_store",
            "status": "active" if vendor.status == "approved" and vendor.is_open else "paused",
            "is_accepting_orders": vendor.status == "approved" and vendor.is_accepting_orders,
            "address": vendor.address,
            "city": vendor.city,
            "state": vendor.state,
            "postal_code": vendor.postal_code,
            "latitude": vendor.latitude,
            "longitude": vendor.longitude,
            "instant_radius_km": vendor.instant_delivery_radius_km,
            "max_delivery_radius_km": vendor.max_delivery_radius_km,
            "base_prep_time_min": vendor.base_prep_time_min,
            "delivery_time_per_km_min": vendor.delivery_time_per_km_min,
            "metadata": {
                "source": "vendor_backfill",
                "vendor_id": str(vendor.id),
            },
        }

    def _sync_node(self, node, vendor):
        payload = self._node_payload(vendor)
        payload.pop("vendor", None)
        payload.pop("code", None)
        for field, value in payload.items():
            setattr(node, field, value)
        node.save(update_fields=[*payload.keys(), "updated_at"])

    def _sync_inventory(self, node, vendor, summary, sync_existing=False, dry_run=False):
        products = self._vendor_products(vendor)
        existing = {
            item.product_id: item
            for item in FulfillmentNodeInventory.objects.filter(node=node, product__vendor=vendor)
        }
        create_items = []
        for product in products.iterator():
            if not product.id:
                summary.skipped_products += 1
                continue

            is_available = self._product_available_for_node(product)
            existing_item = existing.get(product.id)
            if existing_item is None:
                summary.inventories_created += 1
                if dry_run:
                    continue
                create_items.append(
                    FulfillmentNodeInventory(
                        node=node,
                        product=product,
                        stock=max(0, int(product.stock or 0)),
                        reserved_stock=0,
                        low_stock_threshold=max(0, int(product.low_stock_threshold or 0)),
                        is_available=is_available,
                    )
                )
                continue

            if not sync_existing:
                continue
            summary.inventories_updated += 1
            if dry_run:
                continue
            existing_item.stock = max(existing_item.reserved_stock, int(product.stock or 0))
            existing_item.low_stock_threshold = max(0, int(product.low_stock_threshold or 0))
            existing_item.is_available = is_available
            existing_item.save(update_fields=["stock", "low_stock_threshold", "is_available", "updated_at"])

        if create_items:
            FulfillmentNodeInventory.objects.bulk_create(create_items, batch_size=500)

    def _vendor_products(self, vendor):
        return Product.objects.filter(vendor=vendor).exclude(status="archived").order_by("id")

    def _product_available_for_node(self, product) -> bool:
        return (
            product.status == "active"
            and product.approval_status == Product.APPROVAL_STATUS_APPROVED
            and product.is_available
            and int(product.stock or 0) > 0
        )

    def _node_code(self, vendor) -> str:
        return f"vendor-{vendor.id}"
