"""
Scheduled background tasks for admin-triggered jobs.
Each function is decorated with @job('default') to run via RQ.
"""
import logging
from datetime import date, timedelta
from django_rq import job

logger = logging.getLogger(__name__)


@job('default')
def generate_vendor_payouts(payout_id: str):
    """
    Legacy task — now only used for direct status override testing.
    New flow uses the approval/verification lifecycle instead.
    """
    from vendors.models import VendorPayout
    from django.utils import timezone

    try:
        payout = VendorPayout.objects.get(id=payout_id)
        if payout.status not in ('paid', 'verified'):
            payout.status = 'paid'
            payout.paid_at = timezone.now()
            payout.save(update_fields=['status', 'paid_at'])
            logger.info(f"[generate_vendor_payouts] Processed payout {payout_id}")
        else:
            logger.info(f"[generate_vendor_payouts] Payout {payout_id} already finalised.")
    except VendorPayout.DoesNotExist:
        logger.error(f"[generate_vendor_payouts] Payout {payout_id} not found.")
        raise
    except Exception as e:
        logger.error(f"[generate_vendor_payouts] Error: {e}")
        raise


@job('default')
def generate_delivery_payouts(payout_id: str):
    """
    Legacy task — now only used for direct status override testing.
    """
    from vendors.models import DeliveryPartnerPayout
    from django.utils import timezone

    try:
        payout = DeliveryPartnerPayout.objects.get(id=payout_id)
        if payout.status not in ('paid', 'verified'):
            payout.status = 'paid'
            payout.paid_at = timezone.now()
            payout.save(update_fields=['status', 'paid_at'])
            logger.info(f"[generate_delivery_payouts] Processed payout {payout_id}")
        else:
            logger.info(f"[generate_delivery_payouts] Payout {payout_id} already finalised.")
    except DeliveryPartnerPayout.DoesNotExist:
        logger.error(f"[generate_delivery_payouts] Payout {payout_id} not found.")
        raise
    except Exception as e:
        logger.error(f"[generate_delivery_payouts] Error: {e}")
        raise


@job('default')
def remind_unverified_payouts():
    """
    Run every 12h. Sends:
      - 24h reminder to vendor/partner who hasn't verified credit
      - 48h notification to admins that the force-paid override is now unlocked
    """
    from vendors.models import VendorPayout, DeliveryPartnerPayout
    from notifications.models import Notification
    from accounts.models import User
    from django.utils import timezone

    now = timezone.now()
    threshold_24h = now - timedelta(hours=24)
    threshold_48h = now - timedelta(hours=48)

    admin_users = list(User.objects.filter(role='admin', is_active=True))

    # ── Vendor payouts ────────────────────────────────────────────────────────

    # 24h — remind vendor
    for payout in VendorPayout.objects.filter(
        status='pending_verify',
        payment_sent_at__lte=threshold_24h,
        payment_sent_at__gt=threshold_48h,
    ).select_related('vendor__user'):
        Notification.objects.get_or_create(
            user=payout.vendor.user,
            title='Reminder: Verify Your Payout Credit',
            defaults={
                'message': (
                    f'Your payout of ₹{payout.net_payout} was transferred 24 hours ago. '
                    f'Please verify that you received the credit before the 2-day window expires.'
                ),
                'notification_type': 'payout',
                'data': {'payout_id': str(payout.id), 'action': 'reminder_24h'},
            },
        )
        logger.info(f"[remind_unverified_payouts] 24h reminder sent to vendor {payout.vendor_id} for payout {payout.id}")

    # 48h — notify admins override is unlocked
    for payout in VendorPayout.objects.filter(
        status='pending_verify',
        payment_sent_at__lte=threshold_48h,
    ).select_related('vendor'):
        admin_notifications = [
            Notification(
                user=admin,
                title='Payout Override Unlocked',
                message=(
                    f'Vendor "{payout.vendor.store_name}" has not verified payout ₹{payout.net_payout} '
                    f'within 2 days. You can now force-mark it as paid.'
                ),
                notification_type='payout',
                data={'payout_id': str(payout.id), 'action': 'override_unlocked'},
            )
            for admin in admin_users
        ]
        if admin_notifications:
            Notification.objects.bulk_create(admin_notifications, ignore_conflicts=True)
        logger.info(f"[remind_unverified_payouts] 48h override unlocked for vendor payout {payout.id}")

    # ── Delivery partner payouts ───────────────────────────────────────────────

    for payout in DeliveryPartnerPayout.objects.filter(
        status='pending_verify',
        payment_sent_at__lte=threshold_24h,
        payment_sent_at__gt=threshold_48h,
    ).select_related('delivery_partner'):
        Notification.objects.get_or_create(
            user=payout.delivery_partner,
            title='Reminder: Verify Your Payout Credit',
            defaults={
                'message': (
                    f'Your payout of ₹{payout.total_earnings} was transferred 24 hours ago. '
                    f'Please verify receipt before the 2-day window expires.'
                ),
                'notification_type': 'payout',
                'data': {'payout_id': str(payout.id), 'action': 'reminder_24h'},
            },
        )

    for payout in DeliveryPartnerPayout.objects.filter(
        status='pending_verify',
        payment_sent_at__lte=threshold_48h,
    ).select_related('delivery_partner'):
        partner_name = payout.delivery_partner.get_full_name() or payout.delivery_partner.username
        admin_notifications = [
            Notification(
                user=admin,
                title='Delivery Payout Override Unlocked',
                message=(
                    f'{partner_name} has not verified payout ₹{payout.total_earnings} within 2 days. '
                    f'You can now force-mark it as paid.'
                ),
                notification_type='payout',
                data={'payout_id': str(payout.id), 'action': 'override_unlocked'},
            )
            for admin in admin_users
        ]
        if admin_notifications:
            Notification.objects.bulk_create(admin_notifications, ignore_conflicts=True)


@job('default')
def generate_platform_report():
    """
    Generate and log a snapshot of platform statistics.
    """
    from accounts.models import User
    from orders.models import Order
    from vendors.models import Vendor
    from django.db.models import Sum, Count

    try:
        stats = {
            'total_orders': Order.objects.count(),
            'delivered_orders': Order.objects.filter(status='delivered').count(),
            'total_revenue': str(Order.objects.filter(status='delivered').aggregate(s=Sum('total'))['s'] or 0),
            'total_vendors': Vendor.objects.count(),
            'total_users': User.objects.count(),
            'generated_at': date.today().isoformat(),
        }
        logger.info(f"[generate_platform_report] Stats snapshot: {stats}")
        return stats
    except Exception as e:
        logger.error(f"[generate_platform_report] Error: {e}")
        raise


@job('default')
def send_bulk_notification(title: str, message: str, target: str = 'all'):
    """
    Send a notification to all users matching 'target' (all / vendors / customers / delivery).
    """
    from accounts.models import User
    from notifications.models import Notification

    try:
        qs = User.objects.filter(is_active=True)
        if target == 'vendors':
            qs = qs.filter(role='vendor')
        elif target == 'customers':
            qs = qs.filter(role='customer')
        elif target == 'delivery':
            qs = qs.filter(role='delivery')

        notifications = [
            Notification(user=u, title=title, message=message, notification_type='system')
            for u in qs
        ]
        Notification.objects.bulk_create(notifications, batch_size=500)
        logger.info(f"[send_bulk_notification] Sent '{title}' to {len(notifications)} users (target={target})")
    except Exception as e:
        logger.error(f"[send_bulk_notification] Error: {e}")
        raise
