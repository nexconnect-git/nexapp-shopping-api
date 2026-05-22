from decimal import Decimal


def _money(value) -> str:
    try:
        return f"Rs.{Decimal(str(value or 0)).quantize(Decimal('0.01'))}"
    except Exception:
        return "Rs.0.00"


def _line_items(items) -> str:
    lines = []
    for item in items or []:
        name = item.get("name") or item.get("product_name") or "Item"
        quantity = item.get("quantity") or 1
        total = item.get("subtotal") or item.get("total") or 0
        lines.append(f"- {quantity} x {name}: {_money(total)}")
    return "\n".join(lines) or "- Order items will appear in your order details."


def render_customer_email(template_type: str, payload: dict) -> tuple[str, str]:
    brand = payload.get("brand_name") or "NexConnect"
    customer_name = payload.get("customer_name") or "Customer"
    support = payload.get("support_contact") or "support@nex-connect.in"

    if template_type == "otp_login":
        return (
            f"{brand} login OTP",
            (
                f"Hi {customer_name},\n\n"
                f"Your {brand} login OTP is {payload.get('otp')}.\n"
                f"It expires in {payload.get('expiry_minutes', 10)} minutes.\n\n"
                "If you did not request this, please ignore this email."
            ),
        )
    if template_type == "welcome_customer":
        return (
            f"Welcome to {brand}",
            (
                f"Hi {customer_name},\n\n"
                f"Welcome to {brand}. Your customer account is ready.\n\n"
                f"For help, contact {support}."
            ),
        )
    if template_type == "order_placed":
        return (
            f"Order {payload.get('order_number', '')} placed",
            (
                f"Hi {customer_name},\n\n"
                f"Your order {payload.get('order_number')} has been placed with {payload.get('store_name', 'the store')}.\n\n"
                f"{_line_items(payload.get('items'))}\n\n"
                f"Total: {_money(payload.get('total'))}\n"
                f"Delivery address: {payload.get('delivery_address', 'Selected delivery address')}\n\n"
                f"For help, contact {support}."
            ),
        )
    if template_type == "invoice":
        return (
            f"Invoice for order {payload.get('order_number', '')}",
            (
                f"Hi {customer_name},\n\n"
                f"Invoice number: {payload.get('invoice_number', 'Pending')}\n"
                f"Order: {payload.get('order_number')}\n"
                f"Total paid: {_money(payload.get('total'))}\n\n"
                f"{_line_items(payload.get('items'))}"
            ),
        )
    if template_type == "tax_invoice":
        return (
            f"Tax invoice for order {payload.get('order_number', '')}",
            (
                f"Hi {customer_name},\n\n"
                f"Tax invoice number: {payload.get('invoice_number', 'Pending')}\n"
                f"Tax amount: {_money(payload.get('tax_amount'))}\n"
                f"Total paid: {_money(payload.get('total'))}\n\n"
                f"{_line_items(payload.get('items'))}"
            ),
        )

    subject_map = {
        "order_cancelled": "Order cancelled",
        "refund_initiated": "Refund initiated",
        "refund_completed": "Refund completed",
        "payment_failed": "Payment failed",
        "account_suspended": "Account suspended",
    }
    return (
        f"{brand}: {subject_map.get(template_type, 'Account update')}",
        (
            f"Hi {customer_name},\n\n"
            f"{payload.get('message', subject_map.get(template_type, 'There is an update on your account.'))}\n\n"
            f"For help, contact {support}."
        ),
    )
