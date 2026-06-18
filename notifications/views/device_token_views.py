from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.actions import RegisterDeviceTokenAction


class DeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        created = RegisterDeviceTokenAction().execute(
            user=request.user,
            token=request.data.get('token'),
            platform=request.data.get('platform', 'web'),
        )
        return Response(
            {'status': 'token registered'},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
