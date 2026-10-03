"""Shared permission policy using the existing AdminPermissionGrant model."""
from accounts.data.admin_permission_repository import AdminPermissionGrantRepository
from accounts.data.user_repository import UserRepository

ADMIN_PERMISSION_CATALOG = {
    'overview.view': 'View overview', 'orders.view': 'View orders', 'orders.manage': 'Manage orders',
    'dispatch.view': 'View dispatch and fulfillment', 'dispatch.manage': 'Manage dispatch and fulfillment',
    'vendors.view': 'View vendors', 'vendors.manage': 'Manage vendors',
    'customers.view': 'View customers', 'customers.manage': 'Manage customers',
    'catalog.view': 'View catalog', 'catalog.manage': 'Manage catalog',
    'support.view': 'View support', 'support.manage': 'Manage support',
    'finance.view': 'View finance', 'finance.manage': 'Manage finance records',
    'growth.view': 'View promotions', 'growth.manage': 'Manage promotions',
    'notifications.view': 'View notifications', 'notifications.manage': 'Manage notifications',
    'automation.view': 'View jobs', 'automation.manage': 'Manage jobs',
    'settings.view': 'View settings', 'settings.manage': 'Manage settings',
    'audit.view': 'View audits', 'users.reset_password': 'Initiate individual password resets',
}

def granted_permissions(user):
    return set(AdminPermissionGrantRepository.list(user_id=user.pk).filter(scope={}).values_list('permission', flat=True))

def allows(user, permission, permissions=None):
    if not (user and user.is_authenticated and user.is_active and user.role == 'admin'):
        return False
    if user.is_superuser:
        return True
    grants = granted_permissions(user) if permissions is None else permissions
    return permission in grants or (permission.endswith('.view') and permission.replace('.view', '.manage') in grants)


def current_session_user(user):
    if not user or not user.is_authenticated:
        return None
    current = UserRepository.get_by_id(user.pk)
    return current if current and current.is_active and current.password == user.password else None

def required_permission(view, method):
    if getattr(view, 'allow_admin_identity', False):
        return None
    explicit = getattr(view, 'required_admin_permission', None)
    if explicit:
        return explicit.replace('.manage', '.view') if method in ('GET', 'HEAD', 'OPTIONS') else explicit
    name = type(view).__name__
    groups = (
        ('overview', ('AdminStats',)), ('automation', ('ScheduledTask',)), ('audit', ('AdminAudit',)),
        ('finance', ('Payout', 'Payments', 'RefundLedger', 'FinanceExport')),
        ('support', ('Issue', 'AdminTicket')), ('catalog', ('Product', 'Catalog', 'Category')),
        ('growth', ('Banner', 'CustomerContent', 'Coupon')), ('settings', ('Setting', 'Feature', 'TaxRule', 'DeliveryZone')),
        ('dispatch', ('Fulfillment', 'DeliveryPartner', 'DeliveryReassign', 'Asset')),
        ('vendors', ('Vendor',)), ('customers', ('Customer',)), ('notifications', ('Notification',)),
        ('orders', ('AdminOrder',)),
    )
    for domain, names in groups:
        if any(part in name for part in names):
            return f'{domain}.view' if method in ('GET', 'HEAD', 'OPTIONS') else f'{domain}.manage'
    if 'IdentityAvailability' in name:
        return None
    return 'settings.manage'
