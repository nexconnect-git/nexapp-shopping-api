from django.db.models import Count, Exists, F, Max, OuterRef, Q
from django.utils import timezone

from products.data.product_repository import ProductRepository
from products.models import Product, ProductImage, CatalogProductImage
from vendors.data.base import BaseRepository
from vendors.models import Vendor, VendorBankDetails, VendorDocument, VendorOnboarding


class VendorWorkspaceRepository(BaseRepository):
    def __init__(self):
        super().__init__(Vendor)

    def locked(self, vendor):
        return self.model.objects.select_for_update().select_related('user').get(pk=vendor.pk)

    def for_operations_socket(self, user_id):
        return self.filter(user_id=user_id, status='approved', user__force_password_change=False).first()

    @staticmethod
    def photo_filter():
        return (Q(inheritance_mode='base_image', catalog_photo=True) |
                Q(inheritance_mode='vendor_image_only', own_photo=True) |
                (Q(inheritance_mode='mixed') & (Q(own_photo=True) | Q(catalog_photo=True))))

    def inventory_summary(self, vendor):
        products = self.inventory_products(vendor)
        result = products.aggregate(
            total=Count('id'),
            low=Count('id', filter=Q(low_stock_threshold__gt=0, stock__lte=F('low_stock_threshold'))),
            out=Count('id', filter=Q(stock__lte=0)),
            paused=Count('id', filter=Q(is_available=False)),
            missing_photo=Count('id', filter=~self.photo_filter()),
            category_pending=Count('id', filter=Q(category__isnull=True) | Q(category__is_active=False) | Q(category__show_in_customer_ui=False)),
            ready=Count('id', filter=Q(**ProductRepository.customer_visible_filter(), category__is_active=True, category__show_in_customer_ui=True, catalog_product__is_active=True) & self.photo_filter()),
            updated_at=Max('updated_at'),
        )
        return result

    def inventory_products(self, vendor):
        return Product.objects.filter(vendor=vendor).annotate(
            own_photo=Exists(ProductImage.objects.filter(product_id=OuterRef('pk'))),
            catalog_photo=Exists(CatalogProductImage.objects.filter(catalog_product_id=OuterRef('catalog_product_id'))),
        )

    def health_filter(self, query, health):
        filters = {
            'low': Q(low_stock_threshold__gt=0, stock__lte=F('low_stock_threshold'), stock__gt=0),
            'out': Q(stock__lte=0), 'paused': Q(is_available=False),
            'missing_photo': ~self.photo_filter(),
            'category_pending': Q(category__isnull=True) | Q(category__is_active=False) | Q(category__show_in_customer_ui=False),
            'ready': Q(**ProductRepository.customer_visible_filter(), category__is_active=True, category__show_in_customer_ui=True, catalog_product__is_active=True) & self.photo_filter(),
        }
        if health in filters:
            return query.annotate(own_photo=Exists(ProductImage.objects.filter(product_id=OuterRef('pk'))), catalog_photo=Exists(CatalogProductImage.objects.filter(catalog_product_id=OuterRef('catalog_product_id')))).filter(filters[health])
        return query

    def verification_summary(self, vendor):
        bank = VendorBankDetails.objects.filter(vendor=vendor).first()
        onboarding = VendorOnboarding.objects.filter(vendor=vendor).first()
        documents = VendorDocument.objects.filter(vendor=vendor).values('status').annotate(count=Count('id'))
        return {
            'bank': {'configured': bool(bank and bank.account_number_enc), 'verified': bool(bank and bank.is_verified), 'bank_name': bank.bank_name if bank else '', 'masked_account': bank.masked_account_number if bank and bank.account_number_enc else ''},
            'kyc_status': onboarding.kyc_status if onboarding else 'not_submitted',
            'onboarding_status': onboarding.onboarding_status if onboarding else 'not_submitted',
            'documents': {row['status']: row['count'] for row in documents},
        }

    def save(self, vendor, values):
        for key, value in values.items():
            setattr(vendor, key, value)
        vendor.save(update_fields=[*values, 'updated_at'])
        return vendor

    def mark_stock_reviewed(self, vendor):
        return self.save(vendor, {'stock_reviewed_at': timezone.now()})

    def documents(self, vendor):
        return VendorDocument.objects.filter(vendor=vendor).order_by('-uploaded_at')

    def create_document(self, vendor, values):
        upload = values['file']
        return VendorDocument.objects.create(vendor=vendor, **values, original_filename=upload.name, file_size_bytes=upload.size)
