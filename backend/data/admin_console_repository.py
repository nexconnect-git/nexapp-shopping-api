from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound

from accounts.models import AdminAuditLog, AdminPermissionGrant, User
from delivery.models import Asset, DeliveryPartner
from orders.models import Order, OrderIssue, PaymentSession, RefundLedger, PlatformSetting
from products.models import Product
from vendors.models import DeliveryPartnerPayout, Vendor, VendorPayout, VendorDocument, VendorAuditLog
from vendors.data.base import BaseRepository


class AdminConsoleRepository(BaseRepository):
    def __init__(self):
        super().__init__(Order)

    @staticmethod
    def orders():
        return Order.objects.select_related('customer', 'vendor__user', 'delivery_partner__delivery_profile', 'delivery_address', 'assignment').prefetch_related('items', 'tracking', 'invoices', 'rating').order_by('-placed_at')

    @staticmethod
    def locked_order(pk):
        try:
            return Order.objects.select_for_update(of=('self',)).select_related('vendor', 'customer', 'delivery_partner').get(pk=pk)
        except Order.DoesNotExist as exc:
            raise NotFound('Order not found.') from exc

    @staticmethod
    def partners():
        return DeliveryPartner.objects.select_related('user').filter(user__is_active=True, is_approved=True).annotate(
            workload=Count('user__deliveries', filter=Q(user__deliveries__status__in=['ready', 'picked_up', 'on_the_way'])),
        ).order_by('user__username')

    @staticmethod
    def filtered_orders(params, payments=False):
        qs = AdminConsoleRepository.orders()
        if params.get('order'):
            qs = qs.filter(pk=params['order'])
        for field, key in [('status', 'status'), ('vendor_id', 'vendor'), ('customer_id', 'customer'), ('payment_method', 'method'), ('refund_status', 'refund_status')]:
            if params.get(key):
                qs = qs.filter(**{field: params[key]})
        if params.get('delivery_partner'):
            partner = DeliveryPartner.objects.filter(pk=params['delivery_partner']).first()
            qs = qs.filter(delivery_partner_id=partner.user_id if partner else params['delivery_partner'])
        query = params.get('search', '').strip()
        if query:
            qs = qs.filter(Q(order_number__icontains=query) | Q(customer__username__icontains=query) | Q(customer__email__icontains=query) | Q(vendor__store_name__icontains=query) | Q(razorpay_payment_id__icontains=query))
        for key, field in [('date_from', 'placed_at__date__gte'), ('date_to', 'placed_at__date__lte'), ('amount_min', 'total__gte'), ('amount_max', 'total__lte')]:
            if params.get(key) is not None:
                qs = qs.filter(**{field: params[key]})
        if params.get('verified') in ('0', '1'):
            qs = qs.filter(is_payment_verified=params['verified'] == '1')
        if params.get('issue_state') == 'open':
            qs = qs.filter(issues__status__in=['open', 'assigned', 'in_review', 'investigating', 'waiting_customer', 'waiting_vendor', 'waiting_partner', 'escalated', 'resolution_pending']).distinct()
        if params.get('delivery_state') == 'unassigned':
            qs = qs.filter(delivery_partner__isnull=True).exclude(status__in=['delivered', 'cancelled'])
        elif params.get('delivery_state') == 'in_transit':
            qs = qs.filter(status__in=['picked_up', 'on_the_way'])
        if params.get('escalated') == '1':
            qs = qs.filter(dispatch_escalated_at__isnull=False)
        ordering = params.get('ordering', '-placed_at')
        if ordering in ('placed_at', '-placed_at', 'total', '-total', 'status', '-status', 'order_number', '-order_number'):
            qs = qs.order_by(ordering, 'id')
        return qs

    @staticmethod
    def finance_summary(qs=None):
        orders = qs if qs is not None else Order.objects.all()
        confirmed = orders.filter(is_payment_verified=True).exclude(status='cancelled')
        cod = orders.filter(payment_method='cod', is_payment_verified=False).exclude(status='cancelled')
        sums = confirmed.aggregate(amount=Sum('total'))
        return {
            'verified_received': sums['amount'] or Decimal('0'),
            'verified_online': confirmed.filter(payment_method='razorpay').aggregate(amount=Sum('total'))['amount'] or Decimal('0'),
            'pending_online': orders.filter(payment_method='razorpay', is_payment_verified=False).exclude(status='cancelled').count(),
            'unsettled_cod': cod.aggregate(amount=Sum('total'))['amount'] or Decimal('0'),
            'unsettled_cod_count': cod.count(),
            'failed_sessions': PaymentSession.objects.filter(status='failed').count(),
            'refund_requested': RefundLedger.objects.filter(status__in=['requested', 'approved', 'processing']).aggregate(amount=Sum('amount'))['amount'] or Decimal('0'),
            'refund_processed': RefundLedger.objects.filter(status='processed').aggregate(amount=Sum('amount'))['amount'] or Decimal('0'),
            'vendor_payable': VendorPayout.objects.exclude(status__in=['paid', 'verified', 'failed', 'declined', 'cancelled']).aggregate(amount=Sum('net_payout'))['amount'] or Decimal('0'),
            'partner_payable': DeliveryPartnerPayout.objects.exclude(status__in=['paid', 'verified', 'failed', 'declined', 'cancelled']).aggregate(amount=Sum('total_earnings'))['amount'] or Decimal('0'),
            'payout_exceptions': VendorPayout.objects.filter(status__in=['failed', 'declined']).count() + DeliveryPartnerPayout.objects.filter(status__in=['failed', 'declined']).count(),
            'generated_at': timezone.now(),
        }

    @staticmethod
    def reconciliation_exceptions():
        rows = []
        for order in Order.objects.filter(payment_method='razorpay', is_payment_verified=False).exclude(status='cancelled').order_by('-placed_at')[:30]:
            rows.append({'id': str(order.pk), 'type': 'Unverified online payment', 'label': order.order_number, 'amount': order.total, 'route': f'/orders/{order.pk}'})
        for session in PaymentSession.objects.exclude(mismatch_reason='').order_by('-updated_at')[:30]:
            rows.append({'id': str(session.pk), 'type': 'Payment mismatch', 'label': session.gateway_order_id, 'amount': session.amount, 'route': '/payments', 'reason': session.mismatch_reason})
        for payout in VendorPayout.objects.filter(status__in=['failed', 'declined']).select_related('vendor')[:20]:
            rows.append({'id': str(payout.pk), 'type': 'Vendor payout exception', 'label': payout.vendor.store_name, 'amount': payout.net_payout, 'route': '/payouts'})
        for payout in DeliveryPartnerPayout.objects.filter(status__in=['failed', 'declined']).select_related('delivery_partner')[:20]:
            rows.append({'id': str(payout.pk), 'type': 'Partner payout exception', 'label': payout.delivery_partner.username, 'amount': payout.total_earnings, 'route': '/payouts'})
        return rows

    @staticmethod
    def audit(ids):
        return AdminAuditLog.objects.filter(entity_id__in=[str(value) for value in ids]).select_related('actor').order_by('-created_at')

    @staticmethod
    def vendor_audit(vendor_id):
        return VendorAuditLog.objects.filter(vendor_id=vendor_id).select_related('performed_by').order_by('-created_at')

    @staticmethod
    def create_vendor_audit(**data):
        return VendorAuditLog.objects.create(**data)

    @staticmethod
    def vendor_document(vendor_id, document_id):
        document=VendorDocument.objects.select_for_update().select_related('vendor').filter(pk=document_id,vendor_id=vendor_id).first()
        if not document:
            raise NotFound('Document not found.')
        return document

    @staticmethod
    def profile(type_name, pk):
        if type_name == 'vendor':
            entity = Vendor.objects.select_related('user').filter(pk=pk).first()
            user = entity.user if entity else None
            orders = Order.objects.filter(vendor_id=pk)
        elif type_name == 'delivery-partner':
            entity = DeliveryPartner.objects.select_related('user').filter(pk=pk).first()
            user = entity.user if entity else None
            orders = Order.objects.filter(delivery_partner=user) if user else Order.objects.none()
        else:
            user = User.objects.filter(pk=pk, role='customer' if type_name == 'customer' else 'admin').first()
            entity = user
            orders = Order.objects.filter(customer=user) if user else Order.objects.none()
        if not entity:
            raise NotFound('Profile not found.')
        return entity, user, orders

    @staticmethod
    def search(query, domains):
        rows = []
        if 'orders' in domains:
            for item in Order.objects.filter(order_number__icontains=query).order_by('-placed_at')[:5]:
                rows.append({'group': 'Orders', 'label': item.order_number, 'detail': item.status, 'route': f'/orders/{item.pk}'})
        if 'vendors' in domains:
            for item in Vendor.objects.filter(store_name__icontains=query)[:5]:
                rows.append({'group': 'Vendors', 'label': item.store_name, 'detail': item.city, 'route': f'/vendors/{item.pk}'})
        for role, domain, path in [('customer', 'customers', 'customers'), ('delivery', 'dispatch', 'delivery-partners')]:
            if domain not in domains:
                continue
            for user in User.objects.filter(role=role).filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(email__icontains=query)).select_related('delivery_profile')[:5]:
                entity_id = user.delivery_profile.pk if role == 'delivery' and hasattr(user, 'delivery_profile') else user.pk
                rows.append({'group': 'Customers' if role == 'customer' else 'Delivery partners', 'label': user.get_full_name() or user.username, 'detail': user.email, 'route': f'/{path}/{entity_id}'})
        if 'catalog' in domains:
            for item in Product.objects.filter(name__icontains=query)[:5]:
                rows.append({'group': 'Products', 'label': item.name, 'detail': item.sku, 'route': f'/products?search={quote(item.name)}'})
        if 'support' in domains:
            for item in OrderIssue.objects.filter(Q(description__icontains=query) | Q(order__order_number__icontains=query)).select_related('order')[:5]:
                rows.append({'group': 'Issues', 'label': item.order.order_number, 'detail': item.get_status_display(), 'route': f'/issues?issue={item.pk}'})
        return rows

    @staticmethod
    def locked_issue(pk):
        try:
            return OrderIssue.objects.select_for_update(of=('self',)).select_related('order', 'assignee').get(pk=pk)
        except OrderIssue.DoesNotExist as exc:
            raise NotFound('Case not found.') from exc

    @staticmethod
    def admin_exists(pk):
        return User.objects.filter(pk=pk, role='admin', is_active=True).exists()

    @staticmethod
    def assignees():
        return User.objects.filter(role='admin', is_active=True).order_by('username').values('id', 'username', 'first_name', 'last_name')

    @staticmethod
    def related_profile(entity_type, entity, user, orders):
        result = {'issues': OrderIssue.objects.filter(order__in=orders), 'payments': orders, 'documents': []}
        if entity_type == 'vendor':
            result['products'] = Product.objects.filter(vendor=entity)
            result['payouts'] = VendorPayout.objects.filter(vendor=entity)
            result['documents'] = VendorDocument.objects.filter(vendor=entity)
        elif entity_type == 'delivery-partner':
            result['payouts'] = DeliveryPartnerPayout.objects.filter(delivery_partner=user)
            result['assets'] = Asset.objects.filter(assigned_to=entity)
        return result

    @staticmethod
    def database_connected():
        User.objects.exists()
        return True

    @staticmethod
    def locked_administrators(pk):
        administrators = list(User.objects.select_for_update().filter(Q(pk=pk) | Q(role='admin', is_superuser=True, is_active=True)).order_by('id'))
        target = next((user for user in administrators if str(user.pk) == str(pk)), None)
        if not target:
            raise NotFound('Account not found.')
        return target, sum(user.role == 'admin' and user.is_superuser and user.is_active for user in administrators)

    @staticmethod
    def platform_setting(lock=False):
        query = PlatformSetting.objects.select_for_update() if lock else PlatformSetting.objects
        return query.order_by('id').first() or PlatformSetting.objects.create()

    @staticmethod
    def delete(instance):
        instance.delete()

    @staticmethod
    def overview():
        aggregate = Order.objects.aggregate(total_orders=Count('id'), pending_orders=Count('id', filter=Q(status='placed')), awaiting_fulfillment=Count('id', filter=Q(status__in=['confirmed', 'preparing', 'ready'])), orders_delivering=Count('id', filter=Q(status__in=['picked_up', 'on_the_way'])), completed_orders=Count('id', filter=Q(status='delivered')), cancelled_orders=Count('id', filter=Q(status='cancelled')), total_revenue=Sum('total', filter=Q(status='delivered', is_payment_verified=True)))
        aggregate['total_revenue'] = float(aggregate['total_revenue'] or 0)
        aggregate.update({'vendors': Vendor.objects.count(), 'pending_vendors': Vendor.objects.filter(status='pending').count(), 'delivery_partners': DeliveryPartner.objects.count(), 'pending_delivery_partners': DeliveryPartner.objects.filter(is_approved=False).count(), 'products': Product.objects.count(), 'customers': User.objects.filter(role='customer').count(), 'open_issues': OrderIssue.objects.exclude(status__in=['closed', 'resolved', 'rejected']).count()})
        aggregate.update({f'total_{key}': aggregate[key] for key in ['vendors', 'delivery_partners', 'products', 'customers']})
        aggregate.update({'orders': aggregate['total_orders'], 'orders_placed': aggregate['pending_orders'], 'orders_delivered': aggregate['completed_orders'], 'orders_cancelled': aggregate['cancelled_orders'], 'generated_at': timezone.now().isoformat()})
        return aggregate

    @staticmethod
    def save(instance, fields):
        instance.save(update_fields=fields + ['updated_at'])
        return instance
