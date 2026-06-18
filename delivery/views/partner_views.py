from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from helpers.geo_helpers import haversine
from delivery.data.assignment_repo import DeliveryAssignmentRepository
from delivery.data.partner_repo import DeliveryPartnerRepository
from delivery.models import DeliveryAssignment, DeliveryEarning, DeliveryReview
from delivery.permissions import IsApprovedDeliveryPartner
from delivery.serializers import (
    DeliveryEarningSerializer,
    DeliveryReviewSerializer,
    UpdateLocationSerializer,
)
from delivery.tasks import check_assignment_timeout, check_stale_assignments, search_and_notify_partners
from orders.models import Order
from orders.serializers import OrderSerializer
from orders.data.order_repo import OrderRepository
from delivery.actions.partner_actions import UpdateLocationAction


class DeliveryPartnerRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response(
            {"error": "Self-registration is not available. Contact an administrator to be onboarded."},
            status=status.HTTP_403_FORBIDDEN,
        )


class DeliveryDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        partner = getattr(request.user, "delivery_profile", None)
        if not partner:
            return Response(
                {"error": "Delivery partner profile not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not partner.is_approved:
            return Response(
                {
                    "is_approved": False,
                    "partner_status": partner.status,
                    "total_deliveries": partner.total_deliveries,
                    "total_earnings": str(partner.total_earnings),
                    "average_rating": str(partner.average_rating),
                    "active_orders": [],
                }
            )

        base_qs = OrderRepository.get_base_queryset()
        active_orders = base_qs.filter(
            delivery_partner=request.user,
        ).exclude(status__in=["delivered", "cancelled"])
        return Response(
            {
                "total_deliveries": partner.total_deliveries,
                "total_earnings": str(partner.total_earnings),
                "average_rating": str(partner.average_rating),
                "active_orders": OrderSerializer(active_orders, many=True).data,
                "partner_status": partner.status,
                "is_approved": partner.is_approved,
            }
        )


class AvailableOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedDeliveryPartner]

    def get(self, request):
        # Legacy fallback view: Maps exactly to PendingAssignmentRequestsView logic
        # strictly respecting assignment timeouts and notifications
        partner = request.user.delivery_profile
        
        # Enforce exactly the 1-minute timeout queue logic
        expired_assignments = DeliveryAssignmentRepository.get_expired_for_partner(partner, minutes_old=1)
        for assignment in expired_assignments:
            check_assignment_timeout(str(assignment.id))
            
        check_stale_assignments()
        
        pending_qs = DeliveryAssignmentRepository.get_pending_for_partner(
            partner=partner,
            exclude_rejected=True,
            select_related=["order__vendor"],
            prefetch=["order__items"]
        )
        
        # Extract orders and simulate distance_km for legacy compatibility
        nearby_orders = []
        for assignment in pending_qs:
            order = assignment.order
            order_data = OrderSerializer(order).data
            if partner.current_latitude and partner.current_longitude and order.vendor.latitude and order.vendor.longitude:
                dist = haversine(
                    float(partner.current_latitude),
                    float(partner.current_longitude),
                    float(order.vendor.latitude),
                    float(order.vendor.longitude),
                )
                order_data["distance_km"] = round(dist, 2)
            nearby_orders.append(order_data)
            
        nearby_orders.sort(key=lambda o: o.get("distance_km", 999))
        return Response(nearby_orders)


class UpdateLocationView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedDeliveryPartner]

    def post(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        UpdateLocationAction.execute(
            user=request.user,
            latitude=serializer.validated_data["latitude"],
            longitude=serializer.validated_data["longitude"],
            order_id=serializer.validated_data.get("order_id"),
        )

        return Response({"status": "Location updated."})


class SetAvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedDeliveryPartner]

    def post(self, request):
        partner = request.user.delivery_profile
        is_online = request.data.get("is_online", False)

        if is_online:
            DeliveryPartnerRepository.update(partner, status="available")
            if partner.current_latitude and partner.current_longitude:
                for assignment in DeliveryAssignment.objects.filter(status__in=["searching", "notified"]):
                    search_and_notify_partners.delay(str(assignment.id))
        else:
            DeliveryPartnerRepository.update(partner, status="offline")

        return Response({"partner_status": partner.status})


class DeliveryHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedDeliveryPartner]
    serializer_class = OrderSerializer

    def get_queryset(self):
        base_qs = OrderRepository.get_base_queryset()
        status_param = self.request.query_params.get("status", "")
        requested_statuses = [
            value.strip()
            for value in status_param.split(",")
            if value.strip()
        ]
        allowed_statuses = {"delivered", "cancelled"}
        statuses = [
            value for value in requested_statuses if value in allowed_statuses
        ] or ["delivered", "cancelled"]

        return base_qs.filter(
            delivery_partner=self.request.user,
            status__in=statuses,
        )


class DeliveryEarningsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedDeliveryPartner]
    serializer_class = DeliveryEarningSerializer

    def get_queryset(self):
        return DeliveryEarning.objects.filter(delivery_partner=self.request.user.delivery_profile)


class DeliveryReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliveryReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        partner_id = self.kwargs.get("partner_id")
        queryset = DeliveryReview.objects.select_related(
            "delivery_partner__user", "customer", "order"
        ).order_by("-created_at")

        if getattr(user, "role", "") == "admin":
            if partner_id:
                return queryset.filter(delivery_partner_id=partner_id)
            return queryset

        if hasattr(user, "delivery_profile"):
            own_partner_id = str(user.delivery_profile.id)
            if partner_id and str(partner_id) != own_partner_id:
                return queryset.none()
            return queryset.filter(delivery_partner_id=own_partner_id)

        return queryset.none()
