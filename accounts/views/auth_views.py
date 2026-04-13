"""Auth views — public registration, login, and initial superuser setup."""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from accounts.actions.auth_actions import RegisterAction, LoginAction
from accounts.data.user_repository import UserRepository
from accounts.serializers.user_serializers import (
    AdminUserSerializer,
    UserProfileSerializer,
)


class RegisterView(APIView):
    """POST /api/auth/register/ — create a new customer account."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new user and return profile + JWT tokens.

        Args:
            request: DRF request containing registration payload.

        Returns:
            201 response with user data and access/refresh tokens.
        """
        result = RegisterAction(data=request.data).execute()
        return Response(result, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ — authenticate and return JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Validate credentials and issue JWT tokens.

        Args:
            request: DRF request with ``username`` and ``password`` fields.

        Returns:
            200 with user data and tokens, or 400/401 on failure.
        """
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


class SetupSuperUserView(APIView):
    """Allows creating the first superuser if none exists."""

    permission_classes = [AllowAny]

    def get(self, request):  # noqa: ARG002
        """Check whether initial superuser setup is still required.

        Args:
            request: DRF request (no authentication required).

        Returns:
            200 with ``{"needs_setup": true/false}``.
        """
        has_superuser = UserRepository.superuser_exists()
        return Response({'needs_setup': not has_superuser})

    def post(self, request):
        """Create the first superuser account.

        Args:
            request: DRF request with admin account payload.

        Returns:
            201 with profile data, or 403 if a superuser already exists.
        """
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
