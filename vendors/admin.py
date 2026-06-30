from django.contrib import admin
from .models import (
    FulfillmentNode,
    FulfillmentNodeInventory,
    FulfillmentNodeServiceArea,
    Vendor,
    VendorReview,
)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'city', 'status', 'is_open', 'average_rating')
    list_filter = ('status', 'is_open', 'is_featured', 'city')
    search_fields = ('store_name', 'city', 'user__username')
    readonly_fields = ('average_rating', 'total_ratings', 'created_at', 'updated_at')


@admin.register(VendorReview)
class VendorReviewAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'customer', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('vendor__store_name', 'customer__username')


@admin.register(FulfillmentNode)
class FulfillmentNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'node_type', 'vendor', 'city', 'state', 'status', 'is_accepting_orders')
    list_filter = ('node_type', 'status', 'is_accepting_orders', 'city', 'state')
    search_fields = ('name', 'code', 'vendor__store_name', 'city', 'state', 'postal_code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FulfillmentNodeServiceArea)
class FulfillmentNodeServiceAreaAdmin(admin.ModelAdmin):
    list_display = ('label', 'node', 'city', 'state', 'postal_code', 'radius_km', 'is_active', 'priority')
    list_filter = ('is_active', 'city', 'state')
    search_fields = ('label', 'node__name', 'city', 'state', 'postal_code')


@admin.register(FulfillmentNodeInventory)
class FulfillmentNodeInventoryAdmin(admin.ModelAdmin):
    list_display = ('node', 'product', 'stock', 'reserved_stock', 'is_available', 'updated_at')
    list_filter = ('is_available', 'node__status')
    search_fields = ('node__name', 'product__name', 'product__sku')
    readonly_fields = ('updated_at',)
