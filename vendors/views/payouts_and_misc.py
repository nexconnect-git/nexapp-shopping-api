from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedVendor
from vendors.serializers.coupons import VendorCouponSerializer
from vendors.models import Vendor, VendorPayout, VendorReview
from vendors.serializers import VendorPayoutSerializer, VendorReviewSerializer
from vendors.helpers.public_vendor_helpers import StandardPagination
from vendors.actions import UpdateVendorRecipientPayoutAction, VendorCouponAction
from vendors.data.finance_repository import VendorFinanceRepository, VendorCouponRepository
from vendors.data.feedback_repository import VendorFeedbackRepository
from vendors.data import VendorRepository
from vendors.serializers.wallet import VendorWalletTransactionSerializer
from django.http import FileResponse
from vendors.actions import GenerateVendorPayoutStatementAction


class VendorPayoutStatementView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):
        document = GenerateVendorPayoutStatementAction().execute(request.user.vendor_profile, pk)
        return FileResponse(document, as_attachment=True, filename=f'settlement-{pk}.pdf', content_type='application/pdf')

class VendorPayoutListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        return VendorFinanceRepository().payouts(self.request.user.vendor_profile, self.request.query_params)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data['payout_summary'] = VendorFinanceRepository().payout_summary(request.user.vendor_profile)
        response.data['summary_scope'] = 'all_time'
        return response

class VendorWalletTransactionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorWalletTransactionSerializer

    def get_queryset(self):
        return VendorFinanceRepository().transactions(self.request.user.vendor_profile, self.request.query_params)

class VendorPayoutApproveView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        payout = UpdateVendorRecipientPayoutAction().execute(pk, 'approve', request)
        return Response(VendorPayoutSerializer(payout).data)

class VendorPayoutDeclineView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        payout = UpdateVendorRecipientPayoutAction().execute(pk, 'decline', request)
        return Response(VendorPayoutSerializer(payout).data)

class VendorPayoutVerifyCreditView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        payout = UpdateVendorRecipientPayoutAction().execute(pk, 'verify', request)
        return Response(VendorPayoutSerializer(payout).data)

class VendorCouponViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorCouponSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return VendorCouponRepository().for_vendor(self.request.user.vendor_profile, self.request.query_params)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data['summary'] = VendorCouponRepository().summary(request.user.vendor_profile)
        return response

    def perform_create(self, serializer):
        serializer.instance = VendorCouponAction().execute(self.request.user.vendor_profile, self.request.user, 'create', values=serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = VendorCouponAction().execute(self.request.user.vendor_profile, self.request.user, 'update', serializer.instance.pk, serializer.validated_data)

    def perform_destroy(self, instance):
        VendorCouponAction().execute(self.request.user.vendor_profile, self.request.user, 'delete', instance.pk)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        coupon = VendorCouponAction().execute(request.user.vendor_profile, request.user, 'duplicate', self.get_object().pk)
        return Response(self.get_serializer(coupon).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        coupon = VendorCouponAction().execute(request.user.vendor_profile, request.user, 'reactivate', self.get_object().pk)
        return Response(self.get_serializer(coupon).data)

class VendorReviewViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request, vendor_id=None):
        if not vendor_id:
            return Response({"error": "vendor_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        vendor = VendorRepository().get_by_id(vendor_id)
        if not vendor:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        is_admin = bool(getattr(request.user, "role", "") == "admin")
        is_owner = bool(
            hasattr(request.user, "vendor_profile")
            and str(request.user.vendor_profile.id) == str(vendor.id)
        )
        if not (is_admin or is_owner):
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        repository = VendorFeedbackRepository()
        queryset = repository.reviews(vendor, request.query_params)
        if is_admin and 'page' not in request.query_params:
            return Response(VendorReviewSerializer(queryset, many=True).data)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(VendorReviewSerializer(page, many=True).data)
        response.data['rating_summary'] = repository.summary(vendor)
        response.data['summary_scope'] = 'all_time'
        return response
