from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedVendor, IsVendor
from vendors.serializers.public import VendorSerializer
from vendors.actions import BulkUpdateStockAction, SetStoreStatusAction, VendorAnalyticsAction, VendorOperationsSummaryAction
from vendors.data import VendorOrderRepository, VendorProductRepository
from products.actions import UpdateVendorProductAction
from products.serializers import ProductSerializer, ProductCreateUpdateSerializer
from products.models import Product
from orders.serializers import OrderSerializer
from vendors.views.public import StandardPagination

class VendorProfileView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        return Response(VendorSerializer(request.user.vendor_profile).data)

    def patch(self, request):
        serializer = VendorSerializer(request.user.vendor_profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class VendorStoreSettingsView(VendorProfileView):
    pass

class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        vendor = request.user.vendor_profile
        order_repo = VendorOrderRepository()
        product_repo = VendorProductRepository()

        total_orders = order_repo.filter(vendor=vendor).count()
        total_products = product_repo.filter(vendor=vendor).count()
        recent_orders = order_repo.get_recent_orders(vendor, 10)
        low_stock = product_repo.get_low_stock_for_vendor(vendor)

        return Response({
            "total_orders": total_orders,
            "total_products": total_products,
            "average_rating": vendor.average_rating,
            "total_ratings": vendor.total_ratings,
            "recent_orders": OrderSerializer(recent_orders, many=True).data,
            "is_open": vendor.is_open,
            "closing_time": str(vendor.closing_time) if vendor.closing_time else None,
            "require_stock_check": vendor.require_stock_check,
            "low_stock_count": low_stock.count(),
            "low_stock_products": ProductSerializer(low_stock, many=True).data,
        })


class VendorOperationsSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        return Response(VendorOperationsSummaryAction().execute(request.user.vendor_profile))

class VendorAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        action = VendorAnalyticsAction()
        return Response(action.execute(
            vendor=request.user.vendor_profile,
            days=request.query_params.get("days", "30"),
        ))

class SetStoreStatusView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        vendor = request.user.vendor_profile
        try:
            action = SetStoreStatusAction()
            res = action.execute(
                vendor=vendor, 
                is_open=request.data.get("is_open"), 
                closing_time=request.data.get("closing_time")
            )
            return Response({
                "is_open": res.is_open,
                "closing_time": str(res.closing_time) if res.closing_time else None,
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class BulkUpdateStockView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        vendor = request.user.vendor_profile
        action = BulkUpdateStockAction()
        try:
            updated, errors = action.execute(vendor, request.data.get("updates", []))
            return Response({"updated": updated, "errors": errors})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VendorProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductCreateUpdateSerializer
        return ProductSerializer

    def get_queryset(self):
        return VendorProductRepository().get_products_for_vendor_with_growth(
            self.request.user.vendor_profile
        )

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        product = self.get_object()
        serializer = ProductCreateUpdateSerializer(product, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = UpdateVendorProductAction().execute(product, serializer.validated_data)
        return Response(ProductSerializer(product, context={"request": request}).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)
