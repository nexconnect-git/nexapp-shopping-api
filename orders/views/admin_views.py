from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from orders.actions.ordering import AdminUpdateOrderStatusAction
from orders.data.order_repo import OrderRepository
from orders.data.issue_repo import IssueRepository
from orders.models import Order, OrderIssue
from orders.serializers import OrderSerializer, OrderIssueSerializer


class AdminOrderPagination(PageNumberPagination):
    page_size = 20


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        params = self.request.query_params
        return OrderRepository.get_all_admin(
            status_filter=params.get("status"),
            search=params.get("search"),
            vendor=params.get("vendor"),
            customer=params.get("customer"),
            partner=params.get("delivery_partner"),
        )

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = AdminOrderPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


class AdminOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            order = OrderRepository.get_by_id(pk, prefetch=["items", "tracking"])
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)

    def patch(self, request, pk):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
        action = AdminUpdateOrderStatusAction()
        try:
            order = action.execute(str(pk), new_status, request.user)
            return Response(OrderSerializer(order).data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminOrderIssueListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        queryset = IssueRepository.get_all_admin(
            issue_type=request.query_params.get("issue_type"),
            status_filter=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OrderIssueSerializer(page, many=True).data)


class AdminOrderIssueDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            issue = IssueRepository.get_admin_issue(pk)
        except OrderIssue.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderIssueSerializer(issue).data)

    def patch(self, request, pk):
        try:
            issue = IssueRepository.get_admin_issue(pk)
        except OrderIssue.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        for field in ["status", "admin_notes", "refund_amount", "refund_method"]:
            if field in request.data:
                setattr(issue, field, request.data[field])

        new_status = request.data.get("status")
        if new_status in ("resolved", "rejected", "refund_initiated"):
            issue.resolved_by = request.user
            issue.resolved_at = timezone.now()

        issue.save()
        return Response(OrderIssueSerializer(issue).data)

_PLATFORM_SETTING_FIELDS = [
    "upi_id",
    "delivery_base_fee",
    "delivery_per_km_fee",
    "free_delivery_above",
    "cancellation_window_minutes",
    "cancellation_allowed_statuses",
]


class AdminPlatformSettingView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from orders.models.setting import PlatformSetting
        setting = PlatformSetting.get_setting()
        return Response({f: getattr(setting, f) for f in _PLATFORM_SETTING_FIELDS})

    def patch(self, request):
        from orders.models.setting import PlatformSetting
        setting = PlatformSetting.get_setting()
        updated = []
        for field in _PLATFORM_SETTING_FIELDS:
            if field in request.data:
                setattr(setting, field, request.data[field])
                updated.append(field)
        if updated:
            setting.save(update_fields=updated)
        return Response({f: getattr(setting, f) for f in _PLATFORM_SETTING_FIELDS})
