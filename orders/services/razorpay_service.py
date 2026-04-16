"""Razorpay payment service — wraps the razorpay SDK."""

import hashlib
import hmac
import logging

import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)


def _client() -> razorpay.Client:
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


class RazorpayService:
    """Handles Razorpay order creation and payment verification."""

    def create_order(self, amount_inr: float, currency: str = 'INR', receipt: str = '') -> dict:
        """Create a Razorpay order and return the full response dict.

        Args:
            amount_inr: Order total in INR (will be converted to paise).
            currency: ISO 4217 currency code, default 'INR'.
            receipt: Optional receipt string (e.g. NexConnect order number).

        Returns:
            Razorpay order dict containing at least ``id``, ``amount``, ``currency``.

        Raises:
            Exception: If the Razorpay API call fails.
        """
        amount_paise = int(amount_inr * 100)
        data = {
            'amount': amount_paise,
            'currency': currency,
            'receipt': receipt or '',
            'payment_capture': 1,  # auto-capture
        }
        try:
            order = _client().order.create(data=data)
            logger.info("Razorpay order created: %s for ₹%.2f", order['id'], amount_inr)
            return order
        except Exception as exc:
            logger.error("Razorpay order creation failed: %s", exc)
            raise

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verify the HMAC-SHA256 signature returned by the Razorpay checkout.

        Args:
            razorpay_order_id: The ``razorpay_order_id`` from the checkout callback.
            razorpay_payment_id: The ``razorpay_payment_id`` from the checkout callback.
            razorpay_signature: The ``razorpay_signature`` from the checkout callback.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            _client().utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
            })
            return True
        except razorpay.errors.SignatureVerificationError:
            return False

    def create_refund(self, payment_id: str, amount_inr: float) -> dict:
        """Initiate a Razorpay refund for a captured payment.

        Args:
            payment_id: The ``razorpay_payment_id`` to refund.
            amount_inr: Amount to refund in INR (converted to paise).

        Returns:
            Razorpay refund dict containing at least ``id``, ``amount``, ``status``.
        """
        amount_paise = int(amount_inr * 100)
        try:
            refund = _client().payment.refund(payment_id, {'amount': amount_paise, 'speed': 'normal'})
            logger.info("Razorpay refund initiated: %s for ₹%.2f", refund.get('id'), amount_inr)
            return refund
        except Exception as exc:
            logger.error("Razorpay refund failed for payment %s: %s", payment_id, exc)
            raise

    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        """Verify the signature on an incoming Razorpay webhook.

        Args:
            payload_body: Raw request body bytes.
            signature: Value of the ``X-Razorpay-Signature`` header.

        Returns:
            True if the signature matches, False otherwise.
        """
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        if not secret:
            logger.warning("RAZORPAY_WEBHOOK_SECRET not set — skipping webhook verification.")
            return True  # Allow in dev when secret not configured

        expected = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
