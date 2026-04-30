"""Auth views for registration, login, token refresh, and initial setup."""

import hmac

from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.actions.auth_actions import (
    LoginAction,
    RegisterAction,
    RequestMobileOTPAction,
    SendVerificationEmailAction,
    VerifyMobileOTPAction,
    VerifyEmailAction,
)
from accounts.data.user_repository import UserRepository
from accounts.helpers.token_helpers import clear_refresh_cookie, set_refresh_cookie
from accounts.serializers.user_serializers import AdminUserSerializer, UserProfileSerializer


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class RegisterView(APIView):
    """Create a new customer account and issue an access token."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = RegisterAction(data=request.data).execute()
            refresh_token = result['tokens'].pop('refresh')
            response = Response(result, status=status.HTTP_201_CREATED)
            set_refresh_cookie(response, refresh_token)
            return response
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ratelimit(key='ip', rate='20/h', method='POST', block=True), name='post')
class LoginView(APIView):
    """Authenticate the user and set the refresh cookie."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        try:
            result = LoginAction(username=username, password=password).execute()
            refresh_token = result['tokens'].pop('refresh')
            response = Response(result)
            set_refresh_cookie(response, refresh_token)
            return response
        except ValueError as exc:
            msg = str(exc)
            if 'required' in msg:
                return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': msg}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(ratelimit(key='ip', rate='20/h', method='POST', block=True), name='post')
class RequestLoginOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = RequestMobileOTPAction(request.data, purpose='login').execute()
            return Response(result)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ratelimit(key='ip', rate='20/h', method='POST', block=True), name='post')
class VerifyLoginOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = VerifyMobileOTPAction(request.data, purpose='login').execute()
            refresh_token = result['tokens'].pop('refresh')
            response = Response(result)
            set_refresh_cookie(response, refresh_token)
            return response
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class RequestRegisterOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = RequestMobileOTPAction(request.data, purpose='register').execute()
            return Response(result)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class VerifyRegisterOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = VerifyMobileOTPAction(request.data, purpose='register').execute()
            refresh_token = result['tokens'].pop('refresh')
            response = Response(result, status=status.HTTP_201_CREATED)
            set_refresh_cookie(response, refresh_token)
            return response
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class SendVerificationEmailView(APIView):
    """Re-send the email verification OTP to the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            SendVerificationEmailAction(request.user).execute()
            return Response({'detail': 'Verification email sent.'})
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    """Submit an OTP and mark the current user's email as verified."""

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
    """Blacklist the refresh token and clear the refresh cookie."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh') or request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({'error': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = Response({'detail': 'Logged out successfully.'}, status=status.HTTP_205_RESET_CONTENT)
        clear_refresh_cookie(response)
        return response


class CookieTokenRefreshView(APIView):
    """Issue a fresh access token using the HttpOnly refresh cookie."""

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh') or request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({'error': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        serializer.is_valid(raise_exception=True)

        response = Response({'tokens': {'access': serializer.validated_data['access']}})
        rotated_refresh = serializer.validated_data.get('refresh')
        if rotated_refresh:
            set_refresh_cookie(response, rotated_refresh)
        return response


@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='post')
class SetupSuperUserView(APIView):
    """Create the first superuser only while bootstrap setup is enabled."""

    permission_classes = [AllowAny]

    @staticmethod
    def _get_setup_token(request):
        header_token = request.headers.get('X-Setup-Token', '').strip()
        body_token = str(request.data.get('setup_token', '')).strip()
        return header_token or body_token

    @staticmethod
    def _is_valid_setup_token(candidate_token):
        configured_token = settings.INITIAL_SUPERUSER_SETUP_TOKEN.strip()
        return bool(candidate_token and configured_token and hmac.compare_digest(candidate_token, configured_token))

    def get(self, _request):
        if not settings.INITIAL_SUPERUSER_SETUP_ENABLED:
            return Response({'detail': 'Initial setup is disabled.'}, status=status.HTTP_404_NOT_FOUND)

        has_superuser = UserRepository.superuser_exists()
        return Response({'needs_setup': not has_superuser})

    def post(self, request):
        if not settings.INITIAL_SUPERUSER_SETUP_ENABLED:
            return Response({'detail': 'Initial setup is disabled.'}, status=status.HTTP_404_NOT_FOUND)

        if UserRepository.superuser_exists():
            return Response(
                {'error': 'A superuser already exists in the system.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not self._is_valid_setup_token(self._get_setup_token(request)):
            return Response(
                {'error': 'A valid setup token is required.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data['account_type'] = 'superuser'
        data.pop('setup_token', None)

        serializer = AdminUserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
