def normalize_order_status(status: str) -> str:
    return {
        "placed": "created",
        "confirmed": "confirmed",
        "preparing": "preparing",
        "ready": "ready_for_pickup",
        "picked_up": "picked_up",
        "on_the_way": "out_for_delivery",
        "delivered": "delivered",
        "cancelled": "cancelled",
    }.get(status, status or "created")


def normalize_assignment_status(status: str) -> str:
    return {
        "searching": "assigned",
        "notified": "assigned",
        "accepted": "accepted",
        "timed_out": "timed_out",
        "failed": "failed",
        "cancelled": "cancelled",
    }.get(status, status or "assigned")


def normalize_payment_status(order) -> str:
    if order.refund_status == "processed":
        return "refunded"
    if order.refund_status == "initiated":
        return "refund_initiated"
    if order.refund_status == "failed":
        return "failed"
    if order.is_payment_verified or order.total == 0:
        return "success"
    if order.status == "cancelled":
        return "failed"
    return "pending"


def normalize_order_delivery_status(order, assignment_status: str | None = None) -> str | None:
    if order.status == "ready":
        return "accepted" if assignment_status == "accepted" else "available"
    if order.status == "picked_up":
        return "picked_up"
    if order.status == "on_the_way":
        return "on_the_way"
    if order.status == "delivered":
        return "delivered"
    if order.status == "cancelled":
        return "cancelled"
    if assignment_status:
        return normalize_assignment_status(assignment_status)
    return None
