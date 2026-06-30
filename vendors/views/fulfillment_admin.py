from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.models import AdminAuditLog
from accounts.permissions import HasAdminPermission
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.actions.inventory_reservations import ReconcileInventoryReservationsAction
from vendors.data import (
    FulfillmentInventoryRepository,
    FulfillmentNodeRepository,
    FulfillmentServiceAreaRepository,
)
from vendors.actions import BackfillVendorFulfillmentNodesAction, FulfillmentReadinessAuditAction
from vendors.models import FulfillmentNodeInventory
from vendors.serializers.fulfillment import (
    FulfillmentNodeInventorySerializer,
    FulfillmentNodeSerializer,
    FulfillmentNodeServiceAreaSerializer,
)


class AdminFulfillmentPagination(PageNumberPagination):
    page_size = 20


def parse_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


class AdminFulfillmentNodeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeSerializer
    pagination_class = AdminFulfillmentPagination

    def get_queryset(self):
        params = self.request.query_params
        return FulfillmentNodeRepository.list(
            status_filter=params.get("status"),
            node_type=params.get("node_type"),
            vendor_id=params.get("vendor"),
            city=params.get("city"),
            search=params.get("search"),
        )

    def perform_create(self, serializer):
        node = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="create",
            entity_type="fulfillment_node",
            entity_id=str(node.id),
            summary=f"Created fulfillment node {node.name}.",
            metadata={"node_type": node.node_type, "city": node.city, "status": node.status},
        )


class AdminFulfillmentNodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeSerializer

    def get_queryset(self):
        return FulfillmentNodeRepository.list()

    def perform_update(self, serializer):
        node = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="update",
            entity_type="fulfillment_node",
            entity_id=str(node.id),
            summary=f"Updated fulfillment node {node.name}.",
            metadata={"node_type": node.node_type, "city": node.city, "status": node.status},
        )

    def perform_destroy(self, instance):
        node_id = str(instance.id)
        node_name = instance.name
        super().perform_destroy(instance)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="delete",
            entity_type="fulfillment_node",
            entity_id=node_id,
            summary=f"Deleted fulfillment node {node_name}.",
            metadata={},
        )


class AdminFulfillmentNodeServiceAreaListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeServiceAreaSerializer
    pagination_class = AdminFulfillmentPagination

    def get_queryset(self):
        params = self.request.query_params
        return FulfillmentServiceAreaRepository.list(
            node_id=self.kwargs.get("node_id") or params.get("node"),
            is_active=params.get("active"),
            city=params.get("city"),
            search=params.get("search"),
        )

    def perform_create(self, serializer):
        if self.kwargs.get("node_id"):
            area = serializer.save(node_id=self.kwargs["node_id"])
        else:
            area = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="create",
            entity_type="fulfillment_node_service_area",
            entity_id=str(area.id),
            summary=f"Created service area for {area.node.name}.",
            metadata={"node": str(area.node_id), "city": area.city, "postal_code": area.postal_code},
        )


class AdminFulfillmentNodeServiceAreaDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeServiceAreaSerializer

    def get_queryset(self):
        return FulfillmentServiceAreaRepository.list()

    def perform_update(self, serializer):
        area = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="update",
            entity_type="fulfillment_node_service_area",
            entity_id=str(area.id),
            summary=f"Updated service area for {area.node.name}.",
            metadata={"node": str(area.node_id), "active": area.is_active},
        )

    def perform_destroy(self, instance):
        area_id = str(instance.id)
        node_id = str(instance.node_id)
        super().perform_destroy(instance)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="delete",
            entity_type="fulfillment_node_service_area",
            entity_id=area_id,
            summary="Deleted fulfillment node service area.",
            metadata={"node": node_id},
        )


class AdminFulfillmentNodeInventoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeInventorySerializer
    pagination_class = AdminFulfillmentPagination

    def get_queryset(self):
        params = self.request.query_params
        return FulfillmentInventoryRepository.list(
            node_id=self.kwargs.get("node_id") or params.get("node"),
            product_id=params.get("product"),
            low_stock=params.get("low_stock"),
            search=params.get("search"),
        )

    def perform_create(self, serializer):
        if self.kwargs.get("node_id"):
            inventory = serializer.save(node_id=self.kwargs["node_id"])
        else:
            inventory = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="create",
            entity_type="fulfillment_node_inventory",
            entity_id=str(inventory.id),
            summary=f"Created inventory item for {inventory.node.name}.",
            metadata={
                "node": str(inventory.node_id),
                "product": str(inventory.product_id),
                "stock": inventory.stock,
            },
        )


class AdminFulfillmentNodeInventoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    serializer_class = FulfillmentNodeInventorySerializer

    def get_queryset(self):
        return FulfillmentInventoryRepository.list()

    def perform_update(self, serializer):
        inventory = serializer.save()
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="update",
            entity_type="fulfillment_node_inventory",
            entity_id=str(inventory.id),
            summary=f"Updated inventory item for {inventory.node.name}.",
            metadata={
                "node": str(inventory.node_id),
                "product": str(inventory.product_id),
                "stock": inventory.stock,
                "reserved_stock": inventory.reserved_stock,
            },
        )

    def perform_destroy(self, instance):
        inventory_id = str(instance.id)
        node_id = str(instance.node_id)
        product_id = str(instance.product_id)
        super().perform_destroy(instance)
        CreateAdminAuditLogAction().execute(
            request=self.request,
            action="delete",
            entity_type="fulfillment_node_inventory",
            entity_id=inventory_id,
            summary="Deleted fulfillment node inventory item.",
            metadata={"node": node_id, "product": product_id},
        )


class AdminFulfillmentStockComparisonView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"

    def get(self, request):
        params = request.query_params
        queryset = FulfillmentNodeInventory.objects.select_related(
            "node",
            "product",
            "product__vendor",
        ).order_by("node__name", "product__name")
        if params.get("node"):
            queryset = queryset.filter(node_id=params["node"])
        if params.get("vendor"):
            queryset = queryset.filter(product__vendor_id=params["vendor"])
        if params.get("search"):
            search = params["search"]
            queryset = queryset.filter(product__name__icontains=search)

        rows = []
        summary = {
            "total_rows": 0,
            "mismatch_count": 0,
            "node_over_product_count": 0,
            "product_over_node_count": 0,
            "reserved_overstock_count": 0,
            "visibility_mismatch_count": 0,
        }
        only_mismatches = str(params.get("mismatches", "")).lower() in {"1", "true", "yes"}

        for inventory in queryset[:500]:
            product = inventory.product
            node_stock = int(inventory.stock or 0)
            product_stock = int(product.stock or 0)
            reserved_stock = int(inventory.reserved_stock or 0)
            visibility_mismatch = bool(inventory.is_available) and (
                product.status != "active"
                or product.approval_status != "approved"
                or not product.is_available
                or product_stock <= 0
            )
            mismatch_reasons = []
            if node_stock != product_stock:
                mismatch_reasons.append("stock_delta")
            if reserved_stock > node_stock:
                mismatch_reasons.append("reserved_overstock")
            if visibility_mismatch:
                mismatch_reasons.append("visibility_mismatch")
            if only_mismatches and not mismatch_reasons:
                continue

            delta = node_stock - product_stock
            summary["total_rows"] += 1
            if mismatch_reasons:
                summary["mismatch_count"] += 1
            if delta > 0:
                summary["node_over_product_count"] += 1
            elif delta < 0:
                summary["product_over_node_count"] += 1
            if reserved_stock > node_stock:
                summary["reserved_overstock_count"] += 1
            if visibility_mismatch:
                summary["visibility_mismatch_count"] += 1

            rows.append({
                "node_id": str(inventory.node_id),
                "node_name": inventory.node.name,
                "product_id": str(inventory.product_id),
                "product_name": product.name,
                "vendor_id": str(product.vendor_id),
                "vendor_name": product.vendor.store_name if product.vendor else "",
                "node_stock": node_stock,
                "node_reserved_stock": reserved_stock,
                "node_sellable_stock": inventory.sellable_stock,
                "product_stock": product_stock,
                "stock_delta": delta,
                "node_available": inventory.is_available,
                "product_available": product.is_available,
                "product_status": product.status,
                "product_approval_status": product.approval_status,
                "mismatch_reasons": mismatch_reasons,
                "updated_at": inventory.updated_at,
            })

        return Response({"summary": summary, "results": rows})


class AdminCartFulfillmentAuditReportView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "audit.view"

    def get(self, request):
        params = request.query_params
        queryset = AdminAuditLog.objects.select_related("actor").filter(
            entity_type="customer_cart",
            metadata__event_type__startswith="cart_fulfillment_",
        )
        if params.get("event_type"):
            queryset = queryset.filter(metadata__event_type=params["event_type"])
        if params.get("actor"):
            queryset = queryset.filter(actor_id=params["actor"])

        limit = min(max(int(params.get("limit", 50) or 50), 1), 200)
        event_counts = {}
        for event_type in queryset.values_list("metadata__event_type", flat=True):
            if not event_type:
                continue
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        results = []
        for log in queryset.order_by("-created_at")[:limit]:
            results.append({
                "id": str(log.id),
                "event_type": (log.metadata or {}).get("event_type", ""),
                "cart_id": log.entity_id,
                "actor_id": str(log.actor_id or ""),
                "actor": log.actor.username if log.actor else "system",
                "summary": log.summary,
                "metadata": log.metadata or {},
                "created_at": log.created_at,
            })

        return Response({
            "summary": {
                "total_events": queryset.count(),
                "event_counts": event_counts,
            },
            "results": results,
        })


class AdminFulfillmentReadinessReportView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"

    def get(self, request):
        return Response(
            FulfillmentReadinessAuditAction().execute(
                sample_limit=request.query_params.get("sample_limit", 20),
            )
        )


class AdminFulfillmentRolloutPrepareView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    APPLY_CONFIRMATION = "BACKFILL_FULFILLMENT"

    def post(self, request):
        dry_run = parse_bool(request.data.get("dry_run"), default=True)
        if not dry_run and request.data.get("confirm") != self.APPLY_CONFIRMATION:
            return Response(
                {
                    "error": (
                        "Applying fulfillment rollout requires confirm="
                        f"{self.APPLY_CONFIRMATION}."
                    )
                },
                status=400,
            )

        backfill = BackfillVendorFulfillmentNodesAction().execute(
            vendor_id=request.data.get("vendor_id") or None,
            include_unapproved=parse_bool(request.data.get("include_unapproved"), default=False),
            sync_existing=parse_bool(request.data.get("sync_existing"), default=False),
            dry_run=dry_run,
        )
        readiness = FulfillmentReadinessAuditAction().execute(
            sample_limit=request.data.get("sample_limit", 20),
        )
        CreateAdminAuditLogAction().execute(
            request=request,
            action="prepare_fulfillment_rollout",
            entity_type="fulfillment_rollout",
            entity_id="dry-run" if dry_run else "applied",
            summary=(
                "Previewed fulfillment rollout backfill."
                if dry_run
                else "Applied fulfillment rollout backfill."
            ),
            metadata={
                "dry_run": dry_run,
                "backfill": backfill,
                "readiness_status": readiness.get("status"),
                "critical_issue_count": readiness.get("critical_issue_count"),
            },
        )
        return Response({
            "mode": "dry_run" if dry_run else "applied",
            "backfill": backfill,
            "readiness": readiness,
        })

class AdminFulfillmentReservationReconcileView(APIView):
    permission_classes = [IsAuthenticated, HasAdminPermission]
    required_admin_permission = "settings.manage"
    APPLY_CONFIRMATION = "RECONCILE_RESERVATIONS"

    def post(self, request):
        dry_run = parse_bool(request.data.get("dry_run"), default=True)
        if not dry_run and request.data.get("confirm") != self.APPLY_CONFIRMATION:
            return Response(
                {
                    "error": (
                        "Applying reservation reconciliation requires confirm="
                        f"{self.APPLY_CONFIRMATION}."
                    )
                },
                status=400,
            )

        result = ReconcileInventoryReservationsAction().execute(
            failed_payment_age_minutes=request.data.get("failed_payment_age_minutes", 60),
            dry_run=dry_run,
        )
        CreateAdminAuditLogAction().execute(
            request=request,
            action="reconcile_inventory_reservations",
            entity_type="fulfillment_reservations",
            entity_id="dry-run" if dry_run else "applied",
            summary=(
                "Previewed inventory reservation reconciliation."
                if dry_run
                else "Applied inventory reservation reconciliation."
            ),
            metadata=result,
        )
        return Response({
            "mode": "dry_run" if dry_run else "applied",
            "result": result,
        })
