"""Payment actions — Razorpay order creation and verification."""

import logging

from django.conf import settings

from orders.actions.base import BaseAction
from orders.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class CreateRazorpayOrderAction(BaseAction):
    """Creates a Razorpay order for a NexConnect order and stores the order ID.

    The frontend uses the returned ``razorpay_order_id``, ``amount``, and
    ``key_id`` to open the Razorpay checkout modal.
    """

    def __init__(self, order):
        self._order = order

    def execute(self) -> dict:
        """Create the Razorpay order.

        Returns:
            Dict with ``razorpay_order_id``, ``amount`` (paise), ``currency``,
            ``key_id`` for the frontend checkout modal.

        Raises:
            ValueError: If the order already has a verified payment, or if
                        Razorpay credentials are not configured.
        """
        if self._order.is_payment_verified:
            raise ValueError('Payment has already been completed for this order.')

        if not getattr(settings, 'RAZORPAY_KEY_ID', ''):
            raise ValueError('Razorpay is not configured on this server.')

        rz_order = RazorpayService().create_order(
            amount_inr=float(self._order.total),
            receipt=self._order.order_number,
        )

        self._order.razorpay_order_id = rz_order['id']
        self._order.payment_method = 'razorpay'
        self._order.save(update_fields=['razorpay_order_id', 'payment_method', 'updated_at'])

        return {
            'razorpay_order_id': rz_order['id'],
            'amount': rz_order['amount'],
            'currency': rz_order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID,
        }


class VerifyRazorpayPaymentAction(BaseAction):
    """Verifies the Razorpay payment signature and marks the order as paid."""

    def __init__(self, order, razorpay_payment_id: str, razorpay_signature: str):
        self._order = order
        self._payment_id = razorpay_payment_id
        self._signature = razorpay_signature

    def execute(self):
        """Verify the signature and update the order.

        Returns:
            The updated Order instance.

        Raises:
            ValueError: If the signature is invalid or order has no Razorpay order ID.
        """
        if not self._order.razorpay_order_id:
            raise ValueError('No Razorpay order has been created for this order yet.')

        if self._order.is_payment_verified:
            raise ValueError('Payment has already been verified.')

        valid = RazorpayService().verify_payment_signature(
            razorpay_order_id=self._order.razorpay_order_id,
            razorpay_payment_id=self._payment_id,
            razorpay_signature=self._signature,
        )

        if not valid:
            logger.warning(
                "Invalid Razorpay signature for order %s (rz_order=%s, rz_payment=%s)",
                self._order.order_number,
                self._order.razorpay_order_id,
                self._payment_id,
            )
            raise ValueError('Payment verification failed. Invalid signature.')

        self._order.razorpay_payment_id = self._payment_id
        self._order.is_payment_verified = True
        self._order.save(update_fields=['razorpay_payment_id', 'is_payment_verified', 'updated_at'])

        logger.info(
            "Payment verified for order %s (rz_payment=%s)",
            self._order.order_number,
            self._payment_id,
        )
        return self._order
