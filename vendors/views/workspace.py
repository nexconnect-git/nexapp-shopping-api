from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedVendor, IsVendor
from support.serializers import SupportTicketSerializer
from vendors.actions import ContactVendorOnboardingAction, GetVendorWorkspaceAction, ReviewVendorInventoryAction, UploadOwnVendorDocumentAction
from vendors.data.workspace_repository import VendorWorkspaceRepository
from vendors.serializers.onboarding import VendorDocumentSerializer
from vendors.serializers.workspace import InventoryReviewSerializer, OnboardingDocumentUploadSerializer


class VendorWorkspaceView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        return Response(GetVendorWorkspaceAction().execute(request.user.vendor_profile))


class VendorInventoryReviewView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        serializer = InventoryReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ReviewVendorInventoryAction().execute(request.user.vendor_profile, serializer.validated_data))


class VendorOwnDocumentsView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        documents = VendorWorkspaceRepository().documents(request.user.vendor_profile)
        return Response(VendorDocumentSerializer(documents, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = OnboardingDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = UploadOwnVendorDocumentAction().execute(request.user.vendor_profile, serializer.validated_data)
        return Response(VendorDocumentSerializer(document, context={'request': request}).data, status=201)


class VendorOnboardingContactView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = ContactVendorOnboardingAction().execute(request.user.vendor_profile, serializer.validated_data)
        return Response(SupportTicketSerializer(ticket).data, status=201)
