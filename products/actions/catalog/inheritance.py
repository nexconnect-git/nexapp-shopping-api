import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from products.data.catalog_repository import CatalogProductRepository, VendorCatalogGrantRepository
from products.models import Product


class CreateVendorProductFromCatalogAction:
    UNIT_MAP = {
        'kg': 'kg',
        'kilogram': 'kg',
        'g': 'g',
        'gram': 'g',
        'l': 'l',
        'litre': 'l',
        'liter': 'l',
        'ml': 'ml',
        'piece': 'piece',
        'pcs': 'piece',
        'pc': 'piece',
        'unit': 'piece',
        'pack': 'pack',
    }

    def normalize_signature(self, brand, weight, unit):
        normalized_brand = (brand or '').strip().lower()
        normalized_unit_key = (unit or '').strip().lower()
        normalized_unit = self.UNIT_MAP.get(normalized_unit_key, normalized_unit_key)
        quantity_value = None
        if weight:
            raw = ''.join(ch for ch in str(weight) if ch.isdigit() or ch in ['.', ','])
            raw = raw.replace(',', '.')
            try:
                quantity_value = Decimal(raw).quantize(Decimal('0.001'))
            except (InvalidOperation, ValueError):
                quantity_value = None
        return normalized_brand, quantity_value, normalized_unit

    def execute(self, vendor, catalog_product_id, selling_data):
        catalog_product = CatalogProductRepository().get_by_id(catalog_product_id, select_related=['category'])
        if not catalog_product or not catalog_product.is_active:
            raise ValueError('Catalog product not found or inactive.')
        if not VendorCatalogGrantRepository().has_grant(vendor, catalog_product):
            raise ValueError('This catalog product is not available to your store.')
        normalized_brand, quantity_value, normalized_unit = self.normalize_signature(
            selling_data.get('brand') or catalog_product.brand,
            selling_data.get('weight'),
            selling_data.get('unit') or catalog_product.unit,
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
            'vendor': vendor,
            'catalog_product': catalog_product,
            'category': catalog_product.category,
            'name': catalog_product.name,
            'description': catalog_product.description,
            'brand': catalog_product.brand,
            'unit': catalog_product.unit,
            'barcode': catalog_product.barcode,
            'search_keywords': catalog_product.search_keywords,
            'compliance_notes': catalog_product.compliance_notes,
            'slug': self._unique_product_slug(catalog_product.name),
            'brand_normalized': normalized_brand,
            'quantity_normalized': quantity_value,
            'unit_normalized': normalized_unit,
        }
        return Product.objects.create(**payload)

    def _ensure_no_duplicate_variant(self, vendor, catalog_product, brand_normalized, quantity_normalized, unit_normalized, ignore_id=None):
        queryset = Product.objects.filter(
            vendor=vendor,
            catalog_product=catalog_product,
            brand_normalized=brand_normalized,
            quantity_normalized=quantity_normalized,
            unit_normalized=unit_normalized,
        )
        if ignore_id:
            queryset = queryset.exclude(pk=ignore_id)
        if queryset.exists():
            raise ValueError('Duplicate variant detected for this catalog item. Please adjust brand, quantity, or unit.')

    def _unique_product_slug(self, name):
        base = slugify(name) or 'product'
        candidate = base
        counter = 1
        while Product.objects.filter(slug=candidate).exists():
            candidate = f'{base}-{counter}'
            counter += 1
        return candidate


class CreateInheritedProductDraftBatchAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, catalog_product_ids):
        if not catalog_product_ids:
            raise ValueError('At least one catalog product must be selected.')
        batch_id = uuid.uuid4()
        created = []
        for catalog_product_id in catalog_product_ids:
            created.append(
                super().execute(
                    vendor=vendor,
                    catalog_product_id=catalog_product_id,
                    selling_data={
                        'price': Decimal('0.00'),
                        'stock': 0,
                        'status': 'draft',
                        'is_available': False,
                        'approval_status': Product.APPROVAL_STATUS_DRAFT,
                        'submission_batch_id': batch_id,
                    },
                )
            )
        return batch_id, created


class DuplicateInheritedProductAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, product):
        if product.vendor_id != vendor.id:
            raise ValueError('Product not found.')
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
            status='draft',
            is_featured=False,
            inheritance_mode=product.inheritance_mode,
            approval_status=Product.APPROVAL_STATUS_DRAFT,
            submission_batch_id=product.submission_batch_id or uuid.uuid4(),
            brand_normalized='',
            quantity_normalized=None,
            unit_normalized='',
        )


class SubmitInheritedProductBatchAction(CreateVendorProductFromCatalogAction):
    def execute(self, vendor, product_ids):
        if not product_ids:
            raise ValueError('Select at least one variant to submit.')
        variants = Product.objects.filter(vendor=vendor, id__in=product_ids).select_related('catalog_product')
        if variants.count() != len(product_ids):
            raise ValueError('Some selected variants were not found.')
        errors = self._validate_variants(vendor, variants)
        if errors:
            raise ValueError(errors)
        updated = []
        with transaction.atomic():
            for variant in variants:
                variant.approval_status = Product.APPROVAL_STATUS_PENDING
                variant.rejection_reason = ''
                variant.reviewed_by = None
                variant.reviewed_at = None
                variant.approval_requested_at = timezone.now()
                variant.approval_change_summary = ['new_product']
                variant.brand_normalized, variant.quantity_normalized, variant.unit_normalized = self.normalize_signature(
                    variant.brand,
                    variant.weight,
                    variant.unit,
                )
                variant.save(
                    update_fields=[
                        'approval_status',
                        'rejection_reason',
                        'reviewed_by',
                        'reviewed_at',
                        'approval_requested_at',
                        'approval_change_summary',
                        'brand_normalized',
                        'quantity_normalized',
                        'unit_normalized',
                    ]
                )
                updated.append(variant)
        return updated

    def _validate_variants(self, vendor, variants):
        errors = {}
        for variant in variants:
            if not variant.catalog_product_id:
                errors[str(variant.id)] = ['Catalog base is required.']
                continue
            if variant.price is None or variant.price <= 0:
                errors[str(variant.id)] = ['Price must be greater than zero.']
                continue
            if variant.stock is None or variant.stock < 0:
                errors[str(variant.id)] = ['Stock cannot be negative.']
                continue
            brand_norm, qty_norm, unit_norm = self.normalize_signature(variant.brand, variant.weight, variant.unit)
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
                errors[str(variant.id)] = ['Duplicate variant exists for the same catalog item.']
        return errors
