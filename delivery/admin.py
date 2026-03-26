from django.contrib import admin
from .models import DeliveryPartner, DeliveryReview, DeliveryEarning


@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'status', 'is_approved', 'average_rating')
    list_filter = ('vehicle_type', 'status', 'is_approved')
    search_fields = ('user__username', 'vehicle_number', 'license_number')
    readonly_fields = ('average_rating', 'total_deliveries', 'total_earnings', 'created_at', 'updated_at')


@admin.register(DeliveryReview)
class DeliveryReviewAdmin(admin.ModelAdmin):
    list_display = ('delivery_partner', 'customer', 'order', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('delivery_partner__user__username', 'customer__username')


@admin.register(DeliveryEarning)
class DeliveryEarningAdmin(admin.ModelAdmin):
    list_display = ('delivery_partner', 'order', 'amount', 'created_at')
    search_fields = ('delivery_partner__user__username', 'order__order_number')
