from datetime import time

from django.utils import timezone


def is_vendor_within_hours(vendor, current_dt=None):
    local_dt = timezone.localtime(current_dt or timezone.now())
    current_time = local_dt.time().replace(tzinfo=None)
    opening_time = _coerce_time(getattr(vendor, "opening_time", None))
    closing_time = _coerce_time(getattr(vendor, "closing_time", None))
    if not opening_time or not closing_time or opening_time == closing_time:
        return True
    if opening_time < closing_time:
        return opening_time <= current_time <= closing_time
    return current_time >= opening_time or current_time <= closing_time


def get_vendor_availability(vendor, current_dt=None):

    if not vendor.is_open:
        return False, "Currently closed"

    if hasattr(vendor, "is_accepting_orders") and not vendor.is_accepting_orders:
        return False, "Temporarily not accepting orders"

    opening_time = _coerce_time(getattr(vendor, "opening_time", None))
    closing_time = _coerce_time(getattr(vendor, "closing_time", None))
    if not opening_time or not closing_time:
        return True, "Open now"

    if opening_time == closing_time:
        return True, "Open now"

    if is_vendor_within_hours(vendor, current_dt=current_dt):
        return True, f"Open now until {closing_time.strftime('%H:%M')}"

    current_time = timezone.localtime(current_dt or timezone.now()).time().replace(tzinfo=None)
    next_day = "tomorrow" if opening_time < closing_time and current_time > closing_time else "today"
    return False, f"Opens {next_day} at {opening_time.strftime('%H:%M')} ({timezone.get_current_timezone_name()}). Scheduled until {closing_time.strftime('%H:%M')}."


def is_vendor_open_now(vendor, current_dt=None):
    return get_vendor_availability(vendor, current_dt=current_dt)[0]


def _coerce_time(value):
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return timezone.datetime.strptime(normalized, fmt).time()
            except ValueError:
                continue
    return None
