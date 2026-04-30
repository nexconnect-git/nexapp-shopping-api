from django.utils import timezone
from django.utils.text import slugify

from products.models import Product


class ProductApprovalPolicy:
    OPERATIONAL_FIELDS = {
        "price",
        "compare_price",
        "stock",
        "low_stock_threshold",
        "min_order_quantity",
        "is_available",
        "status",
        "prep_time_minutes",
        "is_instant_delivery",
        "is_scheduled_delivery",
    }

    CRUCIAL_FIELDS = {
        "name",
        "description",
        "brand",
        "unit",
        "weight",
        "barcode",
        "sku",
        "category",
        "ingredients",
        "allergens",
        "shelf_life",
        "compliance_notes",
        "packaging_instructions",
        "is_perishable",
        "requires_cold_storage",
        "is_fragile",
        "is_age_restricted",
        "is_returnable",
        "images",
    }

    VENDOR_MANAGED_FIELDS = OPERATIONAL_FIELDS | CRUCIAL_FIELDS | {
        "tax_rate",
        "allow_customer_notes",
        "is_featured",
        "inheritance_mode",
    }

    @classmethod
    def crucial_changes(cls, product, update_data):
        changed = []
        for field in cls.CRUCIAL_FIELDS:
            if field not in update_data:
                continue
            current = getattr(product, f"{field}_id", None) if field == "category" else getattr(product, field, None)
            incoming = getattr(update_data[field], "id", update_data[field])
            if str(current or "") != str(incoming or ""):
                changed.append(field)
        return sorted(changed)

    @classmethod
    def mark_requires_review(cls, product, changed_fields):
        if not changed_fields:
            return []
        product.approval_status = Product.APPROVAL_STATUS_PENDING
        product.rejection_reason = ""
        product.reviewed_by = None
        product.reviewed_at = None
        product.approval_requested_at = timezone.now()
        product.approval_change_summary = changed_fields
        return [
            "approval_status",
            "rejection_reason",
            "reviewed_by",
            "reviewed_at",
            "approval_requested_at",
            "approval_change_summary",
        ]


class UpdateVendorProductAction:
    def execute(self, product, update_data):
        sanitized = {
            field: value
            for field, value in update_data.items()
            if field in ProductApprovalPolicy.VENDOR_MANAGED_FIELDS
        }
        changed_crucial_fields = ProductApprovalPolicy.crucial_changes(product, sanitized)
        update_fields = []

        for field, value in sanitized.items():
            setattr(product, field, value)
            update_fields.append(field)

        if "name" in sanitized:
            product.slug = self._unique_product_slug(sanitized["name"], product)
            update_fields.append("slug")

        should_request_review = bool(changed_crucial_fields) and product.approval_status in {
            Product.APPROVAL_STATUS_APPROVED,
            Product.APPROVAL_STATUS_REJECTED,
            Product.APPROVAL_STATUS_PENDING,
        }
        if should_request_review:
            update_fields.extend(ProductApprovalPolicy.mark_requires_review(product, changed_crucial_fields))

        if update_fields:
            update_fields.append("updated_at")
            product.save(update_fields=sorted(set(update_fields)))
        return product

    def _unique_product_slug(self, name, instance):
        base = slugify(name) or "product"
        candidate = base
        n = 1
        qs = Product.objects.exclude(pk=instance.pk)
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate
