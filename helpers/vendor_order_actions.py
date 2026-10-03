def vendor_order_actions(order, assignment_status=None):
    """Commands supported by the current vendor-owned order snapshot."""
    commands = {
        'placed': ['accept', 'reject'],
        'confirmed': ['start_preparing'],
        'preparing': ['mark_ready'],
    }.get(order.status, []).copy()
    if order.status in ('placed', 'confirmed', 'preparing', 'ready'):
        commands.append('cancel_order')
    if order.status == 'ready':
        if order.delivery_partner_id:
            commands.append('verify_pickup_otp')
        elif assignment_status in ('searching', 'notified'):
            commands.append('cancel_delivery_search')
        elif assignment_status != 'accepted':
            commands.append('start_delivery_search')
    return commands
