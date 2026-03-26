from django.contrib import admin
from .models import Vendor, VendorReview


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
