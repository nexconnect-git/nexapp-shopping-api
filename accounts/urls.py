from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from accounts import views

router = DefaultRouter()
router.register(r'addresses', views.AddressViewSet, basename='address')
router.register(r'admin-users', views.AdminUserViewSet, basename='admin-user')

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('send-verification-email/', views.SendVerificationEmailView.as_view(), name='send-verification-email'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('password-reset/', views.RequestPasswordResetView.as_view(), name='password-reset'),
    path('password-reset/confirm/', views.ConfirmPasswordResetView.as_view(), name='password-reset-confirm'),
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/topup/', views.InitiateWalletTopUpView.as_view(), name='wallet-topup'),
    path('wallet/verify-topup/', views.VerifyWalletTopUpView.as_view(), name='wallet-verify-topup'),
    path('loyalty/', views.LoyaltyView.as_view(), name='loyalty'),
    path('loyalty/preview/', views.LoyaltyPreviewView.as_view(), name='loyalty-preview'),
    path('setup/', views.SetupSuperUserView.as_view(), name='setup'),
    path('', include(router.urls)),
]
