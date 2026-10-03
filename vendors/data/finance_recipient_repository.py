from accounts.models import User
from vendors.data.base import BaseRepository
from vendors.models import Vendor, VendorBankDetails
from orders.models import Order
from delivery.models import DeliveryEarning, DeliveryPartner
from django.db.models import Sum, Count, Q


class FinanceRecipientRepository(BaseRepository):
    def __init__(self):
        super().__init__(VendorBankDetails)

    def bank(self, vendor_id):
        return self.model.objects.filter(vendor_id=vendor_id).first()

    def recipient(self, kind, recipient_id):
        return (Vendor if kind == 'vendor' else DeliveryPartner).objects.filter(pk=recipient_id).first()

    def estimate(self, kind, recipient, start, end):
        if kind == 'vendor':
            eligible = Q(status='delivered', is_payment_verified=True)
            values = Order.objects.filter(vendor=recipient, placed_at__gte=start, placed_at__lt=end).aggregate(total=Sum('total', filter=eligible), count=Count('pk'), eligible=Count('pk', filter=eligible), delivered=Count('pk', filter=Q(status='delivered')), cancelled=Count('pk', filter=Q(status='cancelled')))
            total = float(values['total'] or 0)
            return {'total_revenue': total, 'total_orders': values['count'], 'delivered_orders': values['delivered'], 'cancelled_orders': values['cancelled'], 'average_order_value': total / values['eligible'] if values['eligible'] else 0}
        values = DeliveryEarning.objects.filter(delivery_partner=recipient, created_at__gte=start, created_at__lt=end, order__status='delivered').aggregate(total=Sum('amount'), count=Count('pk'))
        return {'total_amount': float(values['total'] or 0), 'total_deliveries': values['count']}

    def recipients(self):
        vendors = Vendor.objects.select_related('bank_details').order_by('store_name')
        partners = User.objects.filter(role='delivery', is_active=True, delivery_profile__is_approved=True).select_related('delivery_profile').order_by('first_name', 'username')
        return {
            'vendors': [{'id': str(vendor.pk), 'store_name': vendor.store_name, 'city': vendor.city, 'state': vendor.state} for vendor in vendors],
            'delivery': [{'id': str(user.delivery_profile.pk), 'user': {'id': str(user.pk), 'first_name': user.first_name, 'last_name': user.last_name, 'username': user.username}, 'is_approved': True} for user in partners],
        }
