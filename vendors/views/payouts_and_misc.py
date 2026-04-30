import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedVendor
from orders.models import Coupon
from orders.serializers import CouponSerializer
from vendors.models import VendorPayout, VendorReview
from vendors.serializers import VendorPayoutSerializer, VendorReviewSerializer
from vendors.views.public import StandardPagination

class VendorPayoutListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        return VendorPayout.objects.filter(vendor__user=self.request.user)

class VendorWalletTransactionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    from vendors.serializers.wallet import VendorWalletTransactionSerializer
    serializer_class = VendorWalletTransactionSerializer

    def get_queryset(self):
        from vendors.models.vendor_wallet import VendorWalletTransaction
        return VendorWalletTransaction.objects.filter(
            vendor__user=self.request.user
        ).order_by('-created_at')

class VendorPayoutApproveView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor__user=request.user)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND)
        if payout.status != "pending_approval":
            return Response({"error": "Only payouts pending approval can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        payout.status = "approved"
        payout.vendor_approved_at = timezone.now()
        payout.vendor_rejection_reason = ""
        payout.save(update_fields=["status", "vendor_approved_at", "vendor_rejection_reason"])
        return Response(VendorPayoutSerializer(payout).data)

class VendorPayoutDeclineView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor__user=request.user)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND)
        if payout.status != "pending_approval":
            return Response({"error": "Only payouts pending approval can be declined."}, status=status.HTTP_400_BAD_REQUEST)
        payout.status = "failed"
        payout.vendor_rejection_reason = request.data.get("reason", "")
        payout.save(update_fields=["status", "vendor_rejection_reason"])
        return Response(VendorPayoutSerializer(payout).data)

class VendorPayoutVerifyCreditView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        try:
            payout = VendorPayout.objects.get(pk=pk, vendor__user=request.user)
        except VendorPayout.DoesNotExist:
            return Response({"error": "Payout not found."}, status=status.HTTP_404_NOT_FOUND)
        if payout.status != "paid":
            return Response({"error": "Only paid payouts can be verified."}, status=status.HTTP_400_BAD_REQUEST)
        payout.status = "verified"
        payout.vendor_verified_at = timezone.now()
        payout.save(update_fields=["status", "vendor_verified_at"])
        return Response(VendorPayoutSerializer(payout).data)

class VendorCouponViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = CouponSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return Coupon.objects.filter(vendor=self.request.user.vendor_profile).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            vendor=self.request.user.vendor_profile,
            created_by=self.request.user,
            code=serializer.validated_data["code"].strip().upper(),
        )

    def perform_update(self, serializer):
        code = serializer.validated_data.get("code")
        if code:
            serializer.save(code=code.strip().upper())
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        coupon = self.get_object()
        base_code = f"{coupon.code}-COPY"
        code = base_code[:50]
        index = 2
        while Coupon.objects.filter(code=code).exists():
            suffix = f"-{index}"
            code = f"{base_code[:50 - len(suffix)]}{suffix}"
            index += 1
        coupon.pk = None
        coupon.id = uuid.uuid4()
        coupon.code = code
        coupon.title = f"{coupon.title} Copy"[:200]
        coupon.used_count = 0
        coupon.is_active = False
        coupon.created_by = request.user
        coupon.save()
        return Response(self.get_serializer(coupon).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        coupon = self.get_object()
        coupon.is_active = True
        if coupon.valid_until and coupon.valid_until < timezone.now():
            coupon.valid_until = timezone.now() + timedelta(days=30)
        coupon.save(update_fields=["is_active", "valid_until"])
        return Response(self.get_serializer(coupon).data)

class VendorReviewViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request, vendor_id=None):
        queryset = VendorReview.objects.filter(vendor_id=vendor_id).order_by("-created_at")
        return Response(VendorReviewSerializer(queryset, many=True).data)
