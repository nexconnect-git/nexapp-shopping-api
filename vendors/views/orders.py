from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound

from accounts.permissions import IsApprovedVendor
from vendors.data import VendorOrderRepository
from vendors.actions import (
    UpdateOrderStatusAction,
    VerifyPickupOtpAction,
    StartDeliverySearchAction,
    CancelDeliverySearchAction,
)
from vendors.views.public import StandardPagination
from orders.serializers import OrderSerializer


class VendorOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = OrderSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return VendorOrderRepository().get_vendor_orders(
            vendor=self.request.user.vendor_profile,
            status_filter=self.request.query_params.get("status")
        )


class VendorOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = OrderSerializer

    def get_object(self):
        repo = VendorOrderRepository()
        vendor = self.request.user.vendor_profile
        obj = repo.get_by_id(
            obj_id=self.kwargs.get("pk"),
            prefetch=["items", "tracking"]
        )
        if not obj or obj.vendor != vendor:
            raise NotFound()
        return obj


class VendorUpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        order = VendorOrderRepository().get_order_for_vendor(pk=pk, vendor=request.user.vendor_profile)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        action = UpdateOrderStatusAction()
        try:
            updated_order = action.execute(order, request.data.get("status"), request.data.get("cancel_reason"))
            return Response(OrderSerializer(updated_order).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorVerifyPickupOtpView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        order = VendorOrderRepository().get_order_for_vendor(pk=pk, vendor=request.user.vendor_profile, status="ready")
        if not order:
            return Response({"error": "Order not found or not in ready status."}, status=status.HTTP_404_NOT_FOUND)

        action = VerifyPickupOtpAction()
        try:
            updated_order = action.execute(order, request.data.get("otp"))
            return Response(OrderSerializer(updated_order).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorStartDeliverySearchView(APIView):
    """Vendor initiates (or re-initiates) delivery partner search."""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        order = VendorOrderRepository().get_order_for_vendor(pk=pk, vendor=request.user.vendor_profile)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if order.status != "ready":
            return Response({"error": f"Cannot start search. Order status is '{order.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_order = StartDeliverySearchAction().execute(order)
            return Response(OrderSerializer(updated_order).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorCancelDeliverySearchView(APIView):
    """Vendor cancels an in-progress delivery partner search."""
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        order = VendorOrderRepository().get_order_for_vendor(pk=pk, vendor=request.user.vendor_profile)
        if not order:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if order.status != "ready":
            return Response({"error": f"Cannot cancel search. Order status is '{order.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_order = CancelDeliverySearchAction().execute(order)
            return Response(OrderSerializer(updated_order).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
