from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from orders.models import Coupon
from vendors.data.base import BaseRepository
from vendors.models import VendorPayout, VendorWalletTransaction


class VendorFinanceRepository(BaseRepository):
    def __init__(self):
        super().__init__(VendorPayout)

    def payouts(self, vendor, params):
        query = self.filter(vendor=vendor).select_related('vendor')
        if params.get('status'):
            query = query.filter(status=params['status'])
        if params.get('search'):
            query = query.filter(transaction_ref__icontains=params['search'])
        return query.order_by('-period_start', 'id')

    def payout_summary(self, vendor):
        return list(self.filter(vendor=vendor).values('status').annotate(count=Count('id'), amount=Sum('net_payout')).order_by('status'))

    def transactions(self, vendor, params):
        query = VendorWalletTransaction.objects.filter(vendor=vendor)
        if params.get('transaction_type'):
            query = query.filter(transaction_type=params['transaction_type'])
        if params.get('source'):
            query = query.filter(source=params['source'])
        if params.get('search'):
            term = params['search']
            query = query.filter(Q(description__icontains=term) | Q(reference_id__icontains=term))
        return query.order_by('-created_at', 'id')


class VendorCouponRepository(BaseRepository):
    def __init__(self):
        super().__init__(Coupon)

    def for_vendor(self, vendor, params):
        query = self.filter(vendor=vendor)
        now = timezone.now()
        eligible = Q(is_active=True, valid_from__lte=now) & (Q(valid_until__isnull=True) | Q(valid_until__gt=now)) & (Q(usage_limit__isnull=True) | Q(used_count__lt=F('usage_limit')))
        filters = {
            'active': eligible,
            'upcoming': Q(is_active=True, valid_from__gt=now),
            'expired': Q(is_active=True, valid_until__lte=now),
            'inactive': Q(is_active=False),
            'exhausted': Q(is_active=True, valid_from__lte=now, usage_limit__isnull=False, used_count__gte=F('usage_limit')) & (Q(valid_until__isnull=True) | Q(valid_until__gt=now)),
        }
        if params.get('lifecycle') in filters:
            query = query.filter(filters[params['lifecycle']])
        if params.get('search'):
            term = params['search']
            query = query.filter(Q(code__icontains=term) | Q(title__icontains=term) | Q(description__icontains=term))
        return query.order_by('-created_at', 'id')

    def summary(self, vendor):
        return {
            'total': self.filter(vendor=vendor).count(),
            **{key: self.for_vendor(vendor, {'lifecycle': key}).count() for key in ('active', 'upcoming', 'expired', 'inactive', 'exhausted')},
            'uses': self.filter(vendor=vendor).aggregate(total=Sum('used_count'))['total'] or 0,
        }

    def locked(self, vendor, coupon_id):
        return self.filter(vendor=vendor, pk=coupon_id).select_for_update().first()

    def code_exists(self, code):
        return self.filter(code=code).exists()

    def update(self, coupon, values):
        for key, value in values.items():
            setattr(coupon, key, value)
        coupon.save()
        return coupon

    def delete(self, coupon):
        coupon.delete()
