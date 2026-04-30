import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from notifications.models import Notification
from products.data.catalog_repository import (
    CatalogProductRepository,
    VendorCatalogGrantRepository,
)
from products.models import CatalogProduct, CatalogProposal, CatalogProposalItem, Product


class CatalogSlugMixin:
    def unique_catalog_slug(self, name, instance=None):
        base = slugify(name) or "catalog-product"
        qs = CatalogProduct.objects.all()
        if instance:
            qs = qs.exclude(pk=instance.pk)
        candidate = base
        n = 1
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate


class CreateVendorProductFromCatalogAction:
    UNIT_MAP = {
        "kg": "kg",
        "kilogram": "kg",
        "g": "g",
        "gram": "g",
        "l": "l",
        "litre": "l",
        "liter": "l",
        "ml": "ml",
        "piece": "piece",
        "pcs": "piece",
        "pc": "piece",
        "unit": "piece",
        "pack": "pack",
    }

    def normalize_signature(self, brand, weight, unit):
        normalized_brand = (brand or "").strip().lower()
        normalized_unit_key = (unit or "").strip().lower()
        normalized_unit = self.UNIT_MAP.get(normalized_unit_key, normalized_unit_key)
        quantity_value = None
        if weight:
            raw = "".join(ch for ch in str(weight) if ch.isdigit() or ch in [".", ","])
            raw = raw.replace(",", ".")
            try:
                quantity_value = Decimal(raw).quantize(Decimal("0.001"))
            except (InvalidOperation, ValueError):
                quantity_value = None
        return normalized_brand, quantity_value, normalized_unit

    def _ensure_no_duplicate_variant(self, vendor, catalog_product, brand_normalized, quantity_normalized, unit_normalized, ignore_id=None):
        qs = Product.objects.filter(
            vendor=vendor,
            catalog_product=catalog_product,
            brand_normalized=brand_normalized,
            quantity_normalized=quantity_normalized,
            unit_normalized=unit_normalized,
        )
        if ignore_id:
            qs = qs.exclude(pk=ignore_id)
        if qs.exists():
            raise ValueError("Duplicate variant detected for this catalog item. Please adjust brand, quantity, or unit.")

    def execute(self, vendor, catalog_product_id, selling_data):
        catalog_product = CatalogProductRepository().get_by_id(
            catalog_product_id,
            select_related=["category"],
        )
        if not catalog_product or not catalog_product.is_active:
            raise ValueError("Catalog product not found or inactive.")
        if not VendorCatalogGrantRepository().has_grant(vendor, catalog_product):
            raise ValueError("This catalog product has not been approved for your store.")
        normalized_brand, quantity_value, normalized_unit = self.normalize_signature(
            selling_data.get("brand") or catalog_product.brand,
            selling_data.get("weight"),
            selling_data.get("unit") or catalog_product.unit,
        )
        self._ensure_no_duplicate_variant(
            vendor=vendor,
            catalog_product=catalog_product,
            brand_normalized=normalized_brand,
            quantity_normalized=quantity_value,
            unit_normalized=normalized_unit,
        )

        payload = {
            **selling_data,
            "vendor": vendor,
            "catalog_product": catalog_product,
            "category": catalog_product.category,
            "name": catalog_product.name,
            "description": catalog_product.description,
            "brand": catalog_product.brand,
            "unit": catalog_product.unit,
            "barcode": catalog_product.barcode,
            "search_keywords": catalog_product.search_keywords,
            "compliance_notes": catalog_product.compliance_notes,
            "slug": self._unique_product_slug(catalog_product.name),
            "brand_normalized": normalized_brand,
            "quantity_normalized": quantity_value,
            "unit_normalized": normalized_unit,
        }
        return Product.objects.create(**payload)

    def _unique_product_slug(self, name):
        base = slugify(name) or "product"
        candidate = base
        n = 1
        while Product.objects.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate


class CreateInheritedProductDraftBatchAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, catalog_product_ids):
        if not catalog_product_ids:
            raise ValueError("At least one catalog product must be selected.")
        batch_id = uuid.uuid4()
        created = []
        for catalog_product_id in catalog_product_ids:
            created.append(
                super().execute(
                    vendor=vendor,
                    catalog_product_id=catalog_product_id,
                    selling_data={
                        "price": Decimal("0.00"),
                        "stock": 0,
                        "status": "draft",
                        "is_available": False,
                        "approval_status": Product.APPROVAL_STATUS_DRAFT,
                        "submission_batch_id": batch_id,
                    },
                )
            )
        return batch_id, created


class DuplicateInheritedProductAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, product):
        if product.vendor_id != vendor.id:
            raise ValueError("Product not found.")
        # Allow vendors to create a temporary duplicate draft from the same catalog
        # item and adjust its variant signature later. We defer duplicate enforcement
        # to submit-time validation so the draft can exist long enough to be edited.
        return Product.objects.create(
            vendor=vendor,
            catalog_product=product.catalog_product,
            category=product.category,
            name=product.name,
            description=product.description,
            brand=product.brand,
            unit=product.unit,
            barcode=product.barcode,
            search_keywords=product.search_keywords,
            compliance_notes=product.compliance_notes,
            slug=self._unique_product_slug(product.name),
            price=product.price,
            compare_price=product.compare_price,
            tax_rate=product.tax_rate,
            sku=product.sku,
            stock=product.stock,
            low_stock_threshold=product.low_stock_threshold,
            min_order_quantity=product.min_order_quantity,
            weight=product.weight,
            is_available=product.is_available,
            prep_time_minutes=product.prep_time_minutes,
            is_instant_delivery=product.is_instant_delivery,
            is_scheduled_delivery=product.is_scheduled_delivery,
            is_perishable=product.is_perishable,
            requires_cold_storage=product.requires_cold_storage,
            is_fragile=product.is_fragile,
            is_age_restricted=product.is_age_restricted,
            allow_customer_notes=product.allow_customer_notes,
            is_returnable=product.is_returnable,
            packaging_instructions=product.packaging_instructions,
            ingredients=product.ingredients,
            allergens=product.allergens,
            shelf_life=product.shelf_life,
            status="draft",
            is_featured=False,
            inheritance_mode=product.inheritance_mode,
            approval_status=Product.APPROVAL_STATUS_DRAFT,
            submission_batch_id=product.submission_batch_id or uuid.uuid4(),
            brand_normalized="",
            quantity_normalized=None,
            unit_normalized="",
        )


class SubmitInheritedProductBatchAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, product_ids):
        if not product_ids:
            raise ValueError("Select at least one variant to submit.")
        variants = Product.objects.filter(vendor=vendor, id__in=product_ids).select_related("catalog_product")
        if variants.count() != len(product_ids):
            raise ValueError("Some selected variants were not found.")
        errors = {}
        for variant in variants:
            if not variant.catalog_product_id:
                errors[str(variant.id)] = ["Catalog base is required."]
                continue
            if variant.price is None or variant.price <= 0:
                errors[str(variant.id)] = ["Price must be greater than zero."]
                continue
            if variant.stock is None or variant.stock < 0:
                errors[str(variant.id)] = ["Stock cannot be negative."]
                continue
            brand_norm, qty_norm, unit_norm = self.normalize_signature(
                variant.brand,
                variant.weight,
                variant.unit,
            )
            try:
                self._ensure_no_duplicate_variant(
                    vendor=vendor,
                    catalog_product=variant.catalog_product,
                    brand_normalized=brand_norm,
                    quantity_normalized=qty_norm,
                    unit_normalized=unit_norm,
                    ignore_id=variant.id,
                )
            except ValueError:
                errors[str(variant.id)] = ["Duplicate variant exists for the same catalog item."]
                continue
        if errors:
            raise ValueError(errors)
        updated = []
        with transaction.atomic():
            for variant in variants:
                variant.approval_status = Product.APPROVAL_STATUS_PENDING
                variant.rejection_reason = ""
                variant.reviewed_by = None
                variant.reviewed_at = None
                variant.approval_requested_at = timezone.now()
                variant.approval_change_summary = ["new_product"]
                variant.brand_normalized, variant.quantity_normalized, variant.unit_normalized = self.normalize_signature(
                    variant.brand,
                    variant.weight,
                    variant.unit,
                )
                variant.save(
                    update_fields=[
                        "approval_status",
                        "rejection_reason",
                        "reviewed_by",
                        "reviewed_at",
                        "approval_requested_at",
                        "approval_change_summary",
                        "brand_normalized",
                        "quantity_normalized",
                        "unit_normalized",
                    ]
                )
                updated.append(variant)
        return updated


class ReviewVendorProductAction:
    def approve(self, admin_user, product):
        product.approval_status = Product.APPROVAL_STATUS_APPROVED
        product.rejection_reason = ""
        product.reviewed_by = admin_user
        product.reviewed_at = timezone.now()
        product.approval_change_summary = []
        product.save(update_fields=["approval_status", "rejection_reason", "reviewed_by", "reviewed_at", "approval_change_summary"])
        return product

    def reject(self, admin_user, product, reason):
        if not reason.strip():
            raise ValueError("Rejection reason is required.")
        product.approval_status = Product.APPROVAL_STATUS_REJECTED
        product.rejection_reason = reason.strip()
        product.reviewed_by = admin_user
        product.reviewed_at = timezone.now()
        product.save(update_fields=["approval_status", "rejection_reason", "reviewed_by", "reviewed_at"])
        return product


class CreateCatalogProposalAction:
    def execute(self, vendor, items):
        if not items:
            raise ValueError("At least one proposed item is required.")
        with transaction.atomic():
            proposal = CatalogProposal.objects.create(vendor=vendor)
            for item in items:
                CatalogProposalItem.objects.create(
                    proposal=proposal,
                    name=item["name"],
                    category=item.get("category"),
                    description=item.get("description", ""),
                    brand=item.get("brand", ""),
                    unit=item.get("unit", "piece"),
                    barcode=item.get("barcode", ""),
                    sku_hint=item.get("sku_hint", ""),
                )
            return proposal


class ProposalStatusMixin:
    def refresh_proposal(self, proposal, admin_user, admin_notes):
        statuses = list(proposal.items.values_list("status", flat=True))
        if all(item_status == "approved" for item_status in statuses):
            proposal.status = "approved"
        elif all(item_status == "rejected" for item_status in statuses):
            proposal.status = "rejected"
        elif any(item_status in ("approved", "rejected") for item_status in statuses):
            proposal.status = "partially_approved"
        proposal.reviewed_by = admin_user
        proposal.reviewed_at = timezone.now()
        if admin_notes:
            proposal.admin_notes = admin_notes
        proposal.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes"])


class ApproveCatalogProposalItemAction(CatalogSlugMixin, ProposalStatusMixin):
    def execute(self, proposal_id, item_id, admin_user, catalog_product_id=None, admin_notes=""):
        proposal = CatalogProposal.objects.select_related("vendor__user").get(pk=proposal_id)
        item = proposal.items.select_related("category").get(pk=item_id)
        if item.status != "pending":
            raise ValueError("Only pending proposal items can be approved.")

        with transaction.atomic():
            if catalog_product_id:
                catalog_product = CatalogProduct.objects.get(pk=catalog_product_id)
            else:
                catalog_product = CatalogProduct.objects.create(
                    category=item.category,
                    name=item.name,
                    slug=self.unique_catalog_slug(item.name),
                    description=item.description,
                    brand=item.brand,
                    unit=item.unit or "piece",
                    barcode=item.barcode,
                    created_by=admin_user,
                )

            VendorCatalogGrantRepository().grant(proposal.vendor, catalog_product, admin_user)
            item.status = "approved"
            item.created_catalog_product = catalog_product
            item.reviewed_at = timezone.now()
            item.save(update_fields=["status", "created_catalog_product", "reviewed_at"])
            self.refresh_proposal(proposal, admin_user, admin_notes)
            Notification.objects.create(
                user=proposal.vendor.user,
                title="Catalog item approved",
                message=f"{catalog_product.name} is approved for your store catalog.",
                notification_type="system",
                data={
                    "proposal_id": str(proposal.id),
                    "proposal_item_id": str(item.id),
                    "catalog_product_id": str(catalog_product.id),
                },
            )
            return item


class RejectCatalogProposalItemAction(ProposalStatusMixin):
    def execute(self, proposal_id, item_id, admin_user, rejection_reason="", admin_notes=""):
        proposal = CatalogProposal.objects.select_related("vendor__user").get(pk=proposal_id)
        item = proposal.items.get(pk=item_id)
        if item.status != "pending":
            raise ValueError("Only pending proposal items can be rejected.")

        with transaction.atomic():
            item.status = "rejected"
            item.rejection_reason = rejection_reason
            item.reviewed_at = timezone.now()
            item.save(update_fields=["status", "rejection_reason", "reviewed_at"])
            self.refresh_proposal(proposal, admin_user, admin_notes)
            Notification.objects.create(
                user=proposal.vendor.user,
                title="Catalog item rejected",
                message=rejection_reason or f"{item.name} was not approved for the catalog.",
                notification_type="system",
                data={
                    "proposal_id": str(proposal.id),
                    "proposal_item_id": str(item.id),
                },
            )
            return item
