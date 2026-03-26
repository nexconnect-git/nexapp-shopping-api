import math

from rest_framework import status, viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken

from .models import DeliveryPartner, DeliveryReview, DeliveryEarning, Asset
from .serializers import (
    DeliveryPartnerRegistrationSerializer,
    DeliveryPartnerSerializer,
    DeliveryReviewSerializer,
    DeliveryEarningSerializer,
    UpdateLocationSerializer,
    AssetSerializer,
)
from orders.models import Order, OrderTracking
from orders.serializers import OrderSerializer
from accounts.permissions import IsAdminRole
from notifications.models import Notification


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class DeliveryPartnerRegistrationView(APIView):
    """Delivery partner self-registration is disabled. Admin onboards partners via admin panel."""
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
        total_deliveries = partner.total_deliveries
        total_earnings = partner.total_earnings
        active_orders = Order.objects.filter(
            delivery_partner=request.user,
            status__in=["ready", "picked_up", "on_the_way"],
        )
        return Response(
            {
                "total_deliveries": total_deliveries,
                "total_earnings": str(total_earnings),
                "average_rating": str(partner.average_rating),
                "active_orders": OrderSerializer(active_orders, many=True).data,
            }
        )


class AvailableOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        partner = request.user.delivery_profile
        orders = Order.objects.filter(
            status="ready", delivery_partner__isnull=True
        ).select_related("vendor")

        # Filter by proximity to partner's current location
        if partner.current_latitude and partner.current_longitude:
            nearby_orders = []
            for order in orders:
                distance = haversine(
                    float(partner.current_latitude),
                    float(partner.current_longitude),
                    float(order.vendor.latitude),
                    float(order.vendor.longitude),
                )
                if distance <= float(order.vendor.delivery_radius_km) * 2:
                    order_data = OrderSerializer(order).data
                    order_data["distance_km"] = round(distance, 2)
                    nearby_orders.append(order_data)
            nearby_orders.sort(key=lambda o: o["distance_km"])
            return Response(nearby_orders)

        return Response(OrderSerializer(orders, many=True).data)


class AcceptDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(
                pk=pk, status="ready", delivery_partner__isnull=True
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or already assigned."},
                status=status.HTTP_404_NOT_FOUND,
            )

        partner = request.user.delivery_profile
        order.delivery_partner = request.user
        order.save(update_fields=["delivery_partner", "updated_at"])

        partner.status = "on_delivery"
        partner.save(update_fields=["status", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="ready",
            description=f"Delivery partner {request.user.get_full_name() or request.user.username} accepted the order.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        Notification.objects.create(
            user=order.customer,
            title="Delivery Partner Assigned",
            message=f"A delivery partner has accepted your order #{order.order_number} and will pick it up shortly.",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        return Response(OrderSerializer(order).data)


class UpdateDeliveryStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, delivery_partner=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        allowed_statuses = ["picked_up", "on_the_way"]
        if new_status not in allowed_statuses:
            return Response(
                {"error": f"Status must be one of: {', '.join(allowed_statuses)}. Use confirm-delivery endpoint to mark as delivered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        description_map = {
            "picked_up": "Order picked up from vendor.",
            "on_the_way": "Order is on the way.",
        }
        partner = request.user.delivery_profile
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=description_map.get(new_status, ""),
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        if new_status == "on_the_way":
            Notification.objects.create(
                user=order.customer,
                title="Order On the Way",
                message=f"Your order #{order.order_number} is on the way to you!",
                notification_type="delivery",
                data={"order_id": str(order.id), "order_number": order.order_number},
            )

        return Response(OrderSerializer(order).data)


class UpdateLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner = request.user.delivery_profile
        partner.current_latitude = serializer.validated_data["latitude"]
        partner.current_longitude = serializer.validated_data["longitude"]
        partner.save(update_fields=["current_latitude", "current_longitude", "updated_at"])

        return Response({"status": "Location updated."})


class ConfirmDeliveryView(APIView):
    """POST /api/delivery/confirm/<order_id>/ — verify OTP + upload photo to mark as delivered."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, delivery_partner=request.user, status="on_the_way")
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or not in 'on_the_way' status."},
                status=status.HTTP_404_NOT_FOUND,
            )

        submitted_otp = str(request.data.get("otp", "")).strip()
        if not submitted_otp:
            return Response({"error": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)

        if order.delivery_otp and order.delivery_otp != submitted_otp:
            return Response({"error": "Invalid OTP. Please check with the customer."}, status=status.HTTP_400_BAD_REQUEST)

        photo = request.FILES.get("photo")
        if photo:
            order.delivery_photo = photo

        from django.utils import timezone
        order.status = "delivered"
        order.actual_delivery_time = timezone.now()
        order.save(update_fields=["status", "actual_delivery_time", "delivery_photo", "updated_at"])

        partner = request.user.delivery_profile
        partner.status = "available"
        partner.total_deliveries += 1
        DeliveryEarning.objects.create(
            delivery_partner=partner,
            order=order,
            amount=order.delivery_fee,
        )
        partner.total_earnings += order.delivery_fee
        partner.save(update_fields=["status", "total_deliveries", "total_earnings", "updated_at"])

        OrderTracking.objects.create(
            order=order,
            status="delivered",
            description="Order delivered and confirmed with OTP.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        Notification.objects.create(
            user=order.customer,
            title="Order Delivered",
            message=f"Your order #{order.order_number} has been delivered successfully. Enjoy!",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        return Response(OrderSerializer(order).data)


class DeliveryHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(
            delivery_partner=self.request.user,
            status="delivered",
        )


class DeliveryEarningsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryEarningSerializer

    def get_queryset(self):
        return DeliveryEarning.objects.filter(
            delivery_partner=self.request.user.delivery_profile
        )


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


# ── Admin views ────────────────────────────────────────────────────────────────

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminDeliveryPartnerListView(APIView):
    """GET/POST /api/admin/delivery-partners/ — list or create delivery partners (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = DeliveryPartner.objects.select_related('user').order_by('-created_at')

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                user__username__icontains=search
            ) | DeliveryPartner.objects.filter(
                user__email__icontains=search
            ) | DeliveryPartner.objects.filter(
                user__first_name__icontains=search
            )
            qs = qs.distinct()

        is_approved = request.query_params.get('is_approved')
        if is_approved is not None:
            qs = qs.filter(is_approved=is_approved.lower() == 'true')

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DeliveryPartnerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Admin creates a new delivery partner account."""
        serializer = DeliveryPartnerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        data = DeliveryPartnerSerializer(partner).data
        if hasattr(partner, 'auto_generated_password'):
            data['temp_password'] = partner.auto_generated_password
        return Response(data, status=status.HTTP_201_CREATED)


class AdminDeliveryPartnerDetailView(APIView):
    """GET/PATCH /api/admin/delivery-partners/<id>/ — manage a single delivery partner."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_partner(self, pk):
        try:
            return DeliveryPartner.objects.select_related('user').get(pk=pk)
        except DeliveryPartner.DoesNotExist:
            return None

    def get(self, request, pk):
        partner = self._get_partner(pk)
        if not partner:
            return Response({'error': 'Delivery partner not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DeliveryPartnerSerializer(partner).data)

    def patch(self, request, pk):
        partner = self._get_partner(pk)
        if not partner:
            return Response({'error': 'Delivery partner not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DeliveryPartnerSerializer(partner, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        partner = self._get_partner(pk)
        if not partner:
            return Response({'error': 'Delivery partner not found.'}, status=status.HTTP_404_NOT_FOUND)
        partner.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminDeliveryPartnerApprovalView(APIView):
    """POST /api/admin/delivery-partners/<id>/approve/ — approve or reject a partner."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            partner = DeliveryPartner.objects.get(pk=pk)
        except DeliveryPartner.DoesNotExist:
            return Response({'error': 'Delivery partner not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')  # 'approve' or 'reject'
        if action == 'approve':
            partner.is_approved = True
            partner.status = 'available'
            partner.save(update_fields=['is_approved', 'status', 'updated_at'])
            return Response({'status': 'approved', **DeliveryPartnerSerializer(partner).data})
        elif action == 'reject':
            partner.is_approved = False
            partner.status = 'offline'
            partner.save(update_fields=['is_approved', 'status', 'updated_at'])
            return Response({'status': 'rejected', **DeliveryPartnerSerializer(partner).data})
        else:
            return Response({'error': "action must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)


class AdminAssetListCreateView(APIView):
    """GET/POST /api/admin/assets/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Asset.objects.select_related('assigned_to__user').order_by('-created_at')
        asset_type = request.query_params.get('type')
        if asset_type:
            qs = qs.filter(asset_type=asset_type)
        asset_status = request.query_params.get('status')
        if asset_status:
            qs = qs.filter(status=asset_status)
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AssetSerializer(page, many=True).data)

    def post(self, request):
        serializer = AssetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminAssetDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/assets/<pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        try:
            return Asset.objects.select_related('assigned_to__user').get(pk=pk)
        except Asset.DoesNotExist:
            return None

    def get(self, request, pk):
        asset = self._get(pk)
        if not asset:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AssetSerializer(asset).data)

    def patch(self, request, pk):
        asset = self._get(pk)
        if not asset:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssetSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        asset = self._get(pk)
        if not asset:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
