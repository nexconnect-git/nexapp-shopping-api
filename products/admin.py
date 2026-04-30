from django.contrib import admin
from .models import (
    CatalogProduct,
    CatalogProductImage,
    CatalogProposal,
    CatalogProposalItem,
    Category,
    Product,
    ProductImage,
    ProductReview,
    VendorCatalogGrant,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class CatalogProductImageInline(admin.TabularInline):
    model = CatalogProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'catalog_product', 'category', 'price', 'stock', 'is_available')
    list_filter = ('is_available', 'is_featured', 'category', 'vendor')
    search_fields = ('name', 'catalog_product__name', 'vendor__store_name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('average_rating', 'total_ratings', 'total_orders', 'created_at', 'updated_at')
    inlines = [ProductImageInline]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('product__name', 'customer__username')


@admin.register(CatalogProduct)
class CatalogProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'unit', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'brand', 'barcode')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CatalogProductImageInline]


@admin.register(VendorCatalogGrant)
class VendorCatalogGrantAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'catalog_product', 'granted_by', 'granted_at')
    search_fields = ('vendor__store_name', 'catalog_product__name')


class CatalogProposalItemInline(admin.TabularInline):
    model = CatalogProposalItem
    extra = 0


@admin.register(CatalogProposal)
class CatalogProposalAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'status', 'submitted_at', 'reviewed_by', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('vendor__store_name',)
    inlines = [CatalogProposalItemInline]
