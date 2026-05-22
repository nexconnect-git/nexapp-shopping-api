from django.db.models import F, Q
from django.utils import timezone
from orders.models import Coupon, CouponUsage


class CouponRepository:

    @staticmethod
    def get_active_coupon(code):
        return Coupon.objects.get(code=code, is_active=True)

    @staticmethod
    def get_valid_customer_coupons(discount_type=None):
        now = timezone.now()
        qs = (
            Coupon.objects.filter(is_active=True, valid_from__lte=now)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
            .filter(Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit")))
        )
        if discount_type:
            qs = qs.filter(discount_type=discount_type)
        return qs.order_by("display_order", "-created_at")

    @staticmethod
    def get_customer_coupon_summary():
        qs = CouponRepository.get_valid_customer_coupons()
        return {
            "all": qs.count(),
            "free_delivery": qs.filter(discount_type="free_delivery").count(),
            "percentage": qs.filter(discount_type="percentage").count(),
            "fixed": qs.filter(discount_type="fixed").count(),
        }

    @staticmethod
    def get_all_admin():
        return Coupon.objects.select_related("vendor").order_by("display_order", "-created_at")

    @staticmethod
    def get_user_usage_count(coupon, user):
        return CouponUsage.objects.filter(coupon=coupon, user=user).count()
