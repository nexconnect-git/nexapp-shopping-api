"""Auth views for registration, login, token refresh, and initial setup."""

import hmac

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.actions.auth_actions import (
    LoginAction,
    RegisterAction,
    RequestMobileOTPAction,
    SendVerificationEmailAction,
    SetupSuperUserAction,
    VerifyMobileOTPAction,
    VerifyEmailAction,
)
from accounts.data.user_repository import UserRepository
from accounts.helpers.token_helpers import clear_refresh_cookie, set_refresh_cookie
from accounts.serializers.user_serializers import UserProfileSerializer


def _without_refresh_token(payload: dict) -> dict:
    response_payload = payload.copy()
    tokens = response_payload.get('tokens')
    if isinstance(tokens, dict):
        response_payload['tokens'] = tokens.copy()
        response_payload['tokens'].pop('refresh', None)
    return response_payload


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class RegisterView(APIView):
    """Create a new customer account and issue an access token."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = RegisterAction(data=request.data).execute()
            refresh_token = result['tokens']['refresh']
            response = Response(_without_refresh_token(result), status=status.HTTP_201_CREATED)
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
            refresh_token = result['tokens']['refresh']
            response = Response(_without_refresh_token(result))
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
            refresh_token = result['tokens']['refresh']
            response = Response(_without_refresh_token(result))
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
            refresh_token = result['tokens']['refresh']
            response = Response(_without_refresh_token(result), status=status.HTTP_201_CREATED)
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

        user = None
        try:
            user_id = RefreshToken(refresh_token).get(settings.SIMPLE_JWT['USER_ID_CLAIM'])
            if user_id:
                user = UserProfileSerializer.Meta.model.objects.filter(pk=user_id).first()
        except TokenError:
            response = Response({'error': 'Refresh token is invalid or expired.'}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError, ObjectDoesNotExist):
            response = Response({'error': 'Refresh token is invalid or expired.'}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response

        response_tokens = {'access': serializer.validated_data['access']}
        rotated_refresh = serializer.validated_data.get('refresh')
        response = Response({
            'tokens': response_tokens,
            'user': UserProfileSerializer(user).data if user else None,
        })
        if rotated_refresh:
            set_refresh_cookie(response, rotated_refresh)
        return response


@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='post')
class SetupSuperUserView(APIView):
    """Create the first superuser only when no superuser exists."""

    permission_classes = [AllowAny]

    def get(self, _request):
        has_superuser = UserRepository.superuser_exists()
        return Response({'needs_setup': not has_superuser})

    def post(self, request):
        if not getattr(settings, 'INITIAL_SUPERUSER_SETUP_ENABLED', False):
            raise Http404

        expected_token = getattr(settings, 'INITIAL_SUPERUSER_SETUP_TOKEN', '')
        supplied_token = request.data.get('setup_token') or request.headers.get('X-Setup-Token') or ''
        if not expected_token or not hmac.compare_digest(str(supplied_token), str(expected_token)):
            return Response({'error': 'A valid setup token is required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = SetupSuperUserAction(data=request.data).execute()
            return Response(result, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
