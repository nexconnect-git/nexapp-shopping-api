from django.db.models import Q

from orders.models import DeliveryZone, FeatureFlag, RefundLedger, TaxRule
from vendors.data.base import BaseRepository


class RefundLedgerRepository(BaseRepository):
    def __init__(self):
        super().__init__(RefundLedger)

    @staticmethod
    def list(status_filter=None, method=None, order_id=None, search=None):
        queryset = RefundLedger.objects.select_related(
            'order',
            'issue',
            'customer',
            'requested_by',
            'approved_by',
            'processed_by',
        )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if method:
            queryset = queryset.filter(method=method)
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        if search:
            queryset = queryset.filter(
                Q(order__order_number__icontains=search)
                | Q(customer__username__icontains=search)
                | Q(gateway_refund_id__icontains=search)
            )
        return queryset.order_by('-created_at')


class DeliveryZoneRepository(BaseRepository):
    def __init__(self):
        super().__init__(DeliveryZone)

    @staticmethod
    def list(city=None, is_active=None, search=None):
        queryset = DeliveryZone.objects.all()
        if city:
            queryset = queryset.filter(city__iexact=city)
        if is_active in ('0', '1'):
            queryset = queryset.filter(is_active=is_active == '1')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(city__icontains=search))
        return queryset.order_by('city', 'name')


class TaxRuleRepository(BaseRepository):
    def __init__(self):
        super().__init__(TaxRule)

    @staticmethod
    def list(country=None, applies_to=None, is_active=None):
        queryset = TaxRule.objects.all()
        if country:
            queryset = queryset.filter(country__iexact=country)
        if applies_to:
            queryset = queryset.filter(applies_to=applies_to)
        if is_active in ('0', '1'):
            queryset = queryset.filter(is_active=is_active == '1')
        return queryset.order_by('country', 'region', 'name')


class FeatureFlagRepository(BaseRepository):
    def __init__(self):
        super().__init__(FeatureFlag)

    @staticmethod
    def list(audience=None, is_enabled=None, search=None):
        queryset = FeatureFlag.objects.select_related('updated_by')
        if audience:
            queryset = queryset.filter(audience=audience)
        if is_enabled in ('0', '1'):
            queryset = queryset.filter(is_enabled=is_enabled == '1')
        if search:
            queryset = queryset.filter(Q(key__icontains=search) | Q(name__icontains=search))
        return queryset.order_by('key')
