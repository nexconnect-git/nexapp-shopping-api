from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from orders.models import Order, PaymentSession


class Command(BaseCommand):
    help = "Reconcile stale Razorpay payment sessions and order payment state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-minutes",
            type=int,
            default=10,
            help="Only reconcile sessions/orders older than this many minutes.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report actions without changing database state.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options["older_than_minutes"])
        dry_run = options["dry_run"]
        summary = {
            "paid_sessions_without_orders": 0,
            "orders_repaired": 0,
            "unmatched_orders": 0,
        }

        with transaction.atomic():
            paid_without_orders = (
                PaymentSession.objects.select_for_update()
                .filter(status=PaymentSession.STATUS_PAID, created_at__lt=cutoff)
                .filter(orders__isnull=True)
                .distinct()
            )
            for session in paid_without_orders:
                summary["paid_sessions_without_orders"] += 1
                if dry_run:
                    continue
                metadata = session.metadata or {}
                metadata["reconciliation_required"] = True
                metadata["reconciliation_reason"] = "paid_gateway_session_without_application_order"
                metadata["reconciled_at"] = timezone.now().isoformat()
                session.metadata = metadata
                if not session.mismatch_reason:
                    session.mismatch_reason = "Payment captured but no application order is linked."
                session.save(update_fields=["metadata", "mismatch_reason", "updated_at"])

            unpaid_orders = (
                Order.objects.select_for_update()
                .filter(
                    payment_method="razorpay",
                    is_payment_verified=False,
                    razorpay_order_id__gt="",
                    placed_at__lt=cutoff,
                )
                .exclude(status="cancelled")
            )
            for order in unpaid_orders:
                session = (
                    PaymentSession.objects.select_for_update()
                    .filter(
                        gateway_order_id=order.razorpay_order_id,
                        status__in=[
                            PaymentSession.STATUS_PAID,
                            PaymentSession.STATUS_RECONCILED,
                        ],
                    )
                    .first()
                )
                if not session:
                    summary["unmatched_orders"] += 1
                    continue

                summary["orders_repaired"] += 1
                if dry_run:
                    continue
                order.is_payment_verified = True
                if session.gateway_payment_id and not order.razorpay_payment_id:
                    order.razorpay_payment_id = session.gateway_payment_id
                order.save(update_fields=["is_payment_verified", "razorpay_payment_id", "updated_at"])
                session.orders.add(order)
                if session.status != PaymentSession.STATUS_RECONCILED:
                    session.status = PaymentSession.STATUS_RECONCILED
                    session.save(update_fields=["status", "updated_at"])

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(f"Payment reconciliation summary: {summary}"))
