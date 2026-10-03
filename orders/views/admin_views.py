from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from backend.data.admin_console_repository import AdminConsoleRepository
from backend.actions.admin_console_actions import UpdateSupportCaseAction, UpdateAdminSettingsAction
from backend.serializers.admin_console_serializers import AdminOrderFilterSerializer, AdminIssueFilterSerializer, SupportCaseUpdateSerializer, AdminPlatformSettingsSerializer
from accounts.actions.audit_actions import CreateAdminAuditLogAction
from orders.actions.ordering import AdminUpdateOrderStatusAction
from orders.data.order_repo import OrderRepository
from orders.data.issue_repo import IssueRepository
from orders.models import Order, OrderIssue, PlatformSetting
from orders.serializers import OrderSerializer, OrderIssueSerializer

__all__ = [
    'AdminOrderListView', 'AdminOrderDetailView',
    'AdminOrderIssueListView', 'AdminOrderIssueDetailView',
    'AdminPlatformSettingView', 'AdminPaymentsView',
]


class AdminOrderPagination(PageNumberPagination):
    page_size = 20


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        filters = AdminOrderFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return AdminConsoleRepository.filtered_orders(filters.validated_data)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = AdminOrderPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OrderSerializer(page, many=True, context={'request': request}).data)


class AdminOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            order = OrderRepository.get_by_id(pk, prefetch=["items", "tracking"])
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order, context={'request': request}).data)

    def patch(self, request, pk):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
        action = AdminUpdateOrderStatusAction()
        try:
            order = action.execute(str(pk), new_status, request.user)
            CreateAdminAuditLogAction().execute(
                request=request,
                action='status_change',
                entity_type='order',
                entity_id=str(order.id),
                summary=f"Updated order #{order.order_number} to {new_status}.",
                metadata={'status': new_status},
            )
            return Response(OrderSerializer(order, context={'request': request}).data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminOrderIssueListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        filters = AdminIssueFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = IssueRepository.get_all_admin(
            issue_type=request.query_params.get("issue_type"),
            status_filter=request.query_params.get("status"),
            search=request.query_params.get("search"),
            order_filters=filters.validated_data,
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OrderIssueSerializer(page, many=True, context={'request': request}).data)


class AdminOrderIssueDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            issue = IssueRepository.get_admin_issue(pk)
        except OrderIssue.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderIssueSerializer(issue, context={'request': request}).data)

    def patch(self, request, pk):
        serializer = SupportCaseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = UpdateSupportCaseAction().execute(pk, serializer.validated_data, request)
        return Response(OrderIssueSerializer(issue, context={'request': request}).data)


class AdminPaymentsView(generics.ListAPIView):
    """GET /api/admin/payments/
    Returns a paginated list of orders that have online payment data,
    filterable by payment method and verification status.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        filters = AdminOrderFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return AdminConsoleRepository.filtered_orders(filters.validated_data)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = AdminOrderPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OrderSerializer(page, many=True, context={'request': request}).data)


_PLATFORM_SETTING_FIELDS = [
    "upi_id",
    "cod_payment_qr",
    "delivery_base_fee",
    "delivery_per_km_fee",
    "free_delivery_above",
    "platform_fee",
    "packaging_fee",
    "small_cart_threshold",
    "small_cart_fee",
    "tax_percentage",
    "surge_fee",
    "enabled_payment_methods",
    "cancellation_window_minutes",
    "cancellation_allowed_statuses",
]


class AdminPlatformSettingView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response(AdminPlatformSettingsSerializer(AdminConsoleRepository.platform_setting()).data)

    def patch(self, request):
        serializer = AdminPlatformSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        setting = UpdateAdminSettingsAction().execute(serializer.validated_data, request)
        return Response(AdminPlatformSettingsSerializer(setting).data)
