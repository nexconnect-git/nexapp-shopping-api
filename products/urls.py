from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

review_router = DefaultRouter()
review_router.register(r'reviews', views.ProductReviewViewSet, basename='product-review')

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('list/', views.ProductListView.as_view(), name='product-list'),
    path('featured/', views.FeaturedProductsView.as_view(), name='featured-products'),
    path('ai-image/', views.AIImageGenerateView.as_view(), name='ai-image-generate'),
    path('<uuid:product_id>/', include(review_router.urls)),
    path('<uuid:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    # Vendor image management
    path('<uuid:pk>/images/', views.VendorProductImagesView.as_view(), name='vendor-product-images'),
    path('<uuid:pk>/images/<uuid:img_pk>/', views.VendorProductImageDetailView.as_view(), name='vendor-product-image-detail'),
    # Vendor stock management
    path('<uuid:pk>/stock/', views.VendorStockUpdateView.as_view(), name='vendor-stock-update'),
    path('low-stock/', views.VendorLowStockView.as_view(), name='vendor-low-stock'),
]

