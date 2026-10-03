from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime, time, timedelta

from vendors.data.finance_recipient_repository import FinanceRecipientRepository
from vendors.data.vendor_repo import VendorRepository
from vendors.serializers.onboarding import VendorBankDetailsSerializer


class GetFinanceRecipientsAction:
    def execute(self):
        return FinanceRecipientRepository().recipients()


class GetVendorBankSummaryAction:
    def execute(self, vendor_id):
        if not VendorRepository().get_by_id(vendor_id):
            raise NotFound('Vendor not found.')
        bank = FinanceRecipientRepository().bank(vendor_id)
        if bank is None:
            return {'configured': False, 'commission_percentage': '0.00', 'masked_account': '', 'settlement_cycle': ''}
        return {**VendorBankDetailsSerializer(bank).data, 'configured': bool(bank.account_number_enc or bank.upi_id)}


class GetPayoutEstimateAction:
    def execute(self, kind, recipient_id, query):
        try:
            start, end = parse_date(query.get('start_date', '')), parse_date(query.get('end_date', ''))
        except (TypeError, ValueError):
            start = end = None
        if not start or not end or start > end:
            raise ValidationError('Supply a valid start_date and end_date (YYYY-MM-DD).')
        recipient = FinanceRecipientRepository().recipient(kind, recipient_id)
        if not recipient:
            raise NotFound('Recipient not found.')
        lower = timezone.make_aware(datetime.combine(start, time.min))
        upper = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
        return FinanceRecipientRepository().estimate(kind, recipient, lower, upper)
