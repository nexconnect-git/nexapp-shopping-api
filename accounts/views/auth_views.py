"""Auth views — public registration, login, email verification, and superuser setup."""

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts.actions.auth_actions import (
    LoginAction,
    RegisterAction,
    SendVerificationEmailAction,
    VerifyEmailAction,
)
from accounts.data.user_repository import UserRepository
from accounts.serializers.user_serializers import (
    AdminUserSerializer,
    UserProfileSerializer,
)


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class RegisterView(APIView):
    """POST /api/auth/register/ — create a new customer account (10/hour per IP)."""

    permission_classes = [AllowAny]

    def post(self, request):
        result = RegisterAction(data=request.data).execute()
        return Response(result, status=status.HTTP_201_CREATED)


@method_decorator(ratelimit(key='ip', rate='20/h', method='POST', block=True), name='post')
class LoginView(APIView):
    """POST /api/auth/login/ — authenticate and return JWT tokens (20/hour per IP)."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        try:
            result = LoginAction(username=username, password=password).execute()
            return Response(result)
        except ValueError as exc:
            msg = str(exc)
            if 'required' in msg:
                return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': msg}, status=status.HTTP_401_UNAUTHORIZED)


class SendVerificationEmailView(APIView):
    """POST /api/auth/send-verification-email/ — (re)send OTP to the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            SendVerificationEmailAction(request.user).execute()
            return Response({'detail': 'Verification email sent.'})
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — submit OTP and mark email as verified."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        otp = request.data.get('otp', '').strip()
        if not otp:
            return Response({'error': 'OTP is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            VerifyEmailAction(request.user, otp).execute()
            return Response({'detail': 'Email verified successfully.'})
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token so it cannot be reused."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_205_RESET_CONTENT)


class SetupSuperUserView(APIView):
    """Allows creating the first superuser if none exists."""

    permission_classes = [AllowAny]

    def get(self, _request):
        has_superuser = UserRepository.superuser_exists()
        return Response({'needs_setup': not has_superuser})

    def post(self, request):
        if UserRepository.superuser_exists():
            return Response(
                {'error': 'A superuser already exists in the system.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data['account_type'] = 'superuser'

        serializer = AdminUserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserProfileSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
