import csv

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.permissions import HasAdminPermission
from orders.data.operations_repo import (
    DeliveryZoneRepository,
    FeatureFlagRepository,
    RefundLedgerRepository,
    TaxRuleRepository,
)
from orders.data.order_repo import OrderRepository
from orders.serializers.operations_serializers import (
    DeliveryZoneSerializer,
    FeatureFlagSerializer,
    RefundLedgerSerializer,
    TaxRuleSerializer,
)


class AdminOperationsPagination(PageNumberPagination):
    page_size = 20


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
        order = serializer.validated_data['order']
        customer = serializer.validated_data.get('customer') or order.customer
        refund = serializer.save(customer=customer, requested_by=self.request.user)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='refund_create',
            entity_type='refund_ledger',
            entity_id=str(refund.id),
            summary=f"Created refund request for order #{order.order_number}.",
            metadata={'amount': str(refund.amount), 'method': refund.method, 'status': refund.status},
        )


class AdminRefundLedgerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = 'finance.manage'
    serializer_class = RefundLedgerSerializer

    def get_queryset(self):
        return RefundLedgerRepository.list()

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        refund = serializer.save()
        updated_fields = []
        if previous_status != refund.status:
            updated_fields.append('status')
            now = timezone.now()
            if refund.status == 'approved' and not refund.approved_at:
                refund.approved_by = self.request.user
                refund.approved_at = now
                refund.order.refund_status = 'initiated'
                refund.order.save(update_fields=['refund_status'])
            elif refund.status == 'processing':
                refund.order.refund_status = 'initiated'
                refund.order.save(update_fields=['refund_status'])
            elif refund.status == 'processed' and not refund.processed_at:
                refund.processed_by = self.request.user
                refund.processed_at = now
                refund.order.refund_status = 'processed'
                if refund.gateway_refund_id:
                    refund.order.razorpay_refund_id = refund.gateway_refund_id
                    refund.order.save(update_fields=['refund_status', 'razorpay_refund_id'])
                else:
                    refund.order.save(update_fields=['refund_status'])
            elif refund.status == 'failed':
                refund.order.refund_status = 'failed'
                refund.order.save(update_fields=['refund_status'])
            refund.save(update_fields=['approved_by', 'approved_at', 'processed_by', 'processed_at', 'updated_at'])

        CreateAdminAuditLogAction().execute(
            request=self.request,
            action='refund_update',
            entity_type='refund_ledger',
            entity_id=str(refund.id),
            summary=f"Updated refund {refund.id}.",
            metadata={'status': refund.status, 'updated_fields': updated_fields},
        )


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
        writer = csv.writer(response)
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
        writer = csv.writer(response)
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
