from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, Q

from accounts.permissions import IsAdminRole
from vendors.serializers.admin import AdminVendorSerializer, VendorFullOnboardSerializer
from vendors.serializers.public import VendorRegistrationSerializer
from vendors.data import VendorRepository

class AdminVendorOnboardView(APIView):
    """POST /api/admin/vendors/onboard/ — Create a full vendor account via Admin"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = VendorFullOnboardSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        
        # We attach the auto-generated password if one was produced
        response_data = AdminVendorSerializer(vendor).data
        if hasattr(vendor, 'auto_generated_password'):
            response_data['temporary_password'] = vendor.auto_generated_password
            
        return Response(response_data, status=status.HTTP_201_CREATED)

class AdminVendorListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        repo = VendorRepository()
        qs = repo.get_all_with_users(
            search=request.query_params.get("search"),
            status=request.query_params.get("status")
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AdminVendorSerializer(page, many=True).data)

    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        return Response(AdminVendorSerializer(vendor).data, status=status.HTTP_201_CREATED)

class AdminVendorDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = VendorRepository().get_by_id(pk)
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminVendorSerializer(vendor).data)

    def patch(self, request, pk):
        vendor = VendorRepository().get_by_id(pk)
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = AdminVendorSerializer(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminVendorSalesReportView(APIView):
    """GET /api/admin/vendors/<pk>/sales-report/ — analytics for a single vendor."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = VendorRepository().get_by_id(pk)
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Parse period (e.g. 7d, 30d, 90d)
        period = request.query_params.get("period", "30d")
        days = 30
        if period == "7d":
            days = 7
        elif period == "90d":
            days = 90
        elif period == "1y":
            days = 365
            
        start_date = timezone.now() - timedelta(days=days)
        
        # Safe import to avoid circular dependencies
        from orders.models import Order
        
        orders = Order.objects.filter(
            vendor=vendor,
            placed_at__gte=start_date,
            status__in=["delivered", "completed"]
        )
        
        stats = orders.aggregate(
            total_sales=Sum("total"),
            total_orders=Count("id"),
            delivered_orders=Count("id", filter=Q(status="delivered")),
        )
        
        total_revenue = float(stats["total_sales"] or 0)
        total_orders = stats["total_orders"] or 0
        delivered_orders = stats["delivered_orders"] or 0
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Monthly data aggregation
        from django.db.models.functions import TruncMonth
        monthly_data_qs = (
            orders.annotate(month=TruncMonth("placed_at"))
            .values("month")
            .annotate(revenue=Sum("total"))
            .order_by("month")
        )
        monthly_data = [
            {
                "month": m["month"].strftime("%b %Y"),
                "revenue": float(m["revenue"] or 0)
            }
            for m in monthly_data_qs
        ]
        
        # Top products aggregation
        from orders.models import OrderItem
        top_products_qs = (
            OrderItem.objects.filter(order__in=orders)
            .values("product_id", "product_name")
            .annotate(total_sold=Sum("quantity"), revenue=Sum("subtotal"))
            .order_by("-total_sold")[:5]
        )
        top_products = [
            {
                "product_id": str(p["product_id"]),
                "name": p["product_name"],
                "total_sold": p["total_sold"] or 0,
                "revenue": float(p["revenue"] or 0)
            }
            for p in top_products_qs
        ]
        
        return Response({
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "average_order_value": avg_order_value,
            "monthly_data": monthly_data,
            "top_products": top_products,
            "period": period,
        })
