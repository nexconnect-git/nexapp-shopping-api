from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.admin_access import ADMIN_PERMISSION_CATALOG, allows, granted_permissions
from accounts.actions import RequestAccountPasswordResetAction
from accounts.permissions import IsAdminRole
from backend.actions import AdminReadinessAction, DispatchConsoleAction, ProfileOperationalContextAction, UpdateDispatchAction
from backend.data.admin_console_repository import AdminConsoleRepository


class AdminConsoleIdentityView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    allow_admin_identity = True

    def get(self, request):
        return Response({'superuser': request.user.is_superuser, 'permissions': sorted(granted_permissions(request.user)), 'catalog': [{'key': key, 'label': label} for key, label in ADMIN_PERMISSION_CATALOG.items()]})


class AdminAccountResetView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'users.reset_password'
    throttle_classes = [UserRateThrottle]

    def post(self, request, pk):
        RequestAccountPasswordResetAction().execute(target_id=pk, request=request, reason=str(request.data.get('reason') or ''))
        return Response({'detail': 'A single-use reset link has been sent to the registered email. It expires in one hour.'})


class AdminGlobalSearchView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    allow_admin_identity = True

    def get(self, request):
        query = str(request.query_params.get('q', '')).strip()[:100]
        grants = granted_permissions(request.user)
        domains = [domain for domain in ('orders', 'vendors', 'customers', 'dispatch', 'catalog', 'support') if allows(request.user, f'{domain}.view', grants)]
        return Response({'results': AdminConsoleRepository.search(query, domains) if len(query) >= 2 else []})


class AdminProfileContextView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    allow_admin_identity = True

    def get(self, request, entity_type, pk):
        return Response(ProfileOperationalContextAction().execute(entity_type, pk, request))


class AdminFinanceSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'finance.view'

    def get(self, request):
        return Response({'summary': AdminConsoleRepository.finance_summary(), 'exceptions': AdminConsoleRepository.reconciliation_exceptions(), 'scope': 'All platform records. COD shown separately until verified. Bank statements are not connected.'})


class DispatchCommandSerializer(serializers.Serializer):
    command = serializers.ChoiceField(choices=['assign', 'unassign', 'escalate', 'clear_escalation', 'update'])
    partner_id = serializers.UUIDField(required=False)
    priority = serializers.ChoiceField(choices=['normal', 'high', 'urgent'], required=False)
    notes = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    reason = serializers.CharField(max_length=500, min_length=3)

    def validate(self, attrs):
        if attrs['command'] == 'assign' and not attrs.get('partner_id'):
            raise serializers.ValidationError({'partner_id': 'Choose a delivery partner.'})
        return attrs


class AdminDispatchConsoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'dispatch.view'

    def get(self, request):
        qs = AdminConsoleRepository.orders().exclude(status__in=['delivered', 'cancelled'])
        state = request.query_params.get('state')
        if state == 'unassigned':
            qs = qs.filter(delivery_partner__isnull=True)
        elif state == 'escalated':
            qs = qs.filter(dispatch_escalated_at__isnull=False)
        elif state in ('ready', 'picked_up', 'on_the_way'):
            qs = qs.filter(status=state)
        if request.query_params.get('order'):
            field = serializers.UUIDField()
            pk = field.run_validation(request.query_params['order'])
            qs = qs.filter(pk=pk)
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        payload = DispatchConsoleAction().execute(page, request.query_params.get('order'))
        payload['count'] = paginator.page.paginator.count
        payload['page'] = paginator.page.number
        return Response(payload)


class AdminDispatchCommandView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'dispatch.manage'

    def post(self, request, pk):
        data = DispatchCommandSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = UpdateDispatchAction().execute(pk, data.validated_data, request)
        return Response({'id': str(order.pk), 'detail': 'Dispatch updated.'})


class AdminRuntimeReadinessView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'settings.view'

    def get(self, request):
        return Response(AdminReadinessAction().execute())


class AdminSupportAssigneesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    required_admin_permission = 'support.view'

    def get(self, request):
        return Response({'results': list(AdminConsoleRepository.assignees())})
