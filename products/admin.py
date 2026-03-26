from django.contrib import admin
from .models import Category, Product, ProductImage, ProductReview


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'category', 'price', 'stock', 'is_available')
    list_filter = ('is_available', 'is_featured', 'category', 'vendor')
    search_fields = ('name', 'vendor__store_name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('average_rating', 'total_ratings', 'total_orders', 'created_at', 'updated_at')
    inlines = [ProductImageInline]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('product__name', 'customer__username')
