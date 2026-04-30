from datetime import timedelta
from django.db.models import Avg, Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from orders.models import CouponUsage, Order, OrderItem
from products.models import Product
from vendors.actions.base import BaseAction
from vendors.models import VendorPayout


class VendorAnalyticsAction(BaseAction):
    def execute(self, vendor, days="30"):
        orders = Order.objects.filter(vendor=vendor)
        period_label = "All time"
        if days and days != "all":
            try:
                days_int = int(days)
            except (TypeError, ValueError):
                days_int = 30
            start = timezone.now() - timedelta(days=days_int)
            orders = orders.filter(placed_at__gte=start)
            period_label = f"Last {days_int} days"

        delivered = orders.filter(status="delivered")
        order_count = orders.count()
        delivered_count = delivered.count()
        total_revenue = delivered.aggregate(
            total=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )["total"]
        average_order_value = delivered.aggregate(
            avg=Coalesce(Avg("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )["avg"]
        repeat_customers = (
            orders.values("customer")
            .annotate(order_count=Count("id"))
            .filter(order_count__gt=1)
            .count()
        )

        top_products = (
            OrderItem.objects.filter(order__in=delivered, product__vendor=vendor)
            .values("product_id", "product_name")
            .annotate(
                total_sold=Coalesce(Sum("quantity"), Value(0)),
                revenue=Coalesce(Sum("subtotal"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
            .order_by("-revenue")[:10]
        )

        monthly_data = (
            delivered.annotate(month=TruncMonth("placed_at"))
            .values("month")
            .annotate(
                revenue=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
                orders=Count("id"),
            )
            .order_by("month")
        )

        coupon_usages = CouponUsage.objects.filter(coupon__vendor=vendor, order__in=delivered)
        coupon_contribution = coupon_usages.aggregate(
            usage_count=Count("id"),
            discount=Coalesce(Sum("discount_applied"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            revenue=Coalesce(Sum("order__total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        )

        payout_summary = (
            VendorPayout.objects.filter(vendor=vendor)
            .values("status")
            .annotate(
                count=Count("id"),
                amount=Coalesce(Sum("net_payout"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
            .order_by("status")
        )

        low_stock_count = Product.objects.filter(
            vendor=vendor,
            low_stock_threshold__gt=0,
            stock__lte=F("low_stock_threshold"),
        ).count()

        return {
            "period_label": period_label,
            "total_revenue": total_revenue,
            "total_orders": order_count,
            "delivered_orders": delivered_count,
            "average_order_value": average_order_value,
            "repeat_customers": repeat_customers,
            "top_products": [
                {
                    "product_id": row["product_id"],
                    "name": row["product_name"],
                    "total_sold": row["total_sold"],
                    "revenue": row["revenue"],
                }
                for row in top_products
            ],
            "monthly_data": list(monthly_data),
            "payout_summary": list(payout_summary),
            "coupon_contribution": coupon_contribution,
            "low_stock_impact": {
                "low_stock_count": low_stock_count,
            },
        }
