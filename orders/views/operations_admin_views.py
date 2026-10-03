import csv

from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.permissions import HasAdminPermission
from orders.data.operations_repo import (
    DeliveryZoneRepository,
    FeatureFlagRepository,
    RefundLedgerRepository,
    TaxRuleRepository,
)
from orders.data.order_repo import OrderRepository
from orders.actions import MutateRefundLedgerAction, UpdatePageConfigurationAction
from backend.serializers.admin_console_serializers import AdminPageFeatureConfigSerializer
from orders.serializers.operations_serializers import (
    DeliveryZoneSerializer,
    FeatureFlagSerializer,
    RefundLedgerSerializer,
    TaxRuleSerializer,
)


class SafeCsvWriter:
    def __init__(self, response):
        self.writer = csv.writer(response)

    def writerow(self, cells):
        self.writer.writerow(["'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value for value in cells])


class AdminOperationsPagination(PageNumberPagination):
    page_size = 20


PAGE_FEATURE_CONFIG_KEY = 'page_feature_management'


def _default_page_feature_config():
    return {
        'applications': [],
        'global_settings': {
            'requireAuthentication': True,
            'maintenanceMode': False,
            'enabledByDefault': True,
            'pageDisabledAlerts': True,
            'featureAccessRequests': True,
            'bulkActionAlerts': False,
        },
        'version': 1,
    }


def _page_feature_flag():
    return FeatureFlagRepository.page_configuration(_default_page_feature_config())


def _page_feature_response(flag):
    metadata = {**_default_page_feature_config(), **(flag.metadata or {})}
    return {
        **metadata,
        'updated_at': flag.updated_at,
        'is_enabled': flag.is_enabled,
    }


class PageFeatureConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        flag = _page_feature_flag()
        return Response(_page_feature_response(flag))


class AdminPageFeatureConfigView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'

    def get(self, request):
        flag = _page_feature_flag()
        return Response(_page_feature_response(flag))

    def patch(self, request):
        serializer=AdminPageFeatureConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag=UpdatePageConfigurationAction().execute(serializer.validated_data,request,_default_page_feature_config())
        return Response(_page_feature_response(flag))


class AdminRefundLedgerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'
    serializer_class = RefundLedgerSerializer
    pagination_class = AdminOperationsPagination

    def get_queryset(self):
        params = self.request.query_params
        return RefundLedgerRepository.list(
            status_filter=params.get('status'),
            method=params.get('method'),
            order_id=params.get('order'),
            search=params.get('search'),
        )

    def perform_create(self, serializer):
        serializer.instance = MutateRefundLedgerAction().execute(serializer.validated_data, self.request)


class AdminRefundLedgerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'
    serializer_class = RefundLedgerSerializer

    def get_queryset(self):
        return RefundLedgerRepository.list()

    def perform_update(self, serializer):
        serializer.instance = MutateRefundLedgerAction().execute(serializer.validated_data, self.request, pk=serializer.instance.pk)


class AdminDeliveryZoneListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = DeliveryZoneSerializer
    pagination_class = AdminOperationsPagination

    def get_queryset(self):
        params = self.request.query_params
        return DeliveryZoneRepository.list(
            city=params.get('city'),
            is_active=params.get('active'),
            search=params.get('search'),
        )

    def perform_create(self, serializer):
        zone = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='create',
            entity_type='delivery_zone',
            entity_id=str(zone.id),
            summary=f"Created delivery zone {zone.name}.",
            metadata={'city': zone.city, 'radius_km': str(zone.radius_km)},
        )


class AdminDeliveryZoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = DeliveryZoneSerializer

    def get_queryset(self):
        return DeliveryZoneRepository().all()

    def perform_update(self, serializer):
        zone = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='update',
            entity_type='delivery_zone',
            entity_id=str(zone.id),
            summary=f"Updated delivery zone {zone.name}.",
            metadata={'city': zone.city, 'active': zone.is_active},
        )


class AdminTaxRuleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = TaxRuleSerializer
    pagination_class = AdminOperationsPagination

    def get_queryset(self):
        params = self.request.query_params
        return TaxRuleRepository.list(
            country=params.get('country'),
            applies_to=params.get('applies_to'),
            is_active=params.get('active'),
        )

    def perform_create(self, serializer):
        rule = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='create',
            entity_type='tax_rule',
            entity_id=str(rule.id),
            summary=f"Created tax rule {rule.name}.",
            metadata={'tax_rate': str(rule.tax_rate), 'applies_to': rule.applies_to},
        )


class AdminTaxRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = TaxRuleSerializer

    def get_queryset(self):
        return TaxRuleRepository().all()

    def perform_update(self, serializer):
        rule = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='update',
            entity_type='tax_rule',
            entity_id=str(rule.id),
            summary=f"Updated tax rule {rule.name}.",
            metadata={'tax_rate': str(rule.tax_rate), 'active': rule.is_active},
        )


class AdminFeatureFlagListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = FeatureFlagSerializer
    pagination_class = AdminOperationsPagination

    def get_queryset(self):
        params = self.request.query_params
        return FeatureFlagRepository.list(
            audience=params.get('audience'),
            is_enabled=params.get('enabled'),
            search=params.get('search'),
        )

    def perform_create(self, serializer):
        flag = serializer.save(updated_by=self.request.user)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='feature_flag_create',
            entity_type='feature_flag',
            entity_id=flag.key,
            summary=f"Created feature flag {flag.key}.",
            metadata={'enabled': flag.is_enabled, 'audience': flag.audience},
        )


class AdminFeatureFlagDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'settings.manage'
    serializer_class = FeatureFlagSerializer
    lookup_field = 'pk'
    lookup_url_kwarg = 'key'

    def get_queryset(self):
        return FeatureFlagRepository().all()

    def perform_update(self, serializer):
        flag = serializer.save(updated_by=self.request.user)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='feature_flag_update',
            entity_type='feature_flag',
            entity_id=flag.key,
            summary=f"Updated feature flag {flag.key}.",
            metadata={'enabled': flag.is_enabled, 'rollout_percentage': flag.rollout_percentage},
        )


class AdminFinanceExportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'

    def get(self, request):
        export_type = request.query_params.get('type', 'refunds')
        if export_type == 'refunds':
            return self._refund_export()
        if export_type == 'payments':
            return self._payment_export()
        return Response({'error': 'Unsupported export type.'}, status=status.HTTP_400_BAD_REQUEST)

    def _refund_export(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="refunds.csv"'
        writer = SafeCsvWriter(response)
        writer.writerow(['id', 'order', 'customer', 'amount', 'method', 'status', 'gateway_refund_id', 'created_at'])
        for refund in RefundLedgerRepository.list():
            writer.writerow([
                refund.id,
                refund.order.order_number,
                refund.customer.username if refund.customer else '',
                refund.amount,
                refund.method,
                refund.status,
                refund.gateway_refund_id,
                refund.created_at,
            ])
        return response

    def _payment_export(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        writer = SafeCsvWriter(response)
        writer.writerow(['id', 'order_number', 'customer', 'vendor', 'method', 'verified', 'total', 'placed_at'])
        queryset = OrderRepository.get_payment_export_queryset()
        for order in queryset:
            writer.writerow([
                order.id,
                order.order_number,
                order.customer.username,
                order.vendor.store_name,
                order.payment_method,
                order.is_payment_verified,
                order.total,
                order.placed_at,
            ])
        return response
