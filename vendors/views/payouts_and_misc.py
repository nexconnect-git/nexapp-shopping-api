from rest_framework import generics, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from vendors.models import VendorPayout
from vendors.serializers import VendorPayoutSerializer

class VendorPayoutListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        return VendorPayout.objects.filter(vendor__user=self.request.user)

class VendorWalletTransactionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    from vendors.serializers.wallet import VendorWalletTransactionSerializer
    serializer_class = VendorWalletTransactionSerializer

    def get_queryset(self):
        from vendors.models.vendor_wallet import VendorWalletTransaction
        return VendorWalletTransaction.objects.filter(
            vendor__user=self.request.user
        ).order_by('-created_at')

class VendorPayoutApproveView(APIView):
    def post(self, request, pk):
        return Response({})

class VendorPayoutDeclineView(APIView):
    def post(self, request, pk):
        return Response({})

class VendorPayoutVerifyCreditView(APIView):
    def post(self, request, pk):
        return Response({})

class VendorCouponViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response([])

class VendorReviewViewSet(viewsets.ViewSet):
    def list(self, request, vendor_id=None):
        return Response([])
