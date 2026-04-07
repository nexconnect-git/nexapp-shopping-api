"""
API views for the ``orders`` app.

Endpoints covered:
  - Cart management (view, add, update, clear)
  - Order placement and cancellation
  - Coupon validation and listing
  - Order tracking and payment QR code
  - Order ratings
  - Order issues (returns, refunds, damage, mismatch) with messaging
  - Admin: full order management and issue management
"""

import base64
from decimal import Decimal
from io import BytesIO

import qrcode
import qrcode.constants
from django.db.models import Avg, F, Q
from django.utils import timezone

from rest_framework import generics, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from orders.models import (
    Cart,
    CartItem,
    Coupon,
    CouponUsage,
    IssueMessage,
    Order,
    OrderIssue,
    OrderRating,
    OrderTracking,
)
from orders.serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    CouponSerializer,
    CreateOrderSerializer,
    OrderIssueSerializer,
    OrderRatingSerializer,
    OrderSerializer,
    OrderTrackingSerializer,
)
from orders.services import OrderService
from products.models import Product


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class AdminOrderPagination(PageNumberPagination):
    """20-items-per-page pagination for admin order list views."""

    page_size = 20


# ---------------------------------------------------------------------------
# Cart views
# ---------------------------------------------------------------------------


class CartView(APIView):
    """GET /api/orders/cart/ — retrieve the current user's cart."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return (or lazily create) the authenticated user's cart."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)


class AddToCartView(APIView):
    """POST /api/orders/cart/add/ — add a product to the cart."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Add a product (or increment its quantity) in the cart.

        If the product is already in the cart the requested quantity is added
        on top of the existing quantity.

        Returns:
            201 on first add; 200 when incrementing an existing item.
        """
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data.get("quantity", 1)

        try:
            product = Product.objects.get(pk=product_id, is_available=True)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found or unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UpdateCartItemView(APIView):
    """PATCH / DELETE /api/orders/cart/<pk>/ — update or remove a cart item."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        """Set the exact quantity for a cart item; deletes it when quantity ≤ 0."""
        try:
            cart_item = CartItem.objects.get(pk=pk, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        quantity = request.data.get("quantity")
        if quantity is not None:
            if int(quantity) <= 0:
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            cart_item.quantity = int(quantity)
            cart_item.save()

        return Response(CartItemSerializer(cart_item).data)

    def delete(self, request, pk):
        """Remove a single item from the cart."""
        try:
            cart_item = CartItem.objects.get(pk=pk, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    """DELETE /api/orders/cart/clear/ — remove all items from the cart."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        """Clear every item in the current user's cart (idempotent)."""
        try:
            cart = Cart.objects.get(user=request.user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass  # Nothing to clear — still return 204
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Order views
# ---------------------------------------------------------------------------


class CreateOrderView(APIView):
    """POST /api/orders/ — convert the cart into one or more vendor orders."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Place an order for every vendor represented in the current cart."""
        serializer = CreateOrderSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        delivery_address_id = serializer.validated_data["delivery_address_id"]
        notes = serializer.validated_data.get("notes", "")
        payment_method = serializer.validated_data.get("payment_method", "cod")
        coupon_code = (
            serializer.validated_data.get("coupon_code", "").strip().upper()
        )

        try:
            created_orders = OrderService.create_orders_from_cart(
                user=request.user,
                delivery_address_id=delivery_address_id,
                payment_method=payment_method,
                notes=notes,
                coupon_code=coupon_code,
            )
            return Response(
                OrderSerializer(created_orders, many=True).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )


class OrderListView(generics.ListAPIView):
    """GET /api/orders/ — list the authenticated customer's orders."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Return orders belonging to the current user, filtered by ``status``."""
        queryset = Order.objects.filter(customer=self.request.user)
        order_status = self.request.query_params.get("status")
        if order_status:
            queryset = queryset.filter(status=order_status)
        return queryset


class OrderDetailView(generics.RetrieveAPIView):
    """GET /api/orders/<pk>/ — single order detail for the current customer."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Scope to the current user's orders with items and tracking prefetched."""
        return Order.objects.filter(
            customer=self.request.user
        ).prefetch_related("items", "tracking")


class CancelOrderView(APIView):
    """POST /api/orders/<pk>/cancel/ — cancel a placed or confirmed order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Cancel the specified order if it is still cancellable."""
        try:
            order = OrderService.cancel_order(str(pk), request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )


class OrderTrackingView(generics.ListAPIView):
    """GET /api/orders/<pk>/tracking/ — tracking history for a customer order."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderTrackingSerializer

    def get_queryset(self):
        """Return tracking events for the requested order (current user only)."""
        return OrderTracking.objects.filter(
            order_id=self.kwargs["pk"],
            order__customer=self.request.user,
        )


class OrderPaymentQRView(APIView):
    """GET /api/orders/<pk>/payment-qr/ — UPI payment QR code for COD collection."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Generate a UPI-style QR code for the order's total amount.

        Accessible by both the assigned delivery partner and the customer.

        Returns:
            200 with ``qr_base64`` PNG and ``upi_string``; 403/404 on error.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if (
            order.delivery_partner != request.user
            and order.customer != request.user
        ):
            return Response(
                {"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN
            )

        amount = str(order.total)
        upi_string = (
            f"upi://pay?pa=nexconnect@ybl&pn=NexConnect&am={amount}"
            f"&cu=INR&tn=Order%20{order.order_number}"
        )

        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M
        )
        qr.add_data(upi_string)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")

        qr_buffer = BytesIO()
        qr_image.save(qr_buffer, format="PNG")
        qr_base64_string = base64.b64encode(qr_buffer.getvalue()).decode("utf-8")

        return Response(
            {
                "order_number": order.order_number,
                "amount": amount,
                "qr_base64": f"data:image/png;base64,{qr_base64_string}",
                "upi_string": upi_string,
            }
        )


# ---------------------------------------------------------------------------
# Coupon views
# ---------------------------------------------------------------------------


class ValidateCouponView(APIView):
    """POST /api/orders/coupons/validate/ — validate a coupon against a cart total."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Check whether a coupon code is valid for the provided cart total.

        Request body:
            code: Coupon code string.
            cart_total: Numeric cart total to validate minimum order amount.

        Returns:
            200 with ``{valid: true, discount, …}`` or 400 with an error.
        """
        code = request.data.get("code", "").strip().upper()
        cart_total = request.data.get("cart_total", 0)

        if not code:
            return Response(
                {"error": "Coupon code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            return Response(
                {"valid": False, "error": "Invalid coupon code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if coupon.valid_from > now:
            return Response(
                {"valid": False, "error": "Coupon is not yet valid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coupon.valid_until and coupon.valid_until < now:
            return Response(
                {"valid": False, "error": "Coupon has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            return Response(
                {"valid": False, "error": "Coupon usage limit reached."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_uses = CouponUsage.objects.filter(
            coupon=coupon, user=request.user
        ).count()
        if user_uses >= coupon.per_user_limit:
            return Response(
                {"valid": False, "error": "You have already used this coupon."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            total = Decimal(str(cart_total))
        except Exception:
            total = Decimal("0")

        if total < coupon.min_order_amount:
            return Response(
                {
                    "valid": False,
                    "error": (
                        f"Minimum order amount is ₦{coupon.min_order_amount}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount = coupon.calculate_discount(total)
        return Response(
            {
                "valid": True,
                "code": coupon.code,
                "title": coupon.title,
                "discount_type": coupon.discount_type,
                "discount": str(discount),
                "message": f'"{coupon.title}" applied! You save ₦{discount}.',
            }
        )


class CustomerCouponListView(generics.ListAPIView):
    """GET /api/orders/coupons/ — list all active, currently-valid platform coupons."""

    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        """Return coupons that are active, within their date range, and under limit."""
        now = timezone.now()
        return (
            Coupon.objects.filter(is_active=True, valid_from__lte=now)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
            .filter(
                Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit"))
            )
            .order_by("-created_at")
        )


class AdminCouponViewSet(viewsets.ModelViewSet):
    """Admin full CRUD on all coupons — admin role enforced in queryset."""

    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        """Return all coupons for admins; empty queryset for everyone else."""
        if self.request.user.role != "admin":
            return Coupon.objects.none()
        return Coupon.objects.select_related("vendor").order_by("-created_at")

    def perform_create(self, serializer):
        """Attach the creating admin user to the new coupon."""
        serializer.save(created_by=self.request.user)


# ---------------------------------------------------------------------------
# Order ratings
# ---------------------------------------------------------------------------


class SubmitOrderRatingView(APIView):
    """POST /api/orders/<pk>/rating/ — rate a delivered order and its delivery partner."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Submit a 1–5 star rating for a delivered order.

        Also updates the assigned delivery partner's running average rating.

        Returns:
            201 with rating id and value; 400/404 on validation failures.
        """
        try:
            order = Order.objects.get(id=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if order.status != "delivered":
            return Response(
                {"error": "You can only rate delivered orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(order, "rating"):
            return Response(
                {"error": "You have already rated this order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rating_value = serializer.validated_data["rating"]
        rating = OrderRating.objects.create(
            order=order,
            customer=request.user,
            delivery_partner=order.delivery_partner,
            rating=rating_value,
        )

        # Update the delivery partner's aggregate rating if assigned
        if order.delivery_partner:
            try:
                delivery_partner_profile = (
                    order.delivery_partner.delivery_profile
                )
                ratings = OrderRating.objects.filter(
                    delivery_partner=order.delivery_partner
                )
                avg = ratings.aggregate(avg=Avg("rating"))["avg"]
                delivery_partner_profile.average_rating = avg or rating_value
                delivery_partner_profile.save(update_fields=["average_rating"])
            except Exception:  # noqa: BLE001 — partner profile may not exist yet
                pass

        return Response(
            {"id": str(rating.id), "rating": rating.rating},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Order issues (returns / refunds / damage / mismatch)
# ---------------------------------------------------------------------------


class CustomerOrderIssueListCreateView(APIView):
    """GET / POST /api/orders/issues/ — customer lists or raises order issues."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return all open issues raised by the current customer."""
        issues = OrderIssue.objects.filter(
            customer=request.user
        ).select_related("order")
        return Response(OrderIssueSerializer(issues, many=True).data)

    def post(self, request):
        """Raise a new issue against a delivered or cancelled order.

        Request body:
            order: UUID of the target order.
            issue_type: One of the ``OrderIssue.ISSUE_TYPE_CHOICES`` keys.
            description: Human-readable description of the problem.

        Returns:
            201 with the created issue; 400/404 on validation errors.
        """
        order_id = request.data.get("order")
        issue_type = request.data.get("issue_type")
        description = request.data.get("description", "").strip()

        if not order_id or not issue_type or not description:
            return Response(
                {"error": "order, issue_type and description are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_types = [choice[0] for choice in OrderIssue.ISSUE_TYPE_CHOICES]
        if issue_type not in valid_types:
            return Response(
                {"error": f"Invalid issue_type. Valid: {valid_types}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if order.status not in ("delivered", "cancelled"):
            return Response(
                {
                    "error": (
                        "Issues can only be raised on delivered or "
                        "cancelled orders."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue = OrderIssue.objects.create(
            order=order,
            customer=request.user,
            issue_type=issue_type,
            description=description,
        )
        # Auto-post the description as the first message in the thread
        IssueMessage.objects.create(
            issue=issue,
            sender=request.user,
            is_admin=False,
            message=description,
        )
        return Response(
            OrderIssueSerializer(issue).data, status=status.HTTP_201_CREATED
        )


class CustomerOrderIssueDetailView(APIView):
    """GET /api/orders/issues/<pk>/ — customer views a single issue."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Return a single issue belonging to the current customer."""
        try:
            issue = OrderIssue.objects.get(id=pk, customer=request.user)
        except OrderIssue.DoesNotExist:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderIssueSerializer(issue).data)


class IssueMessageCreateView(APIView):
    """POST /api/orders/issues/<pk>/messages/ — customer or admin posts a message."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Add a message to an existing issue thread."""
        message_text = request.data.get("message", "").strip()
        if not message_text:
            return Response(
                {"error": "message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = OrderService.add_issue_message(
                str(pk), request.user, message_text
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )


# ---------------------------------------------------------------------------
# Admin: order management
# ---------------------------------------------------------------------------


class AdminOrderListView(generics.ListAPIView):
    """GET /api/admin/orders/ — paginated list of all orders (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Return orders with optional status/search/vendor/customer/partner filters."""
        queryset = Order.objects.select_related(
            "customer", "vendor"
        ).order_by("-placed_at")

        order_status = self.request.query_params.get("status")
        if order_status:
            queryset = queryset.filter(status=order_status)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(order_number__icontains=search)

        vendor = self.request.query_params.get("vendor")
        if vendor:
            queryset = queryset.filter(vendor_id=vendor)

        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)

        partner = self.request.query_params.get("delivery_partner")
        if partner:
            queryset = queryset.filter(delivery_partner_id=partner)

        return queryset

    def get(self, request, *args, **kwargs):
        """Override to apply AdminOrderPagination instead of the default."""
        queryset = self.get_queryset()
        paginator = AdminOrderPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            OrderSerializer(page, many=True).data
        )


class AdminOrderDetailView(APIView):
    """GET / PATCH /api/admin/orders/<pk>/ — view or status-update any order."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_order(self, pk) -> Order | None:
        """Fetch the order with items and tracking prefetched, or None."""
        try:
            return Order.objects.prefetch_related("items", "tracking").get(pk=pk)
        except Order.DoesNotExist:
            return None

    def get(self, request, pk):  # noqa: ARG002
        """Return full order details."""
        order = self._get_order(pk)
        if not order:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderSerializer(order).data)

    def patch(self, request, pk):
        """Update the status of an order."""
        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"error": "Status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = OrderService.update_order_status(
                str(pk), new_status, request.user
            )
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )


# ---------------------------------------------------------------------------
# Admin: issue management
# ---------------------------------------------------------------------------


class AdminOrderIssueListView(APIView):
    """GET /api/admin/issues/ — paginated list of all order issues."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return all issues with optional ``issue_type``, ``status``, ``search``."""
        queryset = OrderIssue.objects.select_related(
            "order", "customer"
        ).all()

        issue_type = request.query_params.get("issue_type")
        if issue_type:
            queryset = queryset.filter(issue_type=issue_type)

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order__order_number__icontains=search)
                | Q(customer__username__icontains=search)
                | Q(customer__first_name__icontains=search)
                | Q(customer__last_name__icontains=search)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            OrderIssueSerializer(page, many=True).data
        )


class AdminOrderIssueDetailView(APIView):
    """GET / PATCH /api/admin/issues/<pk>/ — view or resolve an order issue."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):  # noqa: ARG002
        """Return a single order issue."""
        try:
            issue = OrderIssue.objects.get(id=pk)
        except OrderIssue.DoesNotExist:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderIssueSerializer(issue).data)

    def patch(self, request, pk):
        """Update an issue's status, admin notes, refund amount, or method."""
        try:
            issue = OrderIssue.objects.get(id=pk)
        except OrderIssue.DoesNotExist:
            return Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )

        updatable_fields = [
            "status", "admin_notes", "refund_amount", "refund_method"
        ]
        for field in updatable_fields:
            if field in request.data:
                setattr(issue, field, request.data[field])

        # Record resolver information for terminal states
        new_status = request.data.get("status")
        if new_status in ("resolved", "rejected", "refund_initiated"):
            issue.resolved_by = request.user
            issue.resolved_at = timezone.now()

        issue.save()
        return Response(OrderIssueSerializer(issue).data)
