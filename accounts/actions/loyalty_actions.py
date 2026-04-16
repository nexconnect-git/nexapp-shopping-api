"""Loyalty points business logic."""

import logging
from decimal import Decimal

from django.db import transaction

from accounts.models.loyalty import LoyaltyAccount, LoyaltyTransaction

logger = logging.getLogger(__name__)

# Points earned per ₹1 spent (configurable)
POINTS_PER_RUPEE = 1
# ₹ value of one point when redeeming
RUPEE_VALUE_PER_POINT = Decimal("0.25")
# Maximum % of order total payable with points
MAX_POINTS_REDEMPTION_PCT = 20


class GetOrCreateLoyaltyAction:
    @staticmethod
    def execute(user) -> LoyaltyAccount:
        account, _ = LoyaltyAccount.objects.get_or_create(user=user)
        return account


class EarnLoyaltyPointsAction:
    @staticmethod
    @transaction.atomic
    def execute(user, order_total: Decimal, reference_id: str, description: str = '') -> LoyaltyAccount:
        points = max(1, int(order_total * POINTS_PER_RUPEE))
        account = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)[0]
        account.points += points
        account.lifetime_points += points
        account.save(update_fields=['points', 'lifetime_points', 'updated_at'])
        LoyaltyTransaction.objects.create(
            account=account,
            points=points,
            transaction_type='earn',
            reference_id=reference_id,
            description=description or f"Earned {points} pts for order {reference_id}",
        )
        return account


class RedeemLoyaltyPointsAction:
    @staticmethod
    @transaction.atomic
    def execute(user, points_to_redeem: int, reference_id: str, description: str = '') -> tuple[LoyaltyAccount, Decimal]:
        """Redeem points. Returns (account, rupee_discount)."""
        if points_to_redeem <= 0:
            raise ValueError("Points to redeem must be positive.")
        account = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)[0]
        if account.points < points_to_redeem:
            raise ValueError(
                f"Insufficient points. Available: {account.points}, Required: {points_to_redeem}"
            )
        rupee_discount = Decimal(str(points_to_redeem)) * RUPEE_VALUE_PER_POINT
        account.points -= points_to_redeem
        account.save(update_fields=['points', 'updated_at'])
        LoyaltyTransaction.objects.create(
            account=account,
            points=-points_to_redeem,
            transaction_type='redeem',
            reference_id=reference_id,
            description=description or f"Redeemed {points_to_redeem} pts",
        )
        return account, rupee_discount
