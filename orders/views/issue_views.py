from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from orders.actions.ordering import AddIssueMessageAction
from orders.data.issue_repo import IssueRepository
from orders.models import IssueMessage, OrderIssue, Order
from orders.serializers import OrderIssueSerializer


class CustomerOrderIssueListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        issues = IssueRepository.get_customer_issues(request.user)
        return Response(OrderIssueSerializer(issues, many=True).data)

    def post(self, request):
        order_id = request.data.get("order")
        issue_type = request.data.get("issue_type")
        description = request.data.get("description", "").strip()

        if not order_id or not issue_type or not description:
            return Response({"error": "order, issue_type and description are required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = [choice[0] for choice in OrderIssue.ISSUE_TYPE_CHOICES]
        if issue_type not in valid_types:
            return Response({"error": f"Invalid issue_type. Valid: {valid_types}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in ("delivered", "cancelled"):
            return Response(
                {"error": "Issues can only be raised on delivered or cancelled orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue = OrderIssue.objects.create(
            order=order, customer=request.user, issue_type=issue_type, description=description,
        )
        IssueMessage.objects.create(issue=issue, sender=request.user, is_admin=False, message=description)
        return Response(OrderIssueSerializer(issue).data, status=status.HTTP_201_CREATED)


class CustomerOrderIssueDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            issue = IssueRepository.get_customer_issue(pk, request.user)
        except OrderIssue.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderIssueSerializer(issue).data)


class IssueMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        message_text = request.data.get("message", "").strip()
        if not message_text:
            return Response({"error": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        action = AddIssueMessageAction()
        try:
            data = action.execute(str(pk), request.user, message_text)
            return Response(data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
