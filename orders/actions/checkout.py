from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Address
from helpers.delivery_quotes import DeliveryServiceabilityError, FarDeliveryConfirmationRequired, quote_vendor_delivery
from helpers.vendor_hours import get_vendor_availability
from orders.models import Cart, Coupon, CouponUsage, PlatformSetting
from vendors.models import VendorHoliday


COD_UPI_CONFIRMATION_MESSAGE = (
    "Cash is not accepted at delivery. Even if you choose COD, you must pay the "
    "delivery partner using UPI at the time of delivery."
)


def decimal_money(value) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def cart_items_for_user(user):
    try:
        cart = Cart.objects.prefetch_related("items__product__vendor").get(user=user)
    except Cart.DoesNotExist:
        raise ValueError("Cart is empty.")
    cart_items = list(cart.items.select_related("product__vendor").all())
    if not cart_items:
        raise ValueError("Cart is empty.")
    return cart, cart_items


def validate_delivery_address(address: Address) -> None:
    required = {
        "full_name": "Receiver name is required.",
        "phone": "Mobile number is required.",
        "address_line1": "House, flat, or building number is required.",
        "city": "City is required.",
        "state": "State is required.",
        "postal_code": "Pincode is required.",
        "latitude": "Latitude is required for delivery.",
        "longitude": "Longitude is required for delivery.",
    }
    errors = [message for field, message in required.items() if not getattr(address, field, None)]
    digits = "".join(ch for ch in str(address.phone or "") if ch.isdigit())
    if address.phone and len(digits) not in (10, 12):
        errors.append("Enter a valid mobile number.")
    pincode = "".join(ch for ch in str(address.postal_code or "") if ch.isdigit())
    if address.postal_code and len(pincode) != 6:
        errors.append("Enter a valid 6 digit pincode.")
    if errors:
        raise ValueError({"code": "invalid_delivery_address", "errors": errors})


def group_items_by_vendor(cart_items: Iterable) -> dict:
    vendor_items = defaultdict(list)
    for item in cart_items:
        vendor_items[item.product.vendor].append(item)
    return dict(vendor_items)


def validate_single_vendor_cart(vendor_items: dict) -> None:
    if len(vendor_items) <= 1:
        return
    names = ", ".join(vendor.store_name for vendor in vendor_items)
    raise ValueError({
        "code": "multi_store_cart",
        "error": "Your cart has items from more than one store. Clear the cart and order from one store at a time.",
        "stores": names,
    })


def validate_cod_confirmation(payment_method: str, cod_upi_confirmed: bool) -> None:
    if payment_method == "cod" and not cod_upi_confirmed:
        raise ValueError({
            "code": "cod_upi_confirmation_required",
            "error": COD_UPI_CONFIRMATION_MESSAGE,
        })


def validate_payment_method(payment_method: str, platform: PlatformSetting) -> None:
    if payment_method == "cod" and not platform.is_cod_enabled():
        raise ValueError("Cash on delivery is currently disabled.")
    if payment_method == "razorpay" and not platform.is_online_payment_enabled():
        raise ValueError("Online payment is currently disabled.")
    if payment_method not in ("cod", "razorpay"):
        raise ValueError("Select an enabled payment method.")


def validate_coupon_for_user(coupon_code: str, user, cart_total: Decimal) -> Coupon | None:
    if not coupon_code:
        return None
    now = timezone.now()
    try:
        coupon = Coupon.objects.get(code=coupon_code, is_active=True)
    except Coupon.DoesNotExist:
        raise ValueError("Invalid coupon code.")
    if coupon.valid_until and coupon.valid_until < now:
        raise ValueError("Coupon has expired.")
    if coupon.valid_from > now:
        raise ValueError("Coupon is not yet valid.")
    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise ValueError("Coupon usage limit reached.")
    if CouponUsage.objects.filter(coupon=coupon, user=user).count() >= coupon.per_user_limit:
        raise ValueError("You have already used this coupon.")
    if cart_total < coupon.min_order_amount:
        raise ValueError(f"Minimum order amount for this coupon is {coupon.min_order_amount}.")
    return coupon


def validate_schedule_slot(scheduled_for, vendor, items) -> None:
    if not scheduled_for:
        return
    if isinstance(scheduled_for, str):
        scheduled_for = parse_datetime(scheduled_for)
        if scheduled_for is None:
            raise ValueError("Scheduled delivery slot is invalid.")
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for)
    scheduled_local = timezone.localtime(scheduled_for)
    now_local = timezone.localtime(timezone.now())
    if scheduled_local <= now_local:
        raise ValueError("Scheduled delivery slot must be in the future.")
    max_window_days = 7
    if scheduled_local > now_local + timedelta(days=max_window_days):
        raise ValueError(f"Scheduled delivery can be placed up to {max_window_days} days ahead.")
    if VendorHoliday.objects.filter(vendor=vendor, date=scheduled_local.date()).exists():
        raise ValueError(f"'{vendor.store_name}' is closed on the selected schedule date.")
    if not all(item.product.is_scheduled_delivery for item in items):
        raise ValueError("One or more products are not available for scheduled orders.")
    min_prep = max(
        [int(getattr(vendor, "scheduled_buffer_min", 0) or 0), int(getattr(vendor, "base_prep_time_min", 0) or 0)]
        + [int(getattr(item.product, "prep_time_minutes", 0) or 0) for item in items]
    )
    if scheduled_local < now_local + timedelta(minutes=min_prep):
        raise ValueError(f"Selected slot must be at least {min_prep} minutes from now.")
    if vendor.opening_time and vendor.closing_time:
        selected_time = scheduled_local.time()
        if not (vendor.opening_time <= selected_time <= vendor.closing_time):
            raise ValueError("Selected slot is outside store working hours.")


def quote_cart_delivery(vendor_items: dict, address: Address, platform: PlatformSetting, confirm_far_delivery: bool):
    total_delivery_fee = Decimal("0.00")
    quotes = []
    far_delivery_quotes = []
    for vendor, items in vendor_items.items():
        subtotal = sum(item.product.price * item.quantity for item in items)
        quote = quote_vendor_delivery(
            vendor=vendor,
            address=address,
            products=[item.product for item in items],
            quantities={str(item.product.id): item.quantity for item in items},
            subtotal=subtotal,
            platform=platform,
        )
        if not quote.is_serviceable:
            raise DeliveryServiceabilityError(quote)
        payload = quote.as_dict()
        if platform.free_delivery_above > 0 and subtotal >= platform.free_delivery_above:
            payload["delivery_fee"] = "0.00"
            payload["reason"] = f"Free delivery on orders above Rs.{platform.free_delivery_above}"
        else:
            payload["reason"] = f"Distance-based delivery for {round(payload['distance_km'], 1)} km"
            total_delivery_fee += quote.delivery_fee
        quotes.append(payload)
        if quote.requires_far_delivery_confirmation:
            far_delivery_quotes.append(payload)
    if far_delivery_quotes and not confirm_far_delivery:
        raise FarDeliveryConfirmationRequired(far_delivery_quotes)
    return total_delivery_fee.quantize(Decimal("0.01")), quotes, far_delivery_quotes


def calculate_checkout_preview(
    user,
    delivery_address_id,
    payment_method="cod",
    coupon_code="",
    wallet_amount=Decimal("0"),
    loyalty_discount=Decimal("0"),
    scheduled_for=None,
    confirm_far_delivery=False,
    cod_upi_confirmed=False,
    require_cod_confirmation=True,
) -> dict:
    if not user.is_active:
        raise ValueError("Your account is not active. Please contact support.")
    try:
        address = Address.objects.get(pk=delivery_address_id, user=user)
    except Address.DoesNotExist:
        raise ValueError("Delivery address not found.")
    validate_delivery_address(address)
    platform = PlatformSetting.get_setting()
    validate_payment_method(payment_method, platform)
    if require_cod_confirmation:
        validate_cod_confirmation(payment_method, cod_upi_confirmed)
    _cart, cart_items = cart_items_for_user(user)
    vendor_items = group_items_by_vendor(cart_items)
    validate_single_vendor_cart(vendor_items)
    vendor = next(iter(vendor_items))
    items = vendor_items[vendor]
    is_open_now, availability_note = get_vendor_availability(vendor, current_dt=timezone.localtime(timezone.now()))
    if not scheduled_for and not is_open_now:
        raise ValueError(f"'{vendor.store_name}' {availability_note.lower()}.")
    validate_schedule_slot(scheduled_for, vendor, items)
    if VendorHoliday.objects.filter(vendor=vendor, date=timezone.localdate()).exists() and not scheduled_for:
        raise ValueError(f"'{vendor.store_name}' is closed today for a holiday.")
    item_subtotal = sum(item.product.price * item.quantity for item in cart_items)
    product_discount = sum(
        max((item.product.compare_price or item.product.price) - item.product.price, Decimal("0")) * item.quantity
        for item in cart_items
    )
    coupon = validate_coupon_for_user((coupon_code or "").strip().upper(), user, item_subtotal)
    coupon_discount = coupon.calculate_discount(item_subtotal) if coupon else Decimal("0.00")
    delivery_fee, delivery_quotes, far_delivery_quotes = quote_cart_delivery(vendor_items, address, platform, confirm_far_delivery)
    if coupon and coupon.discount_type == "free_delivery":
        coupon_discount = delivery_fee
        delivery_fee = Decimal("0.00")

    platform_fee = decimal_money(getattr(platform, "platform_fee", 0))
    packaging_fee = decimal_money(getattr(platform, "packaging_fee", 0))
    small_cart_threshold = decimal_money(getattr(platform, "small_cart_threshold", 0))
    small_cart_fee = decimal_money(getattr(platform, "small_cart_fee", 0)) if small_cart_threshold and item_subtotal < small_cart_threshold else Decimal("0.00")
    surge_fee = decimal_money(getattr(platform, "surge_fee", 0))
    tax_rate = decimal_money(getattr(platform, "tax_percentage", 0))
    taxable = max(item_subtotal - coupon_discount, Decimal("0.00")) + platform_fee + packaging_fee + small_cart_fee + surge_fee
    tax_amount = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    wallet_amount = max(decimal_money(wallet_amount), Decimal("0.00"))
    loyalty_discount = max(decimal_money(loyalty_discount), Decimal("0.00"))
    total = max(
        item_subtotal - coupon_discount + delivery_fee + platform_fee + packaging_fee + small_cart_fee + surge_fee + tax_amount - wallet_amount - loyalty_discount,
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    return {
        "vendor": vendor,
        "items": cart_items,
        "address": address,
        "coupon": coupon,
        "item_subtotal": item_subtotal.quantize(Decimal("0.01")),
        "product_discount": product_discount.quantize(Decimal("0.01")),
        "coupon_discount": coupon_discount.quantize(Decimal("0.01")),
        "delivery_fee": delivery_fee,
        "platform_fee": platform_fee,
        "packaging_fee": packaging_fee,
        "small_cart_fee": small_cart_fee,
        "tax_amount": tax_amount,
        "surge_fee": surge_fee,
        "wallet_discount": wallet_amount,
        "loyalty_discount": loyalty_discount,
        "final_payable": total,
        "delivery_quotes": delivery_quotes,
        "requires_far_delivery_confirmation": bool(far_delivery_quotes),
        "far_delivery_quotes": far_delivery_quotes,
        "cod_upi_confirmation_required": payment_method == "cod",
        "cod_upi_confirmed": bool(cod_upi_confirmed),
        "cod_upi_message": COD_UPI_CONFIRMATION_MESSAGE,
    }


def public_price_breakup(preview: dict) -> dict:
    keys = [
        "item_subtotal",
        "product_discount",
        "coupon_discount",
        "delivery_fee",
        "platform_fee",
        "packaging_fee",
        "small_cart_fee",
        "tax_amount",
        "surge_fee",
        "wallet_discount",
        "loyalty_discount",
        "final_payable",
    ]
    return {key: str(preview[key]) for key in keys}


def available_slots_for_cart(user, start_date=None, days: int = 7) -> list[dict]:
    _cart, cart_items = cart_items_for_user(user)
    vendor_items = group_items_by_vendor(cart_items)
    validate_single_vendor_cart(vendor_items)
    vendor = next(iter(vendor_items))
    items = vendor_items[vendor]
    if not all(item.product.is_scheduled_delivery for item in items):
        return []
    today = timezone.localdate()
    if start_date:
        try:
            today = datetime.fromisoformat(str(start_date)).date()
        except ValueError:
            today = timezone.localdate()
    min_prep = max(
        [int(getattr(vendor, "scheduled_buffer_min", 0) or 0), int(getattr(vendor, "base_prep_time_min", 0) or 0)]
        + [int(getattr(item.product, "prep_time_minutes", 0) or 0) for item in items]
    )
    now_local = timezone.localtime(timezone.now())
    slots = []
    for offset in range(days):
        date_value = today + timedelta(days=offset)
        if VendorHoliday.objects.filter(vendor=vendor, date=date_value).exists():
            continue
        open_time = vendor.opening_time
        close_time = vendor.closing_time
        if not open_time or not close_time:
            continue
        cursor = timezone.make_aware(datetime.combine(date_value, open_time))
        close_at = timezone.make_aware(datetime.combine(date_value, close_time))
        if cursor < now_local + timedelta(minutes=min_prep):
            cursor = now_local + timedelta(minutes=min_prep)
            cursor = cursor.replace(minute=0 if cursor.minute == 0 else 30 if cursor.minute <= 30 else 0, second=0, microsecond=0)
            if cursor.minute == 0 and cursor < now_local + timedelta(minutes=min_prep):
                cursor += timedelta(hours=1)
        while cursor <= close_at:
            end = min(cursor + timedelta(hours=2), close_at)
            if end > cursor:
                slots.append({
                    "id": cursor.isoformat(),
                    "date": cursor.date().isoformat(),
                    "start": cursor.isoformat(),
                    "end": end.isoformat(),
                    "label": f"{cursor.strftime('%a, %d %b')} {cursor.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}",
                    "available": True,
                    "capacity_remaining": None,
                })
            cursor += timedelta(hours=2)
    return slots
