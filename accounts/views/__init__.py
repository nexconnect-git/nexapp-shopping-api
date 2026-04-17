from accounts.views.auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    SendVerificationEmailView,
    VerifyEmailView,
    SetupSuperUserView,
)
from accounts.views.profile_views import ProfileView, ChangePasswordView
from accounts.views.address_views import AddressViewSet
from accounts.views.admin_views import AdminUserViewSet
from accounts.views.admin_customers import AdminCustomerViewSet
from accounts.views.admin_stats import AdminStatsView
from accounts.views.wallet_views import WalletView, InitiateWalletTopUpView, VerifyWalletTopUpView
from accounts.views.loyalty_views import LoyaltyView, LoyaltyPreviewView
from accounts.views.password_reset_views import RequestPasswordResetView, ConfirmPasswordResetView
from accounts.views.referral_views import MyReferralView, ApplyReferralCodeView, ReferralCodeLookupView

__all__ = [
    'RegisterView',
    'LoginView',
    'LogoutView',
    'SendVerificationEmailView',
    'VerifyEmailView',
    'SetupSuperUserView',
    'ProfileView',
    'ChangePasswordView',
    'AddressViewSet',
    'AdminUserViewSet',
    'AdminCustomerViewSet',
    'AdminStatsView',
    'WalletView',
    'InitiateWalletTopUpView',
    'VerifyWalletTopUpView',
    'LoyaltyView',
    'LoyaltyPreviewView',
    'RequestPasswordResetView',
    'ConfirmPasswordResetView',
    'MyReferralView',
    'ApplyReferralCodeView',
    'ReferralCodeLookupView',
]
