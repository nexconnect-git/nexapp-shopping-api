from typing import Any
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework.exceptions import PermissionDenied

from delivery.data.partner_repo import DeliveryPartnerRepository
from delivery.models import DeliveryPartner, DeliveryAssignment
from delivery.tasks import search_and_notify_partners
from orders.models import Order


class UpdateLocationAction:
    @staticmethod
    @transaction.atomic
    def execute(user: Any, latitude: float, longitude: float, order_id: str | None = None) -> DeliveryPartner:
        partner = user.delivery_profile
        had_no_location = not partner.current_latitude

        if not partner.is_approved:
            raise PermissionDenied("Delivery partner is not approved.")

        active_order_qs = Order.objects.select_for_update().filter(
            delivery_partner=user,
            status__in=["ready", "picked_up", "on_the_way"],
        )
        if order_id:
            if not active_order_qs.filter(pk=order_id).exists():
                raise PermissionDenied("Location updates are allowed only for assigned active orders.")
        elif partner.status == "on_delivery" and not active_order_qs.exists():
            raise PermissionDenied("No active assigned order for location tracking.")

        partner.current_latitude = latitude
        partner.current_longitude = longitude
        if partner.status == "offline":
            partner.status = "available"
        partner.save(update_fields=["current_latitude", "current_longitude", "status", "updated_at"])

        if had_no_location and partner.status == "available":
            for assignment in DeliveryAssignment.objects.filter(status__in=["searching", "notified"]):
                search_and_notify_partners.delay(str(assignment.id))
        
        return partner


class SetAvailabilityAction:
    @staticmethod
    @transaction.atomic
    def execute(user: Any, is_online: bool) -> DeliveryPartner:
        partner = user.delivery_profile

        if is_online:
            partner.status = "available"
            partner.save(update_fields=["status", "updated_at"])
            if partner.current_latitude and partner.current_longitude:
                for assignment in DeliveryAssignment.objects.filter(status__in=["searching", "notified"]):
                    search_and_notify_partners.delay(str(assignment.id))
        else:
            partner.status = "offline"
            partner.save(update_fields=["status", "updated_at"])
            
        return partner


class AdminTogglePartnerApprovalAction:
    @staticmethod
    @transaction.atomic
    def execute(partner_id: str, is_approved: bool) -> DeliveryPartner:
        try:
            partner = DeliveryPartner.objects.get(pk=partner_id)
        except DeliveryPartner.DoesNotExist:
            raise ValueError("Delivery partner not found.")

        if is_approved:
            partner.is_approved = True
            partner.status = "available"
        else:
            partner.is_approved = False
            partner.status = "offline"
            
        partner.save(update_fields=["is_approved", "status", "updated_at"])
        return partner


class AdminGeneratePartnerTemporaryPasswordAction:
    @staticmethod
    @transaction.atomic
    def execute(partner_id: str) -> tuple[DeliveryPartner, str]:
        try:
            partner = DeliveryPartnerRepository.get_by_id(
                partner_id,
                select_related=["user"],
            )
        except DeliveryPartner.DoesNotExist as exc:
            raise ValueError("Delivery partner not found.") from exc

        temporary_password = get_random_string(12)
        partner.user.set_password(temporary_password)
        partner.user.force_password_change = True
        partner.user.temp_password = temporary_password
        partner.user.save(
            update_fields=["password", "force_password_change", "temp_password"],
        )
        return partner, temporary_password
