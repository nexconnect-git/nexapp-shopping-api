from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, OrderTracking


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_price', 'quantity', 'subtotal')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'added_at')
    search_fields = ('cart__user__username', 'product__name')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'vendor', 'status', 'total', 'placed_at')
    list_filter = ('status', 'placed_at')
    search_fields = ('order_number', 'customer__username', 'vendor__store_name')
    readonly_fields = ('order_number', 'placed_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'timestamp')
    list_filter = ('status',)
    search_fields = ('order__order_number',)
