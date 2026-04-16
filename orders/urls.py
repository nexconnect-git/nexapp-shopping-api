from django.urls import path, include
from rest_framework.routers import DefaultRouter
from orders import views

router = DefaultRouter()
router.register(r'admin-coupons', views.AdminCouponViewSet, basename='admin-coupon')

urlpatterns = [
    path('banners/', views.BannerListView.as_view(), name='banner-list'),
    path('coupons/', views.CustomerCouponListView.as_view(), name='coupon-list'),
    path('coupons/validate/', views.ValidateCouponView.as_view(), name='coupon-validate'),
    path('', include(router.urls)),
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.AddToCartView.as_view(), name='cart-add'),
    path('cart/items/<uuid:pk>/', views.UpdateCartItemView.as_view(), name='cart-item-update'),
    path('cart/clear/', views.ClearCartView.as_view(), name='cart-clear'),
    path('cancellation-policy/', views.CancellationPolicyView.as_view(), name='cancellation-policy'),
    path('delivery-fee-preview/', views.DeliveryFeePreviewView.as_view(), name='delivery-fee-preview'),
    path('initiate-checkout-payment/', views.InitiateCheckoutPaymentView.as_view(), name='initiate-checkout-payment'),
    path('create/', views.CreateOrderView.as_view(), name='order-create'),
    path('list/', views.OrderListView.as_view(), name='order-list'),
    path('razorpay-webhook/', views.RazorpayWebhookView.as_view(), name='razorpay-webhook'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/cancel/', views.CancelOrderView.as_view(), name='order-cancel'),
    path('<uuid:pk>/tracking/', views.OrderTrackingView.as_view(), name='order-tracking'),
    path('<uuid:pk>/payment-qr/', views.OrderPaymentQRView.as_view(), name='order-payment-qr'),
    path('<uuid:pk>/create-payment/', views.CreateRazorpayOrderView.as_view(), name='order-create-payment'),
    path('<uuid:pk>/verify-payment/', views.VerifyRazorpayPaymentView.as_view(), name='order-verify-payment'),
    path('<uuid:pk>/rate/', views.SubmitOrderRatingView.as_view(), name='order-rate'),
    path('<uuid:pk>/reorder/', views.ReorderView.as_view(), name='order-reorder'),
    # Order Issues
    path('issues/', views.CustomerOrderIssueListCreateView.as_view(), name='issue-list'),
    path('issues/<uuid:pk>/', views.CustomerOrderIssueDetailView.as_view(), name='issue-detail'),
    path('issues/<uuid:pk>/messages/', views.IssueMessageCreateView.as_view(), name='issue-message'),
]
