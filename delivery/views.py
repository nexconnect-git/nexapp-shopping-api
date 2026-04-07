"""
API views for the ``delivery`` app.

Endpoints covered:
  - Delivery partner registration (disabled — admin-only onboarding)
  - Partner dashboard, available orders, delivery workflow
  - Location updates and availability toggling
  - Assignment requests: accept, reject, cancel
  - Delivery history and earnings
  - Admin: partner CRUD, approval, earnings calculation
  - Admin: asset management (list, create, update, delete)
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from rest_framework import generics, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from backend.utils import haversine
from delivery.models import Asset, DeliveryAssignment, DeliveryEarning, DeliveryPartner, DeliveryReview
from delivery.serializers import (
    AssetSerializer,
    DeliveryAssignmentSerializer,
    DeliveryEarningSerializer,
    DeliveryPartnerRegistrationSerializer,
    DeliveryPartnerSerializer,
    DeliveryReviewSerializer,
    UpdateLocationSerializer,
)
from delivery.services import DeliveryService
from delivery.tasks import (
    _expand_and_retry,
    check_assignment_timeout,
    check_stale_assignments,
    search_and_notify_partners,
)
from orders.models import Order
from orders.serializers import OrderSerializer


# ---------------------------------------------------------------------------
# Delivery partner endpoints
# ---------------------------------------------------------------------------

class DeliveryPartnerRegistrationView(APIView):
    """POST /api/delivery/register/ — self-registration is disabled."""

    permission_classes = [AllowAny]

    def post(self, request):  # noqa: ARG002
        """Return 403 — delivery partners are onboarded by admin only.

        Args:
            request: DRF request (unauthenticated allowed).

        Returns:
            403 with an explanatory message.
        """
        return Response(
            {
                "error": (
                    "Self-registration is not available. "
                    "Contact an administrator to be onboarded."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class DeliveryDashboardView(APIView):
    """GET /api/delivery/dashboard/ — authenticated partner's dashboard summary."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return total deliveries, earnings, rating, and active orders.

        Args:
            request: Authenticated DRF request from a delivery partner.

        Returns:
            200 with dashboard statistics.
        """
        partner = request.user.delivery_profile
        active_orders = Order.objects.filter(
            delivery_partner=request.user,
            status__in=["ready", "picked_up", "on_the_way"],
        )
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
    """GET /api/delivery/available-orders/ — orders ready for pickup near the partner."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return orders ready for pickup, sorted by proximity when location is known.

        Args:
            request: Authenticated DRF request from a delivery partner.

        Returns:
            200 with a list of order objects, including ``distance_km`` when location
            is available.
        """
        partner = request.user.delivery_profile
        orders = Order.objects.filter(
            status="ready", delivery_partner__isnull=True
        ).select_related("vendor")

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
    """POST /api/delivery/accept/<pk>/ — partner accepts a delivery."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Assign the partner to an order and return updated order data.

        Args:
            request: Authenticated DRF request from a delivery partner.
            pk: UUID primary key of the order.

        Returns:
            200 with updated order data, or 400/404 on error.
        """
        try:
            order = DeliveryService.accept_delivery(str(pk), request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UpdateDeliveryStatusView(APIView):
    """PATCH /api/delivery/status/<pk>/ — update the delivery status of an order."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        """Transition an order to a new delivery status.

        Args:
            request: Authenticated DRF request with ``status`` field.
            pk: UUID primary key of the order.

        Returns:
            200 with updated order data, or 400/404 on error.
        """
        new_status = request.data.get("status")
        try:
            order = DeliveryService.update_delivery_status(str(pk), new_status, request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class UpdateLocationView(APIView):
    """POST /api/delivery/location/ — update the partner's current GPS coordinates."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Save new latitude/longitude and trigger pending assignment searches.

        When a partner reports their location for the first time, any pending
        delivery assignment searches are immediately dispatched so the partner
        receives notifications without waiting for the scheduler.

        Args:
            request: Authenticated DRF request with ``latitude`` and ``longitude``.

        Returns:
            200 with ``{"status": "Location updated."}``.
        """
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner = request.user.delivery_profile
        had_no_location = not partner.current_latitude
        partner.current_latitude = serializer.validated_data["latitude"]
        partner.current_longitude = serializer.validated_data["longitude"]
        if partner.status == "offline":
            partner.status = "available"
        partner.save(update_fields=["current_latitude", "current_longitude", "status", "updated_at"])

        if had_no_location and partner.status == "available":
            for assignment in DeliveryAssignment.objects.filter(
                status__in=["searching", "notified"]
            ):
                search_and_notify_partners.delay(str(assignment.id))

        return Response({"status": "Location updated."})


class SetAvailabilityView(APIView):
    """POST /api/delivery/set-availability/ — toggle partner online/offline."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Set the partner's availability status.

        When going online, immediately triggers pending assignment searches
        if the partner has a known location.

        Args:
            request: Authenticated DRF request with ``is_online`` boolean.

        Returns:
            200 with updated ``partner_status``.
        """
        partner = request.user.delivery_profile
        is_online = request.data.get("is_online", False)

        if is_online:
            partner.status = "available"
            partner.save(update_fields=["status", "updated_at"])
            if partner.current_latitude and partner.current_longitude:
                for assignment in DeliveryAssignment.objects.filter(
                    status__in=["searching", "notified"]
                ):
                    search_and_notify_partners.delay(str(assignment.id))
        else:
            partner.status = "offline"
            partner.save(update_fields=["status", "updated_at"])

        return Response({"partner_status": partner.status})


class ConfirmDeliveryView(APIView):
    """POST /api/delivery/confirm/<pk>/ — verify OTP and upload photo to mark as delivered."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        """Verify the delivery OTP and finalise the delivery.

        Args:
            request: Authenticated DRF request with ``otp`` and optional
                ``photo`` / ``delivery_photo`` file.
            pk: UUID primary key of the order.

        Returns:
            200 with updated order data, or 400/404 on error.
        """
        submitted_otp = str(request.data.get("otp", "")).strip()
        photo = request.FILES.get("photo") or request.FILES.get("delivery_photo")
        try:
            order = DeliveryService.confirm_delivery(str(pk), request.user, submitted_otp, photo)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DeliveryHistoryView(generics.ListAPIView):
    """GET /api/delivery/history/ — list completed deliveries for the partner."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Return orders delivered by the requesting partner."""
        return Order.objects.filter(
            delivery_partner=self.request.user,
            status="delivered",
        )


class DeliveryEarningsView(generics.ListAPIView):
    """GET /api/delivery/earnings/ — list earning records for the partner."""

    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryEarningSerializer

    def get_queryset(self):
        """Return earnings belonging to the requesting delivery partner."""
        return DeliveryEarning.objects.filter(
            delivery_partner=self.request.user.delivery_profile
        )


class DeliveryReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for delivery partner reviews."""

    serializer_class = DeliveryReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return reviews for a specific partner, or all reviews.

        Returns:
            Queryset filtered by ``partner_id`` URL kwarg when present.
        """
        partner_id = self.kwargs.get("partner_id")
        if partner_id:
            return DeliveryReview.objects.filter(delivery_partner_id=partner_id)
        return DeliveryReview.objects.all()

    def perform_create(self, serializer):
        """Attach the requesting user as the review's customer."""
        serializer.save(customer=self.request.user)


class PendingAssignmentRequestsView(APIView):
    """GET /api/delivery/requests/ — list assignment requests sent to this partner."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return pending assignment requests, expiring stale ones first.

        Synchronously runs timeout and stale-check handlers so the response
        reflects cleaned-up state even when the RQ scheduler is not running.

        Args:
            request: Authenticated DRF request from a delivery partner.

        Returns:
            200 with list of pending assignment objects.
        """
        partner = request.user.delivery_profile

        # Expire notifications older than 1 minute
        cutoff = timezone.now() - timedelta(minutes=1)
        expired_assignments = DeliveryAssignment.objects.filter(
            notified_partners=partner,
            status="notified",
            last_search_at__lt=cutoff,
        )
        for assignment in expired_assignments:
            check_assignment_timeout(str(assignment.id))

        check_stale_assignments()

        pending_qs = (
            DeliveryAssignment.objects.filter(
                notified_partners=partner,
                status="notified",
            )
            .exclude(rejected_partners=partner)
            .select_related("order__vendor")
            .prefetch_related("order__items")
        )
        return Response(DeliveryAssignmentSerializer(pending_qs, many=True).data)


class AcceptAssignmentView(APIView):
    """POST /api/delivery/requests/<assignment_id>/accept/ — accept an assignment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        """Accept a delivery assignment request.

        Args:
            request: Authenticated DRF request from a delivery partner.
            assignment_id: UUID primary key of the assignment.

        Returns:
            200 with ``{status, order}`` data, or 404/409 on error.
        """
        try:
            order = DeliveryService.accept_assignment(str(assignment_id), request.user)
            return Response({"status": "accepted", "order": OrderSerializer(order).data})
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)


class RejectAssignmentView(APIView):
    """POST /api/delivery/requests/<assignment_id>/reject/ — reject an assignment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        """Reject a delivery assignment request.

        If all notified partners have rejected, immediately expands the search
        radius and retries.

        Args:
            request: Authenticated DRF request from a delivery partner.
            assignment_id: UUID primary key of the assignment.

        Returns:
            200 with ``{"status": "rejected"}``, or 404.
        """
        partner = request.user.delivery_profile
        try:
            assignment = DeliveryAssignment.objects.prefetch_related(
                "notified_partners", "rejected_partners"
            ).get(id=assignment_id, notified_partners=partner)
        except DeliveryAssignment.DoesNotExist:
            return Response(
                {"error": "Request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if assignment.status in ("accepted", "cancelled", "failed"):
            return Response({"status": "ok"})

        assignment.rejected_partners.add(partner)

        if assignment.rejected_partners.count() >= assignment.notified_partners.count():
            _expand_and_retry(assignment)

        return Response({"status": "rejected"})


class CancelAssignmentView(APIView):
    """POST /api/delivery/<pk>/cancel-assignment/ — accepted partner cancels their assignment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Cancel an accepted delivery assignment.

        Args:
            request: Authenticated DRF request from a delivery partner.
            pk: UUID primary key of the order.

        Returns:
            200 with ``{"status": "cancelled"}``, or 404 on error.
        """
        try:
            DeliveryService.cancel_assignment(str(pk), request.user)
            return Response({"status": "cancelled"})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------

class StandardPagination(PageNumberPagination):
    """Default pagination for admin delivery list views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminDeliveryPartnerListView(APIView):
    """GET/POST /api/admin/delivery-partners/ — list or create delivery partners."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, optionally filtered list of delivery partners.

        Query params:
            search: Filter by username, email, or first name.
            is_approved: Filter by approval status (true/false).
            status: Filter by partner status string.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated list of delivery partner objects.
        """
        qs = DeliveryPartner.objects.select_related("user").order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            qs = (
                qs.filter(user__username__icontains=search)
                | DeliveryPartner.objects.filter(user__email__icontains=search)
                | DeliveryPartner.objects.filter(user__first_name__icontains=search)
            ).distinct()

        is_approved = request.query_params.get("is_approved")
        if is_approved is not None:
            qs = qs.filter(is_approved=is_approved.lower() == "true")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliveryPartnerSerializer(page, many=True).data
        )

    def post(self, request):
        """Create a new delivery partner account.

        Args:
            request: Authenticated admin DRF request with partner registration data.

        Returns:
            201 with partner data, including ``temp_password`` when auto-generated.
        """
        serializer = DeliveryPartnerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        data = DeliveryPartnerSerializer(partner).data
        if hasattr(partner, "auto_generated_password"):
            data["temp_password"] = partner.auto_generated_password
        return Response(data, status=status.HTTP_201_CREATED)


class AdminDeliveryPartnerDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/delivery-partners/<pk>/ — manage a single partner."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_partner(self, pk):
        """Look up a delivery partner by PK.

        Args:
            pk: UUID primary key of the partner.

        Returns:
            The ``DeliveryPartner`` instance or ``None``.
        """
        try:
            return DeliveryPartner.objects.select_related("user").get(pk=pk)
        except DeliveryPartner.DoesNotExist:
            return None

    def get(self, request, pk):  # noqa: ARG002
        """Return a single delivery partner's details.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the partner.

        Returns:
            200 with partner data, or 404.
        """
        partner = self._get_partner(pk)
        if not partner:
            return Response(
                {"error": "Delivery partner not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(DeliveryPartnerSerializer(partner).data)

    def patch(self, request, pk):
        """Partially update a delivery partner's profile.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key of the partner.

        Returns:
            200 with updated partner data, or 400/404.
        """
        partner = self._get_partner(pk)
        if not partner:
            return Response(
                {"error": "Delivery partner not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DeliveryPartnerSerializer(partner, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a delivery partner account.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the partner.

        Returns:
            204 on success, or 404.
        """
        partner = self._get_partner(pk)
        if not partner:
            return Response(
                {"error": "Delivery partner not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        partner.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminDeliveryPartnerEarningsCalculationView(APIView):
    """GET /api/admin/delivery-partners/<pk>/calculate-earnings/ — earnings for a date range."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        """Return total earnings and delivery count for a partner within a date range.

        Query params:
            start_date: ISO date string (inclusive).
            end_date: ISO date string (inclusive).

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the delivery partner.

        Returns:
            200 with ``total_amount`` and ``total_deliveries``, or 404.
        """
        try:
            partner = DeliveryPartner.objects.get(pk=pk)
        except DeliveryPartner.DoesNotExist:
            return Response(
                {"error": "Delivery partner not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        qs = DeliveryEarning.objects.filter(delivery_partner=partner)
        if start_date:
            qs = qs.filter(created_at__gte=start_date + "T00:00:00Z")
        if end_date:
            qs = qs.filter(created_at__lte=end_date + "T23:59:59Z")

        total = qs.aggregate(total_amount=Sum("amount"))["total_amount"] or 0
        return Response(
            {
                "total_amount": float(total),
                "total_deliveries": qs.count(),
            }
        )


class AdminDeliveryPartnerApprovalView(APIView):
    """POST /api/admin/delivery-partners/<pk>/approve/ — approve or reject a partner."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Set a delivery partner's approval status.

        Args:
            request: Authenticated admin DRF request with ``action``
                (``'approve'`` or ``'reject'``).
            pk: UUID primary key of the delivery partner.

        Returns:
            200 with updated partner data, or 400/404.
        """
        try:
            partner = DeliveryPartner.objects.get(pk=pk)
        except DeliveryPartner.DoesNotExist:
            return Response(
                {"error": "Delivery partner not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        action = request.data.get("action")
        if action == "approve":
            partner.is_approved = True
            partner.status = "available"
            partner.save(update_fields=["is_approved", "status", "updated_at"])
            return Response({"status": "approved", **DeliveryPartnerSerializer(partner).data})
        elif action == "reject":
            partner.is_approved = False
            partner.status = "offline"
            partner.save(update_fields=["is_approved", "status", "updated_at"])
            return Response({"status": "rejected", **DeliveryPartnerSerializer(partner).data})
        else:
            return Response(
                {"error": "action must be 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AdminAssetListCreateView(APIView):
    """GET/POST /api/admin/assets/ — list or create platform assets."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, optionally filtered list of assets.

        Query params:
            type: Filter by asset type.
            status: Filter by asset status.
            assigned_to: Filter by assigned delivery partner UUID.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated list of asset objects.
        """
        qs = Asset.objects.select_related("assigned_to__user").order_by("-created_at")
        asset_type = request.query_params.get("type")
        if asset_type:
            qs = qs.filter(asset_type=asset_type)
        asset_status = request.query_params.get("status")
        if asset_status:
            qs = qs.filter(status=asset_status)
        assigned_to = request.query_params.get("assigned_to")
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AssetSerializer(page, many=True).data)

    def post(self, request):
        """Create a new platform asset.

        Args:
            request: Authenticated admin DRF request with asset payload.

        Returns:
            201 with the new asset data, or 400.
        """
        serializer = AssetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminAssetDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/assets/<pk>/ — manage a single asset."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_asset(self, pk):
        """Look up an asset by PK.

        Args:
            pk: UUID primary key of the asset.

        Returns:
            The ``Asset`` instance or ``None``.
        """
        try:
            return Asset.objects.select_related("assigned_to__user").get(pk=pk)
        except Asset.DoesNotExist:
            return None

    def get(self, request, pk):  # noqa: ARG002
        """Return a single asset.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the asset.

        Returns:
            200 with asset data, or 404.
        """
        asset = self._get_asset(pk)
        if not asset:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AssetSerializer(asset).data)

    def patch(self, request, pk):
        """Partially update an asset.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key of the asset.

        Returns:
            200 with updated asset data, or 400/404.
        """
        asset = self._get_asset(pk)
        if not asset:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssetSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):  # noqa: ARG002
        """Delete an asset.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the asset.

        Returns:
            204 on success, or 404.
        """
        asset = self._get_asset(pk)
        if not asset:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
