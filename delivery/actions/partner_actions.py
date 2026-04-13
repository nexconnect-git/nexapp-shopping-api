from typing import Any
from django.db import transaction
from delivery.models import DeliveryPartner, DeliveryAssignment
from delivery.tasks import search_and_notify_partners


class UpdateLocationAction:
    @staticmethod
    @transaction.atomic
    def execute(user: Any, latitude: float, longitude: float) -> DeliveryPartner:
        partner = user.delivery_profile
        had_no_location = not partner.current_latitude

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
