from django.utils import timezone


def get_vendor_availability(vendor, current_dt=None):
    local_dt = timezone.localtime(current_dt or timezone.now())
    current_time = local_dt.time().replace(tzinfo=None)

    if not vendor.is_open:
        return False, "Currently closed"

    if hasattr(vendor, "is_accepting_orders") and not vendor.is_accepting_orders:
        return False, "Temporarily not accepting orders"

    opening_time = getattr(vendor, "opening_time", None)
    closing_time = getattr(vendor, "closing_time", None)
    if not opening_time or not closing_time:
        return True, "Open now"

    if opening_time == closing_time:
        return True, "Open now"

    if opening_time < closing_time:
        is_within_hours = opening_time <= current_time <= closing_time
    else:
        is_within_hours = current_time >= opening_time or current_time <= closing_time

    if is_within_hours:
        return True, f"Open now until {closing_time.strftime('%H:%M')}"

    return False, f"Closed right now. Open {opening_time.strftime('%H:%M')} - {closing_time.strftime('%H:%M')}"


def is_vendor_open_now(vendor, current_dt=None):
    return get_vendor_availability(vendor, current_dt=current_dt)[0]
