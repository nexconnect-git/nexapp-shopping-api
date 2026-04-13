"""Profile views — authenticated profile management and password change."""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.actions.profile_actions import ChangePasswordAction
from accounts.serializers.user_serializers import (
    ChangePasswordSerializer,
    UserProfileSerializer,
)


class ProfileView(APIView):
    """GET/PUT /api/auth/profile/ — view or update the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the current user's profile.

        Args:
            request: Authenticated DRF request.

        Returns:
            200 with serialised user profile.
        """
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        """Partially update the current user's profile.

        Args:
            request: Authenticated DRF request with fields to update.

        Returns:
            200 with updated profile data.
        """
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — change the authenticated user's password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Verify the current password and set a new one.

        Args:
            request: Authenticated DRF request with ``current_password``
                and ``new_password``.

        Returns:
            200 on success, 400 if the current password is wrong.
        """
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ChangePasswordAction(
                user=request.user,
                current_password=serializer.validated_data['current_password'],
                new_password=serializer.validated_data['new_password'],
            ).execute()
            return Response({'detail': 'Password updated successfully.'})
        except ValueError as exc:
            return Response(
                {'current_password': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
