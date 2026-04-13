from .auth_views import RegisterView, LoginView, SetupSuperUserView
from .profile_views import ProfileView, ChangePasswordView
from .address_views import AddressViewSet
from .admin_views import AdminUserViewSet
from .admin_customers import AdminCustomerViewSet
from .admin_stats import AdminStatsView

__all__ = [
    'RegisterView',
    'LoginView',
    'SetupSuperUserView',
    'ProfileView',
    'ChangePasswordView',
    'AddressViewSet',
    'AdminUserViewSet',
    'AdminCustomerViewSet',
    'AdminStatsView',
]
