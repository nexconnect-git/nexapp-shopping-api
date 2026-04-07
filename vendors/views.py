"""
API views for the ``vendors`` app.

Endpoints covered:
  - Vendor registration, public list, and detail
  - Vendor dashboard, store status, and bulk stock updates
  - Vendor product management (ViewSet)
  - Vendor order management and OTP verification
  - Vendor profile management
  - Nearby vendors (geo-search)
  - Admin: vendor CRUD, status changes, KYC review
  - Admin: onboarding, bank details, documents, serviceable areas, holidays
  - Admin: audit logs, sales reports
  - Payout management (vendor, delivery partner, and admin sides)
  - Vendor coupon management
"""

import random
from decimal import Decimal
from datetime import datetime, timedelta

from django.db import models as db_models, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.permissions import IsAdminRole, IsApprovedVendor, IsVendor
from accounts.serializers import UserProfileSerializer
from backend.utils import haversine
from delivery.models import DeliveryAssignment
from delivery.tasks import search_and_notify_partners
from notifications.models import Notification
from orders.models import Coupon, Order, OrderItem, OrderTracking
from orders.serializers import CouponSerializer, OrderSerializer
from products.models import Product
from products.serializers import ProductCreateUpdateSerializer, ProductSerializer
from vendors.models import (
    DeliveryPartnerPayout,
    Vendor,
    VendorAuditLog,
    VendorBankDetails,
    VendorDocument,
    VendorHoliday,
    VendorOnboarding,
    VendorPayout,
    VendorReview,
    VendorServiceableArea,
)
from vendors.serializers import (
    AdminVendorSerializer,
    DeliveryPartnerPayoutSerializer,
    DocumentVerifySerializer,
    VendorBankDetailsSerializer,
    VendorDocumentSerializer,
    VendorFullOnboardSerializer,
    VendorHolidaySerializer,
    VendorListSerializer,
    VendorOnboardingSerializer,
    VendorPayoutSerializer,
    VendorRegistrationSerializer,
    VendorReviewSerializer,
    VendorSerializer,
    VendorServiceableAreaSerializer,
)
from vendors.services import VendorService


# ---------------------------------------------------------------------------
# Public vendor views
# ---------------------------------------------------------------------------

class VendorRegistrationView(APIView):
    """POST /api/vendors/register/ — create a new vendor account."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new vendor and return profile, vendor data, and JWT tokens.

        Args:
            request: DRF request containing registration payload.

        Returns:
            201 response with user, vendor, status, and access/refresh tokens.
        """
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        refresh = RefreshToken.for_user(vendor.user)
        return Response(
            {
                "user": UserProfileSerializer(vendor.user).data,
                "vendor": VendorSerializer(vendor).data,
                "vendor_status": vendor.status,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VendorListView(generics.ListAPIView):
    """GET /api/vendors/ — publicly list all approved vendors."""

    permission_classes = [AllowAny]
    serializer_class = VendorListSerializer

    def get_queryset(self):
        """Return approved vendors filtered by optional query params.

        Query params:
            search: Filter by store name.
            city: Filter by city (case-insensitive).
            is_open: Filter by open/closed status (true/false).
            is_featured: Filter by featured flag (true/false).
            category: Filter by product category or parent category slug.

        Returns:
            Filtered queryset of approved vendors.
        """
        qs = Vendor.objects.filter(status="approved")
        search = self.request.query_params.get("search")
        city = self.request.query_params.get("city")
        is_open = self.request.query_params.get("is_open")
        is_featured = self.request.query_params.get("is_featured")
        category = self.request.query_params.get("category")

        if search:
            qs = qs.filter(store_name__icontains=search)
        if city:
            qs = qs.filter(city__iexact=city)
        if is_open is not None:
            qs = qs.filter(is_open=is_open.lower() == "true")
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured.lower() == "true")
        if category:
            qs = qs.filter(
                Q(products__category__slug=category)
                | Q(products__category__parent__slug=category)
            ).distinct()
        return qs


class VendorDetailView(generics.RetrieveAPIView):
    """GET /api/vendors/<uuid>/ — publicly retrieve an approved vendor with products."""

    permission_classes = [AllowAny]
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(status="approved")

    def retrieve(self, request, *args, **kwargs):  # noqa: ARG002
        """Return vendor detail plus all available products.

        Args:
            request: DRF request (unauthenticated allowed).
            *args: Positional arguments passed by DRF router.
            **kwargs: Keyword arguments including ``pk``.

        Returns:
            200 with vendor data and nested ``products`` list.
        """
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor).data
        available_products = Product.objects.filter(vendor=vendor, is_available=True)
        vendor_data["products"] = ProductSerializer(available_products, many=True).data
        return Response(vendor_data)


class NearbyVendorsView(APIView):
    """GET /api/vendors/nearby/ — list approved vendors within a radius."""

    permission_classes = [AllowAny]

    def get(self, request):
        """Return vendors within ``radius_km`` of the given coordinates.

        Query params:
            lat: Latitude of the origin point (required).
            lng: Longitude of the origin point (required).
            radius_km: Search radius in kilometres (default: 5).
            category: Filter by product category or parent category slug.

        Args:
            request: DRF request with geo query params.

        Returns:
            200 with a list of vendor data dicts including ``distance_km``,
            sorted by distance ascending.
            400 if ``lat`` or ``lng`` are missing or non-numeric.
        """
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return Response(
                {"error": "lat and lng query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        radius_km = float(request.query_params.get("radius_km", 5))
        vendors = Vendor.objects.filter(status="approved")
        category = request.query_params.get("category")
        if category:
            vendors = vendors.filter(
                Q(products__category__slug=category)
                | Q(products__category__parent__slug=category)
            ).distinct()

        nearby = []
        for vendor in vendors:
            distance = haversine(
                lat, lng, float(vendor.latitude), float(vendor.longitude)
            )
            if distance <= radius_km:
                vendor_data = VendorListSerializer(vendor).data
                vendor_data["distance_km"] = round(distance, 2)
                nearby.append(vendor_data)

        nearby.sort(key=lambda v: v["distance_km"])
        return Response(nearby)


# ---------------------------------------------------------------------------
# Authenticated vendor views
# ---------------------------------------------------------------------------

class VendorProfileView(APIView):
    """GET/PATCH /api/vendors/profile/ — authenticated vendor's own profile."""

    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """Return the current vendor's profile.

        Args:
            request: Authenticated DRF request from a vendor user.

        Returns:
            200 with serialised vendor profile.
        """
        return Response(VendorSerializer(request.user.vendor_profile).data)

    def patch(self, request):
        """Partially update the current vendor's profile.

        Args:
            request: Authenticated DRF request with fields to update.

        Returns:
            200 with updated vendor profile data.
        """
        serializer = VendorSerializer(
            request.user.vendor_profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class VendorDashboardView(APIView):
    """GET /api/vendors/dashboard/ — approved vendor's dashboard summary."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        """Return order counts, product counts, ratings, and low-stock info.

        Args:
            request: Authenticated DRF request from an approved vendor.

        Returns:
            200 with dashboard statistics and recent orders.
        """
        vendor = request.user.vendor_profile
        total_orders = Order.objects.filter(vendor=vendor).count()
        total_products = Product.objects.filter(vendor=vendor).count()
        recent_orders = Order.objects.filter(vendor=vendor).order_by("-placed_at")[:10]

        low_stock = Product.objects.filter(
            vendor=vendor,
            stock__lte=db_models.F("low_stock_threshold"),
            low_stock_threshold__gt=0,
        )

        return Response(
            {
                "total_orders": total_orders,
                "total_products": total_products,
                "average_rating": vendor.average_rating,
                "total_ratings": vendor.total_ratings,
                "recent_orders": OrderSerializer(recent_orders, many=True).data,
                "is_open": vendor.is_open,
                "closing_time": str(vendor.closing_time) if vendor.closing_time else None,
                "require_stock_check": vendor.require_stock_check,
                "low_stock_count": low_stock.count(),
                "low_stock_products": ProductSerializer(low_stock, many=True).data,
            }
        )


class SetStoreStatusView(APIView):
    """POST /api/vendors/store-status/ — toggle the vendor's store open/closed."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        """Open or close the vendor's store.

        Args:
            request: Authenticated DRF request with ``is_open`` (bool)
                and ``closing_time`` (e.g. ``"22:00"``) when opening.

        Returns:
            200 with updated ``is_open`` and ``closing_time`` values.
            400 if ``is_open=true`` but ``closing_time`` is missing.
        """
        vendor = request.user.vendor_profile
        is_open = request.data.get("is_open")
        closing_time = request.data.get("closing_time")

        if is_open:
            if not closing_time:
                return Response(
                    {"error": "closing_time is required when opening the store."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            vendor.is_open = True
            vendor.closing_time = closing_time
            vendor.save(update_fields=["is_open", "closing_time", "updated_at"])
        else:
            vendor.is_open = False
            vendor.save(update_fields=["is_open", "updated_at"])

        return Response(
            {
                "is_open": vendor.is_open,
                "closing_time": str(vendor.closing_time) if vendor.closing_time else None,
            }
        )


class BulkUpdateStockView(APIView):
    """POST /api/vendors/bulk-update-stock/ — update multiple product stock levels."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        """Update stock for multiple products in a single request.

        Args:
            request: Authenticated DRF request with ``updates`` list of
                ``{id, stock}`` dicts.

        Returns:
            200 with ``updated`` (list of updated product IDs) and
            ``errors`` (list of IDs that failed).
        """
        vendor = request.user.vendor_profile
        updates = request.data.get("updates", [])

        if not isinstance(updates, list):
            return Response(
                {"error": "updates must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = []
        errors = []
        for entry in updates:
            product_id = entry.get("id")
            new_stock = entry.get("stock")
            if product_id is None or new_stock is None:
                continue
            try:
                product = Product.objects.get(pk=product_id, vendor=vendor)
                product.stock = max(0, int(new_stock))
                product.save(update_fields=["stock"])
                updated.append(str(product.id))
            except (Product.DoesNotExist, ValueError):
                errors.append(str(product_id))

        return Response({"updated": updated, "errors": errors})


class VendorProductViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor's own product management."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get_serializer_class(self):
        """Return write serializer on mutations, read serializer otherwise."""
        if self.action in ("create", "update", "partial_update"):
            return ProductCreateUpdateSerializer
        return ProductSerializer

    def get_queryset(self):
        """Return products belonging to the requesting vendor."""
        return Product.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_create(self, serializer):
        """Attach the requesting vendor to the new product."""
        serializer.save(vendor=self.request.user.vendor_profile)


class VendorOrdersView(generics.ListAPIView):
    """GET /api/vendors/orders/ — list orders for the approved vendor."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Return vendor's orders, optionally filtered by status.

        Query params:
            status: Filter by order status string.

        Returns:
            Filtered queryset of vendor orders.
        """
        qs = Order.objects.filter(vendor=self.request.user.vendor_profile)
        order_status = self.request.query_params.get("status")
        if order_status:
            qs = qs.filter(status=order_status)
        return qs


class VendorOrderDetailView(generics.RetrieveAPIView):
    """GET /api/vendors/orders/<pk>/ — retrieve a single vendor order."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Return vendor orders with items and tracking prefetched."""
        return Order.objects.filter(
            vendor=self.request.user.vendor_profile
        ).prefetch_related("items", "tracking")


class VendorUpdateOrderStatusView(APIView):
    """PATCH /api/vendors/orders/<pk>/status/ — advance or cancel an order."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        """Transition an order to a new status.

        Allowed transitions:
            placed → confirmed, cancelled
            confirmed → preparing, cancelled
            preparing → ready

        When transitioning to ``ready``, a delivery OTP is generated and
        a background task is dispatched to find a delivery partner.

        Args:
            request: Authenticated DRF request with ``status`` and optionally
                ``cancel_reason``.
            pk: UUID primary key of the order.

        Returns:
            200 with updated order data, or 400/404 on error.
        """
        try:
            order = Order.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        cancel_reason = (request.data.get("cancel_reason") or "").strip()

        allowed_transitions = {
            "placed": ["confirmed", "cancelled"],
            "confirmed": ["preparing", "cancelled"],
            "preparing": ["ready"],
        }
        current_allowed = allowed_transitions.get(order.status, [])
        if new_status not in current_allowed:
            return Response(
                {"error": f"Cannot transition from '{order.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == "cancelled" and not cancel_reason:
            return Response(
                {"error": "A cancellation reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == "ready":
            order.delivery_otp = str(random.randint(100000, 999999))

        order.status = new_status
        order.save(update_fields=["status", "delivery_otp", "updated_at"])

        description_map = {
            "confirmed": "Order confirmed by vendor.",
            "preparing": "Order is being prepared.",
            "ready": "Order is ready for pickup by delivery partner.",
            "cancelled": (
                f"Order cancelled by vendor. Reason: {cancel_reason}"
                if cancel_reason
                else "Order was cancelled by vendor."
            ),
        }
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=description_map.get(new_status, f"Order {new_status} by vendor."),
        )

        status_messages = {
            "confirmed": "Your order has been confirmed by the vendor.",
            "preparing": "Your order is being prepared.",
            "ready": "Your order is ready! A delivery partner will pick it up soon.",
            "cancelled": (
                f"Your order #{order.order_number} was cancelled by the vendor."
                f" Reason: {cancel_reason}"
                if cancel_reason
                else f"Your order #{order.order_number} was cancelled by the vendor."
            ),
        }
        Notification.objects.create(
            user=order.customer,
            title=f"Order {new_status.capitalize()}",
            message=status_messages.get(new_status, f"Your order status is now {new_status}."),
            notification_type="order",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        if new_status == "ready":
            assignment, _ = DeliveryAssignment.objects.get_or_create(order=order)
            assignment.status = "searching"
            assignment.save(update_fields=["status", "updated_at"])
            search_and_notify_partners.delay(str(assignment.id))

        return Response(OrderSerializer(order).data)


class VendorVerifyPickupOtpView(APIView):
    """POST /api/vendors/orders/<pk>/verify-pickup-otp/ — verify delivery partner's pickup OTP."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        """Verify the pickup OTP and mark the order as picked up.

        Args:
            request: Authenticated DRF request with ``otp`` field.
            pk: UUID primary key of the order.

        Returns:
            200 with updated order data, or 400/404 on error.
        """
        try:
            order = Order.objects.get(
                pk=pk, vendor=request.user.vendor_profile, status="ready"
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or not in ready status."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not order.delivery_partner:
            return Response(
                {"error": "No delivery partner assigned yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submitted_otp = str(request.data.get("otp", "")).strip()
        if not submitted_otp:
            return Response(
                {"error": "OTP is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.pickup_otp != submitted_otp:
            return Response(
                {"error": "Invalid OTP. Please ask the delivery partner to check again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "picked_up"
        order.save(update_fields=["status", "updated_at"])

        partner = order.delivery_partner.delivery_profile
        OrderTracking.objects.create(
            order=order,
            status="picked_up",
            description="Order picked up — pickup OTP verified by vendor.",
            latitude=partner.current_latitude,
            longitude=partner.current_longitude,
        )

        Notification.objects.create(
            user=order.customer,
            title="Order Picked Up",
            message=f"Your order #{order.order_number} has been picked up and is on its way!",
            notification_type="delivery",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        return Response(OrderSerializer(order).data)


class VendorRetriggerPickupView(APIView):
    """POST /api/vendors/orders/<pk>/retrigger-pickup/ — restart delivery partner search."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):  # noqa: ARG002
        """Reset a timed-out delivery assignment and restart partner search.

        Args:
            request: Authenticated DRF request (no body required).
            pk: UUID primary key of the order.

        Returns:
            200 with order data, or 400/404 on error.
        """
        try:
            order = Order.objects.get(
                pk=pk, vendor=request.user.vendor_profile, status="ready"
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or not in ready status."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.delivery_partner:
            return Response(
                {"error": "A delivery partner is already assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, _ = DeliveryAssignment.objects.get_or_create(order=order)

        if assignment.status == "accepted":
            return Response(
                {"error": "Assignment already accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.status = "searching"
        assignment.current_radius_km = 2.0
        assignment.last_search_at = timezone.now()
        assignment.save(update_fields=["status", "current_radius_km", "last_search_at", "updated_at"])
        assignment.notified_partners.clear()
        assignment.rejected_partners.clear()

        search_and_notify_partners.delay(str(assignment.id))

        Notification.objects.create(
            user=order.vendor.user,
            title="Searching for Delivery Partner",
            message=f"Looking for a delivery partner for Order #{order.order_number}...",
            notification_type="delivery",
            data={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "type": "assignment_searching",
            },
        )

        return Response(OrderSerializer(order).data)


# ---------------------------------------------------------------------------
# Admin vendor views
# ---------------------------------------------------------------------------

class AdminVendorListView(APIView):
    """GET/POST /api/admin/vendors/ — list all vendors or create one (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, optionally filtered list of all vendors.

        Query params:
            search: Filter by store name or city.
            status: Filter by vendor status.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated list of vendor objects.
        """
        qs = Vendor.objects.select_related("user").order_by("-created_at")
        search = request.query_params.get("search")
        if search:
            qs = (
                qs.filter(store_name__icontains=search)
                | Vendor.objects.filter(city__icontains=search)
            ).distinct()

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminVendorSerializer(page, many=True).data
        )

    def post(self, request):
        """Create a new vendor (user + vendor profile) as admin.

        Args:
            request: Authenticated admin DRF request with vendor registration data.

        Returns:
            201 with the new vendor's data.
        """
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        return Response(AdminVendorSerializer(vendor).data, status=status.HTTP_201_CREATED)


class AdminVendorDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/vendors/<pk>/ — manage a single vendor."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_vendor(self, pk):
        """Look up a vendor by PK.

        Args:
            pk: UUID primary key of the vendor.

        Returns:
            The ``Vendor`` instance or ``None``.
        """
        return VendorService.get_vendor_or_none(pk)

    def get(self, request, pk):  # noqa: ARG002
        """Return a single vendor's details.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with vendor data, or 404.
        """
        vendor = self._get_vendor(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(AdminVendorSerializer(vendor).data)

    def patch(self, request, pk):
        """Partially update a vendor's profile.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated vendor data, or 400/404.
        """
        vendor = self._get_vendor(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = AdminVendorSerializer(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a vendor account.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            204 on success, or 404.
        """
        vendor = self._get_vendor(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        vendor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorStatusView(APIView):
    """POST /api/admin/vendors/<pk>/status/ — approve, reject, or suspend a vendor."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Change the approval status of a vendor.

        Args:
            request: Authenticated admin DRF request with ``status`` field.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated vendor data, or 400/404 on error.
        """
        try:
            vendor = VendorService.update_vendor_status(
                str(pk), request.data.get("status")
            )
            return Response(VendorSerializer(vendor).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response(
                    {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
                )
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VendorReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor reviews — list, create, update, delete."""

    serializer_class = VendorReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return reviews for a specific vendor, or all reviews.

        Returns:
            Queryset filtered by ``vendor_id`` URL kwarg when present.
        """
        vendor_id = self.kwargs.get("vendor_id")
        if vendor_id:
            return VendorReview.objects.filter(vendor_id=vendor_id)
        return VendorReview.objects.all()

    def perform_create(self, serializer):
        """Attach the requesting user as the review's customer."""
        serializer.save(customer=self.request.user)


# ---------------------------------------------------------------------------
# Admin onboarding views
# ---------------------------------------------------------------------------

class AdminVendorOnboardView(APIView):
    """POST /api/admin/vendors/onboard/ — full vendor creation with all details."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        """Create a vendor account with onboarding, bank, areas, and holidays in one call.

        Args:
            request: Authenticated admin DRF request with full onboarding payload.

        Returns:
            201 with vendor data, including ``temp_password`` when auto-generated.
        """
        serializer = VendorFullOnboardSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        data = AdminVendorSerializer(vendor).data
        if hasattr(vendor, "auto_generated_password"):
            data["temp_password"] = vendor.auto_generated_password
        return Response(data, status=status.HTTP_201_CREATED)


class AdminVendorOnboardingDetailView(APIView):
    """GET/PATCH /api/admin/vendors/<pk>/onboarding/ — view or update onboarding details."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return the vendor's onboarding record.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with onboarding data, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)
        return Response(VendorOnboardingSerializer(onboarding).data)

    def patch(self, request, pk):
        """Partially update onboarding details and log the change.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated onboarding data, or 400/404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)
        serializer = VendorOnboardingSerializer(
            onboarding, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        VendorService._create_audit_log(
            vendor, "profile_updated", "Onboarding details updated.", request
        )
        return Response(serializer.data)


class AdminVendorKYCReviewView(APIView):
    """POST /api/admin/vendors/<pk>/kyc-review/ — approve or reject vendor KYC."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Approve or reject a vendor's KYC submission.

        Args:
            request: Authenticated admin DRF request with ``action``
                (``'approve'`` or ``'reject'``) and optional ``rejection_reason``.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated onboarding data, or 400/404 on error.
        """
        action = request.data.get("action")
        reason = request.data.get("rejection_reason", "")
        try:
            onboarding = VendorService.review_vendor_kyc(
                str(pk), action, reason, request.user, request
            )
            return Response(VendorOnboardingSerializer(onboarding).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response(
                    {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
                )
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminVendorBankDetailsView(APIView):
    """GET/PUT /api/admin/vendors/<pk>/bank/ — view or update vendor bank details."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return the vendor's bank details.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with bank details, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        bank, _ = VendorBankDetails.objects.get_or_create(vendor=vendor)
        return Response(VendorBankDetailsSerializer(bank).data)

    def put(self, request, pk):
        """Create or fully replace vendor bank details and log the change.

        Args:
            request: Authenticated admin DRF request with bank detail fields.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated bank details, or 400/404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        bank, created = VendorBankDetails.objects.get_or_create(vendor=vendor)
        serializer = VendorBankDetailsSerializer(
            bank, data=request.data, partial=not created
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        VendorService._create_audit_log(
            vendor, "bank_updated", "Bank details updated.", request
        )
        return Response(serializer.data)


class AdminVendorBankVerifyView(APIView):
    """POST /api/admin/vendors/<pk>/bank/verify/ — mark vendor bank details as verified."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Set ``is_verified=True`` on the vendor's bank details.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with updated bank details, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            bank = vendor.bank_details
        except VendorBankDetails.DoesNotExist:
            return Response(
                {"error": "Bank details not found."}, status=status.HTTP_404_NOT_FOUND
            )
        bank.is_verified = True
        bank.save(update_fields=["is_verified"])
        VendorService._create_audit_log(
            vendor, "bank_verified", "Bank details verified.", request
        )
        return Response(VendorBankDetailsSerializer(bank).data)


class AdminVendorDocumentListView(APIView):
    """GET/POST /api/admin/vendors/<pk>/documents/ — list or upload vendor documents."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):  # noqa: ARG002
        """Return all documents uploaded for a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with list of document objects, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        docs = VendorDocument.objects.filter(vendor=vendor)
        return Response(VendorDocumentSerializer(docs, many=True).data)

    def post(self, request, pk):
        """Upload a new document for a vendor and log the action.

        Args:
            request: Authenticated admin DRF request with document payload.
            pk: UUID primary key of the vendor.

        Returns:
            201 with the new document data, or 400/404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = VendorDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=vendor)
        VendorService._create_audit_log(
            vendor,
            "document_uploaded",
            f"Document uploaded: {serializer.instance.get_document_type_display()}",
            request,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminVendorDocumentVerifyView(APIView):
    """POST /api/admin/vendors/<pk>/documents/<doc_pk>/verify/ — verify or reject a document."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk, doc_pk):
        """Approve or reject a vendor's uploaded document.

        Args:
            request: Authenticated admin DRF request with ``action``
                (``'verify'`` or ``'reject'``) and optional ``rejection_reason``.
            pk: UUID primary key of the vendor.
            doc_pk: UUID primary key of the document.

        Returns:
            200 with updated document data, or 400/404 on error.
        """
        serializer = DocumentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            doc = VendorService.verify_document(
                str(pk),
                str(doc_pk),
                serializer.validated_data["action"],
                serializer.validated_data.get("rejection_reason", ""),
                request.user,
                request,
            )
            return Response(VendorDocumentSerializer(doc).data)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response(
                    {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
                )
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminVendorServiceableAreaView(APIView):
    """GET/POST /api/admin/vendors/<pk>/serviceable-areas/ — manage vendor serviceable areas."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return all serviceable pincodes for a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with list of serviceable area objects, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        areas = VendorServiceableArea.objects.filter(vendor=vendor)
        return Response(VendorServiceableAreaSerializer(areas, many=True).data)

    def post(self, request, pk):
        """Add a serviceable pincode to a vendor and log the action.

        Args:
            request: Authenticated admin DRF request with pincode, city, state.
            pk: UUID primary key of the vendor.

        Returns:
            201 (created) or 200 (already exists) with area data, or 400/404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = VendorServiceableAreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, created = VendorServiceableArea.objects.get_or_create(
            vendor=vendor,
            pincode=serializer.validated_data["pincode"],
            defaults={
                "city": serializer.validated_data.get("city", ""),
                "state": serializer.validated_data.get("state", ""),
            },
        )
        if created:
            VendorService._create_audit_log(
                vendor,
                "serviceable_area_added",
                f"Pincode {obj.pincode} added.",
                request,
            )
        return Response(
            VendorServiceableAreaSerializer(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminVendorServiceableAreaDetailView(APIView):
    """DELETE /api/admin/vendors/<pk>/serviceable-areas/<area_pk>/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk, area_pk):  # noqa: ARG002
        """Remove a serviceable pincode from a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.
            area_pk: UUID primary key of the serviceable area.

        Returns:
            204 on success, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            area = VendorServiceableArea.objects.get(pk=area_pk, vendor=vendor)
        except VendorServiceableArea.DoesNotExist:
            return Response(
                {"error": "Area not found."}, status=status.HTTP_404_NOT_FOUND
            )
        area.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorHolidayView(APIView):
    """GET/POST /api/admin/vendors/<pk>/holidays/ — manage vendor holidays."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return all declared holidays for a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with list of holiday objects, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        holidays = VendorHoliday.objects.filter(vendor=vendor)
        return Response(VendorHolidaySerializer(holidays, many=True).data)

    def post(self, request, pk):
        """Add a holiday date for a vendor and log the action.

        Args:
            request: Authenticated admin DRF request with ``date`` and optional ``reason``.
            pk: UUID primary key of the vendor.

        Returns:
            201 (created) or 200 (already exists) with holiday data, or 400/404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = VendorHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, created = VendorHoliday.objects.get_or_create(
            vendor=vendor,
            date=serializer.validated_data["date"],
            defaults={"reason": serializer.validated_data.get("reason", "")},
        )
        VendorService._create_audit_log(
            vendor, "holiday_added", f"Holiday on {obj.date} added.", request
        )
        return Response(
            VendorHolidaySerializer(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminVendorHolidayDetailView(APIView):
    """DELETE /api/admin/vendors/<pk>/holidays/<holiday_pk>/"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk, holiday_pk):  # noqa: ARG002
        """Delete a holiday entry for a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.
            holiday_pk: UUID primary key of the holiday.

        Returns:
            204 on success, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            holiday = VendorHoliday.objects.get(pk=holiday_pk, vendor=vendor)
        except VendorHoliday.DoesNotExist:
            return Response(
                {"error": "Holiday not found."}, status=status.HTTP_404_NOT_FOUND
            )
        holiday.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorAuditLogView(APIView):
    """GET /api/admin/vendors/<pk>/audit-logs/ — retrieve the audit log for a vendor."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return all audit log entries for a vendor.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with list of audit log entries, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )
        logs = VendorAuditLog.objects.filter(vendor=vendor)
        return Response(VendorAuditLogSerializer(logs, many=True).data)


class AdminVendorSalesReportView(APIView):
    """GET /api/admin/vendors/<pk>/sales-report/ — vendor sales analytics."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        """Return revenue, order counts, and top-product analytics for a vendor.

        Query params:
            period: ``30d`` (default), ``90d``, or ``12m``.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the vendor.

        Returns:
            200 with aggregated sales statistics, or 404.
        """
        vendor = VendorService.get_vendor_or_none(pk)
        if not vendor:
            return Response(
                {"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND
            )

        period = request.query_params.get("period", "30d")
        now = timezone.now()
        period_map = {"90d": timedelta(days=90), "12m": timedelta(days=365)}
        start_date = now - period_map.get(period, timedelta(days=30))

        orders = Order.objects.filter(vendor=vendor, placed_at__gte=start_date)

        total_revenue = (
            orders.exclude(status="cancelled").aggregate(rev=Sum("total"))["rev"] or 0
        )
        total_orders = orders.count()
        delivered_orders = orders.filter(status="delivered").count()
        cancelled_orders = orders.filter(status="cancelled").count()
        non_cancelled = total_orders - cancelled_orders
        avg_order_value = (
            float(total_revenue) / non_cancelled if non_cancelled > 0 else 0
        )

        orders_by_status = dict(
            orders.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        monthly_data = [
            {
                "month": entry["month"].strftime("%Y-%m"),
                "revenue": float(entry["revenue"] or 0),
                "orders": entry["order_count"],
            }
            for entry in (
                orders.exclude(status="cancelled")
                .annotate(month=TruncMonth("placed_at"))
                .values("month")
                .annotate(revenue=Sum("total"), order_count=Count("id"))
                .order_by("month")
            )
        ]

        top_products_data = [
            {
                "product_id": str(p["product_id"]),
                "name": p["product_name"],
                "total_sold": p["total_sold"],
                "revenue": float(p["revenue"] or 0),
            }
            for p in (
                OrderItem.objects.filter(
                    order__vendor=vendor, order__placed_at__gte=start_date
                )
                .exclude(order__status="cancelled")
                .values("product_id", "product_name")
                .annotate(total_sold=Sum("quantity"), revenue=Sum("subtotal"))
                .order_by("-revenue")[:10]
            )
        ]

        return Response(
            {
                "total_revenue": float(total_revenue),
                "total_orders": total_orders,
                "delivered_orders": delivered_orders,
                "cancelled_orders": cancelled_orders,
                "average_order_value": round(avg_order_value, 2),
                "orders_by_status": orders_by_status,
                "monthly_data": monthly_data,
                "top_products": top_products_data,
            }
        )


# ---------------------------------------------------------------------------
# Payout views — vendor payouts (admin side)
# ---------------------------------------------------------------------------

class VendorPayoutListView(generics.ListAPIView):
    """GET /api/vendors/payouts/ — list the current vendor's payouts."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        """Return payouts belonging to the requesting vendor."""
        return VendorPayout.objects.filter(vendor=self.request.user.vendor_profile)


class AdminVendorPayoutListView(generics.ListCreateAPIView):
    """GET/POST /api/admin/payouts/vendors/ — list or create vendor payouts (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        """Return all vendor payouts, optionally filtered by status or vendor.

        Query params:
            status: Filter by payout status.
            vendor_id: Filter by vendor UUID.

        Returns:
            Filtered queryset with ``vendor`` select_related.
        """
        qs = VendorPayout.objects.select_related("vendor").all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        vendor_id = self.request.query_params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        return qs

    def perform_create(self, serializer):
        """Calculate payout amounts, link delivered orders, and notify the vendor."""
        # The admin provides vendor, period_start, and period_end in the request.
        payout = serializer.save(status="pending_approval")

        # Period filtering: all delivered orders for this vendor in this period 
        # that haven't been linked to a payout yet.
        from orders.models import Order
        from django.db.models import Sum

        orders_to_payout = Order.objects.filter(
            vendor=payout.vendor,
            status="delivered",
            placed_at__gte=payout.period_start,
            placed_at__lte=payout.period_end,
            vendor_payout__isnull=True
        )

        total_orders = orders_to_payout.count()
        if total_orders > 0:
            # Calculate subtotal (Sales) and coupon_discount
            stats = orders_to_payout.aggregate(
                subtotal=Sum("subtotal"),
                discount=Sum("coupon_discount")
            )
            subtotal = stats["subtotal"] or Decimal("0.00")
            discount = stats["discount"] or Decimal("0.00")
            
            # Gross Sales = Sum of subtotals
            # Net Sales (Earnings for Vendor) = Sum(subtotal - discount)
            # Commission calculation (if any) should be done here.
            # For now, we use the formula: net_payout = subtotal - discount
            payout.gross_sales = subtotal
            payout.net_payout = subtotal - discount
            payout.platform_commission = Decimal("0.00") # Placeholder for commission logic
            payout.save(update_fields=["gross_sales", "net_payout", "platform_commission"])

            # Link orders to this payout
            orders_to_payout.update(vendor_payout=payout)

        Notification.objects.create(
            user=payout.vendor.user,
            title="Payout Initiated \u2014 Approval Required",
            message=(
                f"A payout of \u20b9{payout.net_payout} for the period "
                f"{payout.period_start.strftime('%b %d')} \u2013 "
                f"{payout.period_end.strftime('%b %d, %Y')} "
                f"has been initiated. Please review and approve it in your Payments section."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "approval_required"},
        )


class AdminVendorPayoutDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/admin/payouts/vendors/<pk>/ — manage a single vendor payout."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VendorPayoutSerializer
    queryset = VendorPayout.objects.all()


class AdminVendorPayoutScheduleView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/schedule/ — advance an approved payout to scheduled."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):  # noqa: ARG002
        """Move an approved vendor payout to ``scheduled`` status.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "approved":
            return Response(
                {"error": "Only approved payouts can be scheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payout.status = "scheduled"
        payout.save(update_fields=["status"])
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutSendPaymentView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/send-payment/ — mark payment as dispatched."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Mark a scheduled vendor payout as paid and notify the vendor to verify.

        Args:
            request: Authenticated admin DRF request with optional
                ``transaction_ref`` field.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "scheduled":
            return Response(
                {"error": "Only scheduled payouts can be marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "paid"
        payout.payment_sent_at = timezone.now()
        payout.transaction_ref = request.data.get("transaction_ref", payout.transaction_ref)
        
        from django.db import transaction
        with transaction.atomic():
            payout.save(update_fields=["status", "payment_sent_at", "transaction_ref"])
            
            # Reduce Vendor Wallet balance upon payment
            vendor = payout.vendor
            vendor.wallet_balance -= payout.net_payout
            vendor.save(update_fields=["wallet_balance", "updated_at"])

        Notification.objects.create(
            user=payout.vendor.user,
            title="Payout Transferred \u2014 Please Verify",
            message=(
                f"Your payout of \u20b9{payout.net_payout} has been transferred to your bank account. "
                f"Please verify that you have received the credit within 2 days."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "verify_credit"},
        )
        return Response(VendorPayoutSerializer(payout).data)


class AdminVendorPayoutForcePaidView(APIView):
    """POST /api/admin/payouts/vendors/<pk>/force-paid/ — force-verify after 2-day timeout."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):  # noqa: ARG002
        """Override vendor verification when the 2-day window has expired.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "paid":
            return Response(
                {"error": "Override only available for dispatched payouts awaiting vendor verification."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not payout.payment_sent_at:
            return Response(
                {"error": "payment_sent_at is not set on this payout."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deadline = payout.payment_sent_at + timedelta(days=2)
        if timezone.now() < deadline:
            return Response(
                {
                    "error": (
                        f"Vendor verification window has not expired. "
                        f"Override available after {deadline.strftime('%b %d, %Y %H:%M UTC')}."
                    ),
                    "override_available_at": deadline.isoformat(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "verified"
        payout.vendor_verified_at = timezone.now()
        payout.paid_at = payout.vendor_verified_at
        payout.save(update_fields=["status", "vendor_verified_at", "paid_at"])

        Notification.objects.create(
            user=payout.vendor.user,
            title="Payout Verified by Platform",
            message=(
                f"Your payout of \u20b9{payout.net_payout} has been marked as verified by the platform "
                f"as the 2-day confirmation window expired."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "force_verified"},
        )
        return Response(VendorPayoutSerializer(payout).data)


# ---------------------------------------------------------------------------
# Payout views — vendor self-service
# ---------------------------------------------------------------------------

class VendorPayoutApproveView(APIView):
    """POST /api/vendors/payouts/<pk>/approve/ — vendor approves a payout."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        """Approve a pending payout and notify admins.

        Args:
            request: Authenticated DRF request from an approved vendor.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "pending_approval":
            return Response(
                {"error": "This payout is not awaiting your approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "approved"
        payout.vendor_approved_at = timezone.now()
        payout.save(update_fields=["status", "vendor_approved_at"])

        admin_users = User.objects.filter(role="admin", is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=admin,
                    title="Payout Approved by Vendor",
                    message=(
                        f"{request.user.vendor_profile.store_name} has approved payout of "
                        f"\u20b9{payout.net_payout}. You can now schedule it."
                    ),
                    notification_type="payout",
                    data={"payout_id": str(payout.id), "action": "approved"},
                )
                for admin in admin_users
            ]
        )
        return Response(VendorPayoutSerializer(payout).data)


class VendorPayoutDeclineView(APIView):
    """POST /api/vendors/payouts/<pk>/decline/ — vendor declines a payout."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        """Decline a pending payout with a reason.

        Args:
            request: Authenticated DRF request from an approved vendor,
                with optional ``reason`` field.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "pending_approval":
            return Response(
                {"error": "This payout is not awaiting your approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "failed"
        payout.vendor_rejection_reason = request.data.get("reason", "").strip()
        payout.save(update_fields=["status", "vendor_rejection_reason"])
        return Response(VendorPayoutSerializer(payout).data)


class VendorPayoutVerifyCreditView(APIView):
    """POST /api/vendors/payouts/<pk>/verify-credit/ — vendor confirms credit received."""

    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        """Confirm receipt of a paid payout and notify admins.

        Args:
            request: Authenticated DRF request from an approved vendor.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor=request.user.vendor_profile)
        except VendorPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "paid":
            return Response(
                {"error": "This payout is not awaiting credit verification."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "verified"
        payout.vendor_verified_at = timezone.now()
        payout.paid_at = payout.vendor_verified_at
        payout.save(update_fields=["status", "vendor_verified_at", "paid_at"])

        admin_users = User.objects.filter(role="admin", is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=admin,
                    title="Payout Verified by Vendor",
                    message=(
                        f"{request.user.vendor_profile.store_name} has confirmed receipt of "
                        f"payout \u20b9{payout.net_payout}."
                    ),
                    notification_type="payout",
                    data={"payout_id": str(payout.id), "action": "verified"},
                )
                for admin in admin_users
            ]
        )
        return Response(VendorPayoutSerializer(payout).data)


# ---------------------------------------------------------------------------
# Payout views — delivery partner payouts (admin side)
# ---------------------------------------------------------------------------

class AdminDeliveryPayoutListView(generics.ListCreateAPIView):
    """GET/POST /api/admin/payouts/delivery/ — list or create delivery partner payouts."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DeliveryPartnerPayoutSerializer

    def get_queryset(self):
        """Return all delivery partner payouts, optionally filtered.

        Query params:
            status: Filter by payout status.
            partner_id: Filter by delivery partner UUID.

        Returns:
            Filtered queryset with ``delivery_partner`` select_related.
        """
        qs = DeliveryPartnerPayout.objects.select_related("delivery_partner").all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        partner_id = self.request.query_params.get("partner_id")
        if partner_id:
            qs = qs.filter(delivery_partner_id=partner_id)
        return qs

    def perform_create(self, serializer):
        """Calculate delivery partner earnings, link delivered orders, and notify partner."""
        payout = serializer.save(status="scheduled")

        from orders.models import Order
        from django.db.models import Sum

        # Filter delivered orders for this partner in this period not yet linked to a payout
        orders_to_payout = Order.objects.filter(
            delivery_partner=payout.delivery_partner,
            status="delivered",
            placed_at__gte=payout.period_start,
            placed_at__lte=payout.period_end,
            delivery_payout__isnull=True
        )

        total_deliveries = orders_to_payout.count()
        if total_deliveries > 0:
            total_earnings = orders_to_payout.aggregate(Sum("delivery_fee"))["delivery_fee__sum"] or Decimal("0.00")
            
            payout.total_deliveries = total_deliveries
            payout.total_earnings = total_earnings
            payout.save(update_fields=["total_deliveries", "total_earnings"])

            # Link orders to this payout
            orders_to_payout.update(delivery_payout=payout)

        Notification.objects.create(
            user=payout.delivery_partner,
            title="Payout Scheduled",
            message=(
                f"A payout of \u20b9{payout.total_earnings} for {payout.total_deliveries} deliveries "
                f"({payout.period_start.strftime('%b %d')} \u2013 "
                f"{payout.period_end.strftime('%b %d, %Y')}) "
                f"has been scheduled by the admin."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "scheduled"},
        )


class AdminDeliveryPayoutDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/admin/payouts/delivery/<pk>/ — manage a delivery payout."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DeliveryPartnerPayoutSerializer
    queryset = DeliveryPartnerPayout.objects.all()


class AdminDeliveryPayoutScheduleView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/schedule/ — schedule a delivery payout."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):  # noqa: ARG002
        """Move a pending or approved delivery payout to ``scheduled`` status.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(pk=pk)
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status not in ("pending_approval", "approved"):
            return Response(
                {"error": "Only pending or approved payouts can be scheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payout.status = "scheduled"
        payout.save(update_fields=["status"])
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class AdminDeliveryPayoutSendPaymentView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/send-payment/ — dispatch delivery payout."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        """Mark a scheduled delivery payout as paid and notify the partner.

        Args:
            request: Authenticated admin DRF request with optional
                ``transaction_ref`` field.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(pk=pk)
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "scheduled":
            return Response(
                {"error": "Only scheduled payouts can be marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "paid"
        payout.payment_sent_at = timezone.now()
        payout.transaction_ref = request.data.get("transaction_ref", payout.transaction_ref)
        payout.save(update_fields=["status", "payment_sent_at", "transaction_ref"])

        Notification.objects.create(
            user=payout.delivery_partner,
            title="Payout Transferred \u2014 Please Verify",
            message=(
                f"Your payout of \u20b9{payout.total_earnings} has been transferred. "
                f"Please verify that you have received the credit within 2 days."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "verify_credit"},
        )
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class AdminDeliveryPayoutForcePaidView(APIView):
    """POST /api/admin/payouts/delivery/<pk>/force-paid/ — force-verify after 2-day timeout."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):  # noqa: ARG002
        """Override partner verification when the 2-day window has expired.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(pk=pk)
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "paid":
            return Response(
                {"error": "Override only available for dispatched payouts awaiting verification."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not payout.payment_sent_at:
            return Response(
                {"error": "payment_sent_at is not set."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deadline = payout.payment_sent_at + timedelta(days=2)
        if timezone.now() < deadline:
            return Response(
                {
                    "error": (
                        f"Verification window has not expired. "
                        f"Override available after {deadline.strftime('%b %d, %Y %H:%M UTC')}."
                    ),
                    "override_available_at": deadline.isoformat(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "verified"
        payout.partner_verified_at = timezone.now()
        payout.paid_at = payout.partner_verified_at
        payout.save(update_fields=["status", "partner_verified_at", "paid_at"])

        Notification.objects.create(
            user=payout.delivery_partner,
            title="Payout Verified by Platform",
            message=(
                f"Your payout of \u20b9{payout.total_earnings} has been marked as verified "
                f"by the platform as the 2-day confirmation window expired."
            ),
            notification_type="payout",
            data={"payout_id": str(payout.id), "action": "force_verified"},
        )
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


# ---------------------------------------------------------------------------
# Payout views — delivery partner self-service
# ---------------------------------------------------------------------------

class DeliveryPayoutListView(generics.ListAPIView):
    """GET /api/delivery/payouts/ — delivery partner's own payouts."""

    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryPartnerPayoutSerializer

    def get_queryset(self):
        """Return payouts for the requesting delivery partner."""
        return DeliveryPartnerPayout.objects.filter(delivery_partner=self.request.user)


class DeliveryPayoutApproveView(APIView):
    """POST /api/delivery/payouts/<pk>/approve/ — delivery partner approves a payout."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Approve a pending payout and notify admins.

        Args:
            request: Authenticated DRF request from a delivery partner.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(
                pk=pk, delivery_partner=request.user
            )
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "pending_approval":
            return Response(
                {"error": "This payout is not awaiting your approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "approved"
        payout.partner_approved_at = timezone.now()
        payout.save(update_fields=["status", "partner_approved_at"])

        partner_name = request.user.get_full_name() or request.user.username
        admin_users = User.objects.filter(role="admin", is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=admin,
                    title="Delivery Payout Approved",
                    message=(
                        f"{partner_name} has approved their payout of "
                        f"\u20b9{payout.total_earnings}. You can now schedule it."
                    ),
                    notification_type="payout",
                    data={"payout_id": str(payout.id), "action": "approved"},
                )
                for admin in admin_users
            ]
        )
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class DeliveryPayoutDeclineView(APIView):
    """POST /api/delivery/payouts/<pk>/decline/ — delivery partner declines a payout."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Decline a pending payout with an optional reason.

        Args:
            request: Authenticated DRF request from a delivery partner,
                with optional ``reason`` field.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(
                pk=pk, delivery_partner=request.user
            )
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "pending_approval":
            return Response(
                {"error": "This payout is not awaiting your approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "failed"
        payout.partner_rejection_reason = request.data.get("reason", "").strip()
        payout.save(update_fields=["status", "partner_rejection_reason"])
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


class DeliveryPayoutVerifyCreditView(APIView):
    """POST /api/delivery/payouts/<pk>/verify-credit/ — delivery partner confirms credit received."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Confirm receipt of a paid delivery payout and notify admins.

        Args:
            request: Authenticated DRF request from a delivery partner.
            pk: UUID primary key of the payout.

        Returns:
            200 with updated payout data, or 400/404.
        """
        try:
            payout = DeliveryPartnerPayout.objects.get(
                pk=pk, delivery_partner=request.user
            )
        except DeliveryPartnerPayout.DoesNotExist:
            return Response(
                {"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if payout.status != "paid":
            return Response(
                {"error": "This payout is not awaiting credit verification."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout.status = "verified"
        payout.partner_verified_at = timezone.now()
        payout.paid_at = payout.partner_verified_at
        payout.save(update_fields=["status", "partner_verified_at", "paid_at"])

        partner_name = request.user.get_full_name() or request.user.username
        admin_users = User.objects.filter(role="admin", is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=admin,
                    title="Delivery Payout Verified",
                    message=(
                        f"{partner_name} has confirmed receipt of "
                        f"payout \u20b9{payout.total_earnings}."
                    ),
                    notification_type="payout",
                    data={"payout_id": str(payout.id), "action": "verified"},
                )
                for admin in admin_users
            ]
        )
        return Response(DeliveryPartnerPayoutSerializer(payout).data)


# ---------------------------------------------------------------------------
# Vendor coupon management
# ---------------------------------------------------------------------------

class VendorCouponViewSet(viewsets.ModelViewSet):
    """Vendor manages coupons for their own store."""

    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        """Return coupons belonging to the requesting vendor, ordered by newest first."""
        try:
            vendor = self.request.user.vendor_profile
        except Exception:
            return Coupon.objects.none()
        return Coupon.objects.filter(vendor=vendor).order_by("-created_at")

    def perform_create(self, serializer):
        """Attach the vendor and creator to the new coupon.

        Raises:
            PermissionDenied: If the requesting user has no vendor profile.
        """
        try:
            vendor = self.request.user.vendor_profile
        except Exception:
            raise PermissionDenied("No vendor profile found.")
        serializer.save(vendor=vendor, created_by=self.request.user)
