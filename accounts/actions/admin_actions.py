"""Admin actions — orchestrate admin stats and customer management."""

from typing import Any, Dict

from django.core.cache import cache
from django.db.models import Count, Q, Sum

from accounts.admin_access import allows, granted_permissions
from backend.data.admin_console_repository import AdminConsoleRepository
from accounts.data.user_repository import UserRepository
from accounts.models.user import User
from accounts.actions.audit_actions import CreateAdminAuditLogAction


class GetAdminStatsAction:
    """Compute and optionally cache platform-wide aggregate statistics."""

    CACHE_KEY = 'admin_stats_v2'
    CACHE_TTL = 15  # seconds — reduced DB pressure; dashboard refreshes every 30s anyway

    def execute(self, user=None) -> Dict[str, Any]:
        """Return aggregated platform statistics, served from cache when fresh.

        Returns:
            Dictionary of platform statistics keyed by metric name.
        """
        data = cache.get(self.CACHE_KEY)
        if data is None:
            data = self._compute()
            cache.set(self.CACHE_KEY, data, self.CACHE_TTL)
        if user is None:
            return data
        grants = granted_permissions(user)
        result = {'generated_at': data.get('generated_at')}
        domains = {'orders': ['orders', 'total_orders', 'pending_orders', 'awaiting_fulfillment', 'orders_delivering', 'completed_orders', 'cancelled_orders', 'orders_placed', 'orders_delivered', 'orders_cancelled'], 'vendors': ['vendors', 'total_vendors', 'pending_vendors'], 'dispatch': ['delivery_partners', 'total_delivery_partners', 'pending_delivery_partners'], 'customers': ['customers', 'total_customers'], 'catalog': ['products', 'total_products'], 'finance': ['total_revenue'], 'support': ['open_issues']}
        for domain, keys in domains.items():
            if allows(user, f'{domain}.view', grants):
                result.update({key: data[key] for key in keys})
        return result

    @staticmethod
    def _compute() -> Dict[str, Any]:
        return AdminConsoleRepository.overview()


class ManageCustomerAction:
    """Apply admin-sourced updates to a customer account."""

    def __init__(self, user_id: str, data: Dict[str, Any]):
        self._user_id = user_id
        self._data = data

    def execute(self) -> User:
        """Update the customer and return the saved instance.

        Returns:
            The updated User instance.

        Raises:
            ValueError: If no customer with the given ID exists.
        """
        user = UserRepository.get_customer_by_id(self._user_id)
        if user is None:
            raise ValueError('Customer not found.')
        return UserRepository.update(user, self._data)


class UpdateAccountStatusAction:
    """Update the account status (is_active / status field) of any user."""

    ALLOWED_STATUSES = {'active', 'suspended', 'pending', 'rejected'}

    def execute(self, user_id: str, status: str, request=None) -> User:
        """Set a new status on the target user and persist the change.

        Args:
            user_id: Primary key of the user to update.
            status: New status string (active / suspended / pending / rejected).
            request: Optional DRF request (reserved for future audit logging).

        Returns:
            The updated User instance.

        Raises:
            ValueError: If the user is not found or the status value is invalid.
        """
        if status not in self.ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. "
                f"Allowed values: {', '.join(sorted(self.ALLOWED_STATUSES))}."
            )

        user = UserRepository.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User with id '{user_id}' not found.")

        # Map logical status to model fields
        update_data: Dict[str, Any] = {'status': status}
        if status == 'active':
            update_data['is_active'] = True
        elif status in ('suspended', 'rejected'):
            update_data['is_active'] = False

        updated_user = UserRepository.update(user, update_data)
        CreateAdminAuditLogAction().execute(
            request=request,
            action='status_change',
            entity_type='user',
            entity_id=str(user.id),
            summary=f"Updated account status for {user.username} to {status}.",
            metadata={'status': status, 'fields': update_data},
        )
        return updated_user


class CheckUserAvailabilityAction:
    """Check whether user identity fields are available for onboarding flows."""

    VALID_FIELDS = {'username', 'email', 'phone'}
    VALID_ROLES = {'customer', 'vendor', 'delivery', 'admin'}

    def execute(self, field: str, value: str, exclude_user_id: str = '', role: str = '') -> Dict[str, Any]:
        normalized_field = (field or '').strip().lower()
        normalized_value = (value or '').strip()
        normalized_role = (role or '').strip().lower()
        if normalized_field not in self.VALID_FIELDS:
            raise ValueError('field must be username, email, or phone.')
        if not normalized_value:
            raise ValueError('value is required.')
        if normalized_role and normalized_role not in self.VALID_ROLES:
            raise ValueError('role must be customer, vendor, delivery, or admin.')

        exclude_id = exclude_user_id or None
        role_scope = normalized_role or None
        if normalized_field == 'username':
            exists = UserRepository.username_exists(normalized_value, exclude_user_id=exclude_id)
            suggestions = self._username_suggestions(normalized_value) if exists else []
        elif normalized_field == 'email':
            exists = UserRepository.email_exists(normalized_value, exclude_user_id=exclude_id, role=role_scope)
            suggestions = self._email_suggestions(normalized_value, role=role_scope) if exists else []
        else:
            exists = UserRepository.phone_exists(normalized_value, exclude_user_id=exclude_id, role=role_scope)
            suggestions = self._phone_suggestions(normalized_value, role=role_scope) if exists else []

        return {
            'field': normalized_field,
            'value': normalized_value,
            'role': normalized_role,
            'unique': not exists,
            'message': '' if not exists else f'{normalized_field.replace("_", " ").title()} is already in use.',
            'suggestions': suggestions,
        }

    def _username_suggestions(self, value: str) -> list[str]:
        base = ''.join(ch.lower() if ch.isalnum() else '_' for ch in value).strip('_') or 'user'
        candidates = []
        for suffix in ('01', '02', 'hq', 'ops', 'new'):
            candidate = f'{base[:150 - len(suffix) - 1]}_{suffix}'
            if not UserRepository.username_exists(candidate):
                candidates.append(candidate)
            if len(candidates) >= 3:
                break
        return candidates

    def _email_suggestions(self, value: str, role: str | None = None) -> list[str]:
        if '@' not in value:
            return []
        local, domain = value.split('@', 1)
        if not local or not domain:
            return []
        candidates = []
        for suffix in ('ops', 'admin', 'new'):
            candidate = f'{local}+{suffix}@{domain}'
            if not UserRepository.email_exists(candidate, role=role):
                candidates.append(candidate)
            if len(candidates) >= 3:
                break
        return candidates

    def _phone_suggestions(self, value: str, role: str | None = None) -> list[str]:
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) < 4:
            return []

        prefix = '+' if value.strip().startswith('+') else ''
        base = digits[:-1]
        last_digit = int(digits[-1])
        candidates = []
        for offset in range(1, 10):
            candidate = f'{prefix}{base}{(last_digit + offset) % 10}'
            if not UserRepository.phone_exists(candidate, role=role):
                candidates.append(candidate)
            if len(candidates) >= 3:
                break
        return candidates
