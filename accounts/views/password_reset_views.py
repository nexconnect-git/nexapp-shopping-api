import logging
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from accounts.actions import RequestAccountPasswordResetAction, ConfirmAccountPasswordResetAction

logger = logging.getLogger(__name__)

class ResetThrottle(AnonRateThrottle):
    rate = '5/hour'

class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResetThrottle]

    def post(self, request):
        email = str(request.data.get('email') or '').strip().lower()
        role = request.data.get('role', '')
        if email and role in ('', 'customer', 'vendor', 'delivery', 'admin'):
            try:
                RequestAccountPasswordResetAction().execute(email=email, role=role)
            except Exception:
                logger.warning('Self-service password reset could not be delivered.')
        return Response({'detail': 'If that account is eligible, a reset link has been sent.'})

class ResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)

class ConfirmPasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResetThrottle]

    def post(self, request):
        data = ResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        ConfirmAccountPasswordResetAction().execute(**data.validated_data)
        return Response({'detail': 'Password changed. Sign in again to continue.'})
