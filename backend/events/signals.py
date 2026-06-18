from django.dispatch import Signal

# --- Order Events ---
# Fired when a customer successfully places an order.
# Providing arguments: sender, order
order_placed = Signal()

# Fired when an order is cancelled by the customer or admin.
# Providing arguments: sender, order
order_cancelled = Signal()

# Fired when an order status is updated.
# Providing arguments: sender, order, new_status, old_status
order_status_updated = Signal()

# --- Vendor Events ---
# Fired when an admin approves a vendor's application.
# Providing arguments: sender, vendor
vendor_approved = Signal()

# Fired when an admin rejects a vendor's application.
# Providing arguments: sender, vendor
vendor_rejected = Signal()

# --- Customer / Payment Events ---
# Fired when a cart is populated / checkout begins (maybe used later)
checkout_started = Signal()

# --- Support Events ---
# Fired when a new support issue is created.
# Providing arguments: sender, issue
issue_created = Signal()
issue_updated = Signal()
issue_message_added = Signal()  # For websockets

# ── Support/Tickets ───────────────────────────────────────────────────────────
support_ticket_created = Signal()
support_ticket_updated = Signal()
