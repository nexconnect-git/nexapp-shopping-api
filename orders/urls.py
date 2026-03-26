from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.AddToCartView.as_view(), name='cart-add'),
    path('cart/items/<uuid:pk>/', views.UpdateCartItemView.as_view(), name='cart-item-update'),
    path('cart/clear/', views.ClearCartView.as_view(), name='cart-clear'),
    path('create/', views.CreateOrderView.as_view(), name='order-create'),
    path('list/', views.OrderListView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/cancel/', views.CancelOrderView.as_view(), name='order-cancel'),
    path('<uuid:pk>/tracking/', views.OrderTrackingView.as_view(), name='order-tracking'),
]
