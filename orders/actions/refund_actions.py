"""Razorpay refund actions."""

import logging

from orders.services.razorpay_service import RazorpayService
from .base import BaseAction

logger = logging.getLogger(__name__)


class IssueRazorpayRefundAction(BaseAction):
    """Initiate a Razorpay refund for a verified online payment.

    Raises ValueError if the order is not eligible (wrong payment method,
    payment not verified, or refund already initiated).
    """

    def execute(self, order) -> dict:
        if order.payment_method != 'razorpay':
            raise ValueError("Order was not paid online — no refund to issue.")
        if not order.is_payment_verified:
            raise ValueError("Payment has not been verified — cannot refund.")
        if order.razorpay_refund_id:
            raise ValueError("Refund already initiated.")

        refund = RazorpayService().create_refund(
            payment_id=order.razorpay_payment_id,
            amount_inr=float(order.total),
        )

        order.razorpay_refund_id = refund.get('id', '')
        order.refund_status = 'initiated'
        order.save(update_fields=['razorpay_refund_id', 'refund_status', 'updated_at'])
        logger.info("Refund initiated for order %s: %s", order.order_number, refund.get('id'))
        return refund
