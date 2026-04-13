"""Admin actions — orchestrate admin stats and customer management."""

from typing import Any, Dict

from django.core.cache import cache
from django.db.models import Count, Q, Sum

from accounts.data.user_repository import UserRepository
from accounts.models.user import User


class GetAdminStatsAction:
    """Compute and optionally cache platform-wide aggregate statistics."""

    CACHE_KEY = 'admin_stats_v1'
    CACHE_TTL = 120  # seconds — reduced DB pressure; dashboard refreshes every 30s anyway

    def execute(self) -> Dict[str, Any]:
        """Return aggregated platform statistics, served from cache when fresh.

        Returns:
            Dictionary of platform statistics keyed by metric name.
        """
        data = cache.get(self.CACHE_KEY)
        if data is None:
            data = self._compute()
            cache.set(self.CACHE_KEY, data, self.CACHE_TTL)
        return data

    @staticmethod
    def _compute() -> Dict[str, Any]:
        # Import here to avoid circular imports at module load time
        from orders.models import Order
        from vendors.models import Vendor
        from products.models import Product
        from delivery.models import DeliveryPartner

        # Single aggregate pass over orders table
        order_agg = Order.objects.aggregate(
            total_count=Count('id'),
            placed=Count('id', filter=Q(status='placed')),
            delivering=Count('id', filter=Q(status__in=['picked_up', 'on_the_way'])),
            delivered=Count('id', filter=Q(status='delivered')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            revenue=Sum('total', filter=Q(status='delivered')),
        )

        total_orders      = order_agg['total_count'] or 0
        placed_orders     = order_agg['placed']      or 0
        delivering_orders = order_agg['delivering']  or 0
        delivered_orders  = order_agg['delivered']   or 0
        cancelled_orders  = order_agg['cancelled']   or 0
        total_revenue     = float(order_agg['revenue'] or 0)

        # Batch all simple counts in a single aggregate per model
        vendor_agg = Vendor.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
        )
        partner_agg = DeliveryPartner.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(is_approved=False)),
        )

        total_vendors    = vendor_agg['total']   or 0
        pending_vendors  = vendor_agg['pending'] or 0
        total_partners   = partner_agg['total']  or 0
        pending_partners = partner_agg['pending'] or 0
        total_products   = Product.objects.count()
        total_customers  = User.objects.filter(role='customer').count()

        return {
            'customers':                  total_customers,
            'vendors':                    total_vendors,
            'pending_vendors':            pending_vendors,
            'delivery_partners':          total_partners,
            'pending_delivery_partners':  pending_partners,
            'products':                   total_products,
            'orders':                     total_orders,
            'orders_placed':              placed_orders,
            'orders_delivering':          delivering_orders,
            'orders_delivered':           delivered_orders,
            'orders_cancelled':           cancelled_orders,
            'total_revenue':              total_revenue,
            'total_vendors':              total_vendors,
            'total_products':             total_products,
            'total_customers':            total_customers,
            'total_delivery_partners':    total_partners,
            'total_orders':               total_orders,
            'pending_orders':             placed_orders,
            'completed_orders':           delivered_orders,
            'cancelled_orders':           cancelled_orders,
        }


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

        return UserRepository.update(user, update_data)
