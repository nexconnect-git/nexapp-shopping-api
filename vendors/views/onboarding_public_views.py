from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.actions.admin_actions import CheckUserAvailabilityAction
from accounts.serializers import UserProfileSerializer
from vendors.actions import SendVendorSelfRegistrationEmailsAction
from vendors.serializers.public import VendorRegistrationSerializer, VendorSerializer


class VendorRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        SendVendorSelfRegistrationEmailsAction().execute(vendor)
        refresh = RefreshToken.for_user(vendor.user)
        return Response(
            {
                'user': UserProfileSerializer(vendor.user).data,
                'vendor': VendorSerializer(vendor).data,
                'vendor_status': vendor.status,
                'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)},
            },
            status=status.HTTP_201_CREATED,
        )


class VendorIdentityAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = CheckUserAvailabilityAction().execute(
                field=request.data.get('field', ''),
                value=request.data.get('value', ''),
                role='vendor',
            )
            return Response(result)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
