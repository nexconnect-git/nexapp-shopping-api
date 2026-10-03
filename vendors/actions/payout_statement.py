import io

from django.template.loader import render_to_string
from rest_framework.exceptions import APIException, NotFound
from xhtml2pdf import pisa

from vendors.data.payout_repository import PayoutRepository


class GeneratePayoutStatementAction:
    def execute(self, kind, payout_id):
        payout = PayoutRepository(kind).detail(payout_id)
        recipient = payout.vendor.store_name if kind == 'vendor' else payout.delivery_partner.get_full_name() or payout.delivery_partner.username
        html = render_to_string('invoices/payout_statement.html', {
            'payout': payout, 'recipient': recipient, 'kind': kind,
            'amount': payout.net_payout if kind == 'vendor' else payout.total_earnings,
        })
        output = io.BytesIO()
        if pisa.CreatePDF(io.StringIO(html), dest=output).err:
            raise APIException('The settlement statement could not be rendered. Please retry.')
        output.seek(0)
        return output


class GenerateVendorPayoutStatementAction:
    def execute(self, vendor, payout_id):
        payout = PayoutRepository('vendor').detail(payout_id)
        if payout.vendor_id != vendor.pk:
            raise NotFound('Settlement not found.')
        return GeneratePayoutStatementAction().execute('vendor', payout_id)
