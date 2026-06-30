from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orders.models import InventoryReservation, Order, PaymentSession
from products.models import Product
from vendors.models import FulfillmentNodeInventory


@dataclass
class ReservationReconciliationResult:
    expired_reserved: int = 0
    released_cancelled: int = 0
    released_failed_payment: int = 0
    product_units_restored: int = 0
    node_units_restored: int = 0

    def as_dict(self):
        return {
            "expired_reserved": self.expired_reserved,
            "released_cancelled": self.released_cancelled,
            "released_failed_payment": self.released_failed_payment,
            "product_units_restored": self.product_units_restored,
            "node_units_restored": self.node_units_restored,
        }


class ReservationInventoryAction:
    """Release reservation ledgers and restore committed stock once."""

    @transaction.atomic
    def release_order(self, order: Order, reason: str = "cancelled") -> ReservationReconciliationResult:
        result = ReservationReconciliationResult()
        reservations = list(
            InventoryReservation.objects.select_for_update()
            .select_related("product", "fulfillment_node")
            .filter(order=order, status=InventoryReservation.STATUS_COMMITTED)
        )
        now = timezone.now()
        for reservation in reservations:
            self._restore_product_stock(reservation)
            self._restore_node_stock(reservation)
            reservation.status = InventoryReservation.STATUS_RELEASED
            reservation.released_at = now
            reservation.save(update_fields=["status", "released_at", "updated_at"])
            result.released_cancelled += 1 if reason == "cancelled" else 0
            result.released_failed_payment += 1 if reason == "failed_payment" else 0
            result.product_units_restored += int(reservation.quantity or 0)
            if reservation.fulfillment_node_id:
                result.node_units_restored += int(reservation.quantity or 0)
        return result

    def _restore_product_stock(self, reservation: InventoryReservation) -> None:
        if not reservation.product_id:
            return
        Product.objects.filter(pk=reservation.product_id).update(stock=F("stock") + reservation.quantity)
        if reservation.product and reservation.product.status == "sold_out":
            Product.objects.filter(pk=reservation.product_id).update(status="active")

    def _restore_node_stock(self, reservation: InventoryReservation) -> None:
        if not reservation.fulfillment_node_id:
            return
        FulfillmentNodeInventory.objects.filter(
            node_id=reservation.fulfillment_node_id,
            product_id=reservation.product_id,
        ).update(stock=F("stock") + reservation.quantity, is_available=True)


class ReconcileInventoryReservationsAction:
    """Scheduled reconciliation for expired and failed reservation flows."""

    def execute(self, failed_payment_age_minutes: int = 60, dry_run: bool = False) -> dict:
        result = ReservationReconciliationResult()
        result.expired_reserved += self._expire_stale_reserved_rows(dry_run=dry_run)
        failed_payment_age_minutes = max(5, int(failed_payment_age_minutes or 60))
        result = self._release_cancelled_orders(result, dry_run=dry_run)
        result = self._release_failed_payment_orders(result, failed_payment_age_minutes, dry_run=dry_run)
        payload = result.as_dict()
        payload["dry_run"] = dry_run
        return payload

    def _expire_stale_reserved_rows(self, dry_run: bool = False) -> int:
        queryset = InventoryReservation.objects.filter(
            status=InventoryReservation.STATUS_RESERVED,
            reserved_until__lt=timezone.now(),
        )
        if dry_run:
            return queryset.count()
        return queryset.update(
            status=InventoryReservation.STATUS_EXPIRED,
            released_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def _release_cancelled_orders(
        self,
        result: ReservationReconciliationResult,
        dry_run: bool = False,
    ) -> ReservationReconciliationResult:
        order_ids = (
            InventoryReservation.objects.filter(
                status=InventoryReservation.STATUS_COMMITTED,
                order__status="cancelled",
            )
            .values_list("order_id", flat=True)
            .distinct()
        )
        if dry_run:
            reservations = InventoryReservation.objects.filter(
                status=InventoryReservation.STATUS_COMMITTED,
                order_id__in=order_ids,
            )
            result.released_cancelled += reservations.count()
            result.product_units_restored += sum(int(qty or 0) for qty in reservations.values_list("quantity", flat=True))
            result.node_units_restored += sum(
                int(qty or 0)
                for qty in reservations.filter(fulfillment_node__isnull=False).values_list("quantity", flat=True)
            )
            return result
        release_action = ReservationInventoryAction()
        for order in Order.objects.filter(id__in=order_ids):
            released = release_action.release_order(order, reason="cancelled")
            result.released_cancelled += released.released_cancelled
            result.product_units_restored += released.product_units_restored
            result.node_units_restored += released.node_units_restored
        return result

    def _release_failed_payment_orders(
        self,
        result: ReservationReconciliationResult,
        failed_payment_age_minutes: int,
        dry_run: bool = False,
    ) -> ReservationReconciliationResult:
        cutoff = timezone.now() - timedelta(minutes=failed_payment_age_minutes)
        order_ids = (
            PaymentSession.objects.filter(
                status=PaymentSession.STATUS_FAILED,
                updated_at__lte=cutoff,
                orders__isnull=False,
            )
            .values_list("orders__id", flat=True)
            .distinct()
        )
        release_action = ReservationInventoryAction()
        for order in Order.objects.filter(
            id__in=order_ids,
            payment_method="razorpay",
            is_payment_verified=False,
        ).exclude(status="cancelled"):
            if dry_run:
                reservations = InventoryReservation.objects.filter(
                    order=order,
                    status=InventoryReservation.STATUS_COMMITTED,
                )
                result.released_failed_payment += reservations.count()
                result.product_units_restored += sum(
                    int(qty or 0)
                    for qty in reservations.values_list("quantity", flat=True)
                )
                result.node_units_restored += sum(
                    int(qty or 0)
                    for qty in reservations.filter(fulfillment_node__isnull=False).values_list("quantity", flat=True)
                )
                continue
            order.status = "cancelled"
            order.save(update_fields=["status", "updated_at"])
            released = release_action.release_order(order, reason="failed_payment")
            result.released_failed_payment += released.released_failed_payment
            result.product_units_restored += released.product_units_restored
            result.node_units_restored += released.node_units_restored
        return result
