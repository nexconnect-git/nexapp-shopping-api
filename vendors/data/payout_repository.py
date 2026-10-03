from rest_framework.exceptions import NotFound
from accounts.models import User

from vendors.data.base import BaseRepository
from vendors.models import DeliveryPartnerPayout, Vendor, VendorPayout


class PayoutRepository(BaseRepository):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(VendorPayout if kind == 'vendor' else DeliveryPartnerPayout)

    def detail(self, payout_id):
        relation = 'vendor' if self.kind == 'vendor' else 'delivery_partner'
        payout = self.model.objects.select_related(relation).filter(pk=payout_id).first()
        if payout is None:
            raise NotFound('Payout not found.')
        return payout

    def locked(self, payout_id):
        payout = self.model.objects.select_for_update().filter(pk=payout_id).first()
        if payout is None:
            raise NotFound('Payout not found.')
        return payout

    def lock_recipient(self, recipient):
        model = Vendor if self.kind == 'vendor' else User
        return model.objects.select_for_update().get(pk=recipient.pk)

    def overlaps(self, recipient, start, end):
        field = 'vendor' if self.kind == 'vendor' else 'delivery_partner'
        return self.model.objects.filter(**{field: recipient}, period_start__lte=end, period_end__gte=start).exclude(status='failed').exists()

    def recipient_user_id(self, payout):
        if self.kind == 'delivery':
            return payout.delivery_partner_id
        return Vendor.objects.filter(pk=payout.vendor_id).values_list('user_id', flat=True).get()
