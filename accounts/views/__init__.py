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
]
