TASK_REGISTRY = {
    'generate_vendor_payouts': {
        'label': 'Process Vendor Payout',
        'description': 'Process a pending vendor payout record.',
        'func': 'notifications.scheduled_tasks.generate_vendor_payouts',
        'params': ['payout_id'],
        'icon': 'storefront',
        'category': 'payouts',
    },
    'generate_delivery_payouts': {
        'label': 'Process Delivery Payout',
        'description': 'Process a pending delivery partner payout.',
        'func': 'notifications.scheduled_tasks.generate_delivery_payouts',
        'params': ['payout_id'],
        'icon': 'two_wheeler',
        'category': 'payouts',
    },
    'generate_platform_report': {
        'label': 'Platform Sales Report',
        'description': 'Generate a platform-wide sales and orders statistics snapshot.',
        'func': 'notifications.scheduled_tasks.generate_platform_report',
        'params': [],
        'icon': 'bar_chart',
        'category': 'reports',
    },
    'send_bulk_notification': {
        'label': 'Send Bulk Notification',
        'description': 'Broadcast a notification to all users or a specific role group.',
        'func': 'notifications.scheduled_tasks.send_bulk_notification',
        'params': ['title', 'message', 'target'],
        'icon': 'campaign',
        'category': 'notifications',
    },
    'enforce_vendor_closing_times': {
        'label': 'Enforce Vendor Closing Times',
        'description': 'Warn vendors before closing and auto-close stores that pass their configured closing time.',
        'func': 'notifications.scheduled_tasks.enforce_vendor_closing_times',
        'params': ['warning_minutes'],
        'icon': 'schedule',
        'category': 'operations',
    },
    'release_due_scheduled_orders': {
        'label': 'Release Due Scheduled Orders',
        'description': 'Notify vendors when scheduled orders enter their preparation window.',
        'func': 'notifications.scheduled_tasks.release_due_scheduled_orders',
        'params': [],
        'icon': 'event_available',
        'category': 'operations',
    },
    'reconcile_inventory_reservations': {
        'label': 'Reconcile Inventory Reservations',
        'description': 'Expire stale reservations and release stock for failed payment flows.',
        'func': 'notifications.scheduled_tasks.reconcile_inventory_reservations',
        'params': ['failed_payment_age_minutes'],
        'icon': 'inventory',
        'category': 'operations',
    },
    'refresh_customer_recommendations': {
        'label': 'Refresh Customer Recommendations',
        'description': 'Precompute product, deal, and store recommendations for customer-app home and discovery.',
        'func': 'orders.scheduled_tasks.refresh_customer_recommendations',
        'params': ['user_id', 'limit'],
        'icon': 'auto_awesome',
        'category': 'recommendations',
    },
}


def serialize_job(job, scheduled_time=None):
    func_name = ''
    task_key = ''
    try:
        func_name = job.func_name
        for key, meta in TASK_REGISTRY.items():
            if meta['func'] in func_name or key in func_name:
                task_key = key
                break
    except Exception:
        pass

    meta = TASK_REGISTRY.get(task_key, {})
    status_value = job.get_status()
    status_str = getattr(status_value, 'value', status_value) if status_value else 'scheduled'

    return {
        'id': job.id,
        'task_key': task_key,
        'label': meta.get('label', func_name),
        'icon': meta.get('icon', 'schedule'),
        'category': meta.get('category', 'other'),
        'args': list(job.args or []),
        'kwargs': dict(job.kwargs or {}),
        'scheduled_at': scheduled_time.isoformat() if scheduled_time else None,
        'enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
        'status': status_str,
        'description': meta.get('description', ''),
    }


def task_definitions():
    return [
        {
            'key': key,
            'label': meta['label'],
            'description': meta['description'],
            'icon': meta['icon'],
            'category': meta['category'],
            'params': meta['params'],
        }
        for key, meta in TASK_REGISTRY.items()
    ]
