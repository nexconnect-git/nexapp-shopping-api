from django.db.models import Q
from django.utils import timezone
from orders.models import OrderIssue
from backend.data.admin_console_repository import AdminConsoleRepository


class IssueRepository:

    @staticmethod
    def get_customer_issues(user):
        return OrderIssue.objects.filter(customer=user).select_related("order")

    @staticmethod
    def get_customer_issue(pk, user):
        return OrderIssue.objects.get(id=pk, customer=user)

    @staticmethod
    def get_all_admin(issue_type=None, status_filter=None, search=None, order_filters=None):
        qs = OrderIssue.objects.select_related("order", "customer", "assignee").prefetch_related("messages", "attachments").all()
        if order_filters:
            related = {key: value for key, value in order_filters.items() if key in ("vendor", "customer", "delivery_partner", "order")}
            if related:
                qs = qs.filter(order__in=AdminConsoleRepository.filtered_orders(related))
            for key in ('assignee', 'queue', 'priority'):
                if order_filters.get(key):
                    qs = qs.filter(**{key: order_filters[key]})
            if order_filters.get('due'):
                qs = qs.exclude(status__in=['resolved', 'closed', 'rejected'])
                qs = qs.filter(**{'due_at__lt' if order_filters['due'] == 'overdue' else 'due_at__gte': timezone.now()})
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
        return qs.order_by('-created_at', 'id')

    @staticmethod
    def get_admin_issue(pk):
        return OrderIssue.objects.select_related("order", "customer", "assignee").prefetch_related("messages", "attachments").get(id=pk)
