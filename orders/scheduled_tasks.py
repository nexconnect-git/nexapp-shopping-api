import logging

from django_rq import job

from orders.actions import RefreshCustomerRecommendationsAction

logger = logging.getLogger(__name__)


@job('default')
def refresh_customer_recommendations(user_id=None, limit=24):
    """Refresh persisted recommendation snapshots for one customer or all customers."""
    result = RefreshCustomerRecommendationsAction().execute(user_id=user_id, limit=int(limit or 24))
    logger.info('[refresh_customer_recommendations] %s', result)
    return result
