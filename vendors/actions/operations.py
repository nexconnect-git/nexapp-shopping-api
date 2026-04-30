from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from delivery.models import DeliveryAssignment
from notifications.models import Notification
from orders.models import Order
from products.models import Product
from support.models import SupportTicket
from vendors.actions.base import BaseAction
from vendors.models import VendorPayout


class VendorOperationsSummaryAction(BaseAction):
    def execute(self, vendor):
        today = timezone.localdate()
        today_orders = Order.objects.filter(vendor=vendor, placed_at__date=today)
        active_orders = Order.objects.filter(
            vendor=vendor,
            status__in=["placed", "confirmed", "preparing", "ready", "picked_up", "on_the_way"],
        )
        low_stock = Product.objects.filter(
            vendor=vendor,
            low_stock_threshold__gt=0,
            stock__lte=F("low_stock_threshold"),
        )

        status_counts = {
            row["status"]: row["count"]
            for row in active_orders.values("status").annotate(count=Count("id"))
        }
        assignment_counts = {
            row["status"]: row["count"]
            for row in DeliveryAssignment.objects.filter(order__vendor=vendor)
            .values("status")
            .annotate(count=Count("id"))
        }

        today_revenue = today_orders.filter(status="delivered").aggregate(
            total=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )["total"] or Decimal("0")

        return {
            "store": {
                "is_open": vendor.is_open,
                "is_accepting_orders": vendor.is_accepting_orders,
                "auto_order_acceptance": vendor.auto_order_acceptance,
                "closing_time": str(vendor.closing_time) if vendor.closing_time else None,
            },
            "today": {
                "revenue": today_revenue,
                "orders": today_orders.count(),
                "delivered_orders": today_orders.filter(status="delivered").count(),
            },
            "orders": {
                "new": status_counts.get("placed", 0),
                "confirmed": status_counts.get("confirmed", 0),
                "preparing": status_counts.get("preparing", 0),
                "ready": status_counts.get("ready", 0),
                "picked_up": status_counts.get("picked_up", 0),
                "on_the_way": status_counts.get("on_the_way", 0),
                "active_total": active_orders.count(),
            },
            "delivery": {
                "searching": assignment_counts.get("searching", 0) + assignment_counts.get("notified", 0),
                "assigned": assignment_counts.get("accepted", 0),
                "timed_out": assignment_counts.get("timed_out", 0),
            },
            "alerts": {
                "low_stock": low_stock.count(),
                "product_attention": Product.objects.filter(vendor=vendor).filter(
                    Q(stock__lte=0) | Q(is_available=False)
                ).count(),
                "pending_payouts": VendorPayout.objects.filter(
                    vendor=vendor,
                    status__in=["pending_approval", "paid"],
                ).count(),
                "support_open": SupportTicket.objects.filter(
                    vendor=vendor,
                    status__in=["open", "in_progress"],
                ).count(),
                "unread_notifications": Notification.objects.filter(user=vendor.user, is_read=False).count(),
            },
            "updated_at": timezone.now(),
        }


class VendorLiveOrdersAction(BaseAction):
    def execute(self, vendor):
        return Order.objects.filter(
            vendor=vendor,
            placed_at__gte=timezone.now() - timedelta(days=14),
        ).select_related("customer", "vendor", "delivery_address", "delivery_partner").prefetch_related(
            "items", "tracking"
        ).order_by("-placed_at")
