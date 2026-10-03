from accounts.admin_access import allows


def user_can_access_invoice(user, invoice) -> bool:
    if getattr(user, 'role', '') == 'admin':
        return allows(user, 'finance.view')
    if invoice.recipient == user:
        return True
    if invoice.vendor and hasattr(user, 'vendor_profile') and invoice.vendor == user.vendor_profile:
        return True
    if invoice.order and invoice.order.customer == user:
        return True
    return bool(
        invoice.order
        and hasattr(user, 'vendor_profile')
        and invoice.order.vendor == user.vendor_profile
    )
