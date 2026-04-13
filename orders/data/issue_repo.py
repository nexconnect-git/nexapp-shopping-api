from django.db.models import Q
from orders.models import OrderIssue


class IssueRepository:

    @staticmethod
    def get_customer_issues(user):
        return OrderIssue.objects.filter(customer=user).select_related("order")

    @staticmethod
    def get_customer_issue(pk, user):
        return OrderIssue.objects.get(id=pk, customer=user)

    @staticmethod
    def get_all_admin(issue_type=None, status_filter=None, search=None):
        qs = OrderIssue.objects.select_related("order", "customer").all()
        if issue_type:
            qs = qs.filter(issue_type=issue_type)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(order__order_number__icontains=search)
                | Q(customer__username__icontains=search)
                | Q(customer__first_name__icontains=search)
                | Q(customer__last_name__icontains=search)
            )
        return qs

    @staticmethod
    def get_admin_issue(pk):
        return OrderIssue.objects.get(id=pk)
