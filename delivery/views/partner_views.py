from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.utils import haversine
from delivery.models import DeliveryAssignment, DeliveryEarning, DeliveryReview
from delivery.serializers import (
    DeliveryEarningSerializer,
    DeliveryReviewSerializer,
    UpdateLocationSerializer,
)
from delivery.tasks import search_and_notify_partners
from orders.models import Order
from orders.serializers import OrderSerializer
from delivery.data.partner_repo import DeliveryPartnerRepository
from orders.data.order_repo import OrderRepository


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
        partner = request.user.delivery_profile
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
            }
        )


class AvailableOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        partner = request.user.delivery_profile
        base_qs = OrderRepository.get_base_queryset()
        orders = base_qs.filter(status="ready", delivery_partner__isnull=True).select_related("vendor")

        if partner.current_latitude and partner.current_longitude:
            nearby_orders = []
            for order in orders:
                dist = haversine(
                    float(partner.current_latitude),
                    float(partner.current_longitude),
                    float(order.vendor.latitude),
                    float(order.vendor.longitude),
                )
                if dist <= float(order.vendor.delivery_radius_km) * 2:
                    order_data = OrderSerializer(order).data
                    order_data["distance_km"] = round(dist, 2)
                    nearby_orders.append(order_data)
            nearby_orders.sort(key=lambda o: o["distance_km"])
            return Response(nearby_orders)

        return Response(OrderSerializer(orders, many=True).data)


class UpdateLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner = request.user.delivery_profile
        had_no_location = not partner.current_latitude
        
        url_data = {"current_latitude": serializer.validated_data["latitude"], "current_longitude": serializer.validated_data["longitude"]}
        if partner.status == "offline":
            url_data["status"] = "available"
        
        DeliveryPartnerRepository.update(partner, **url_data)

        if had_no_location and partner.status == "available":
            for assignment in DeliveryAssignment.objects.filter(status__in=["searching", "notified"]):
                search_and_notify_partners.delay(str(assignment.id))

        return Response({"status": "Location updated."})


class SetAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        base_qs = OrderRepository.get_base_queryset()
        return base_qs.filter(delivery_partner=self.request.user, status="delivered")


class DeliveryEarningsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryEarningSerializer

    def get_queryset(self):
        return DeliveryEarning.objects.filter(delivery_partner=self.request.user.delivery_profile)


class DeliveryReviewViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        partner_id = self.kwargs.get("partner_id")
        if partner_id:
            return DeliveryReview.objects.filter(delivery_partner_id=partner_id)
        return DeliveryReview.objects.all()

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
