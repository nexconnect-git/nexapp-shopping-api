from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from vendors.data.finance_repository import VendorCouponRepository


class VendorCouponAction:
    @transaction.atomic
    def execute(self, vendor, user, command, coupon_id=None, values=None):
        repo = VendorCouponRepository()
        values = dict(values or {})
        if command == 'create':
            return repo.create(**values, vendor=vendor, created_by=user)
        coupon = repo.locked(vendor, coupon_id)
        if coupon is None:
            raise NotFound('Coupon not found.')
        if command == 'delete':
            repo.delete(coupon)
            return None
        if command == 'update':
            return repo.update(coupon, values)
        if command == 'reactivate':
            if coupon.valid_until and coupon.valid_until <= timezone.now():
                raise ValidationError({'valid_until': 'Choose a new end date before activating an expired coupon.'})
            if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                raise ValidationError({'usage_limit': 'Usage limit has been reached. Edit the limit before activating.'})
            return repo.update(coupon, {'is_active': True})
        if command == 'duplicate':
            base = coupon.code[:39] + '-COPY'
            code, index = base, 2
            while repo.code_exists(code):
                code = base + '-' + str(index)
                index += 1
            fields = ('description', 'discount_type', 'discount_value', 'min_order_amount', 'max_discount_amount', 'usage_limit', 'per_user_limit', 'valid_from', 'valid_until', 'display_section', 'badge_text', 'icon_name', 'accent_color', 'display_order')
            return repo.create(**{key: getattr(coupon, key) for key in fields}, vendor=vendor, created_by=user, code=code, title=(coupon.title + ' Copy')[:200], is_active=False)
        raise ValidationError('Unsupported coupon command.')
