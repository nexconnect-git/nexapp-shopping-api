from backend.views.health_views import health_live, health_ready
from backend.views.media_views import MediaFileView
from backend.views.customer_views import (
    CustomerActiveOrderView,
    CustomerBestCouponView,
    CustomerBuyAgainView,
    CustomerCartSuggestionsView,
    CustomerCheckoutSlotsView,
    CustomerExploreView,
    CustomerHomeView,
    CustomerOrderConfirmationView,
    CustomerServiceabilityView,
)
from backend.views.scheduled_task_views import (
    AdminScheduledTaskCancelView,
    AdminScheduledTaskListCreateView,
)

__all__ = [
    'AdminScheduledTaskCancelView',
    'AdminScheduledTaskListCreateView',
    'CustomerActiveOrderView',
    'CustomerBestCouponView',
    'CustomerBuyAgainView',
    'CustomerCartSuggestionsView',
    'CustomerCheckoutSlotsView',
    'CustomerExploreView',
    'CustomerHomeView',
    'CustomerOrderConfirmationView',
    'CustomerServiceabilityView',
    'MediaFileView',
    'health_live',
    'health_ready',
]
