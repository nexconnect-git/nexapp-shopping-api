"""Views for the accounts app.

Covers public auth (register, login), authenticated profile management,
address CRUD, admin user management, and platform statistics.
"""

from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

from accounts.models import User, Address
from accounts.permissions import IsAdminRole, IsSuperUser
from accounts.serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    AddressSerializer,
    ChangePasswordSerializer,
    AdminUserUpdateSerializer,
    AdminUserSerializer,
)
from accounts.services import AccountService
from backend.mixins import BaseDetailView


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
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


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
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            }
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
            AccountService.change_user_password(
                request.user,
                serializer.validated_data["current_password"],
                serializer.validated_data["new_password"],
            )
            return Response({"detail": "Password updated successfully."})
        except ValueError as e:
            return Response(
                {"current_password": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing the current user's delivery addresses."""

    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return addresses belonging to the authenticated user."""
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Attach the current user to the new address on save."""
        serializer.save(user=self.request.user)


class AdminUserViewSet(viewsets.ModelViewSet):
    """GET/POST/DELETE admin and superuser accounts (superuser only)."""

    permission_classes = [IsAuthenticated, IsSuperUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        """Return all staff users ordered by creation date (newest first)."""
        return User.objects.filter(is_staff=True).order_by("-created_at")


# ── Admin views ────────────────────────────────────────────────────────────────

class StandardPagination(PageNumberPagination):
    """Default pagination class for admin list views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminCustomerListView(APIView):
    """GET /api/admin/customers/ — list all customers (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return a paginated, optionally filtered list of customers.

        Query params:
            search: Filter by username, email, first name, or last name.
            is_verified: Filter by email-verification status (true/false).

        Args:
            request: Authenticated admin DRF request.

        Returns:
            Paginated list of customer profiles.
        """
        qs = User.objects.filter(role="customer").order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            qs = (
                qs.filter(username__icontains=search)
                | User.objects.filter(role="customer", email__icontains=search)
                | User.objects.filter(
                    role="customer", first_name__icontains=search
                )
                | User.objects.filter(
                    role="customer", last_name__icontains=search
                )
            )
            qs = qs.distinct()

        is_verified = request.query_params.get("is_verified")
        if is_verified is not None:
            qs = qs.filter(is_verified=is_verified.lower() == "true")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = UserProfileSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCustomerDetailView(BaseDetailView, APIView):
    """GET/PATCH/DELETE /api/admin/customers/<id>/ — manage a single customer."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_user(self, pk):
        """Look up a customer by PK using the BaseDetailView mixin.

        Args:
            pk: UUID primary key of the user.

        Returns:
            The ``User`` instance or ``None``.
        """
        return self.get_object_or_none(User, pk=pk, role="customer")

    def get(self, request, pk):  # noqa: ARG002
        """Return a single customer's profile.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the customer.

        Returns:
            200 with profile data, or 404.
        """
        user = self._get_user(pk)
        if not user:
            return Response(
                {"error": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(UserProfileSerializer(user).data)

    def patch(self, request, pk):
        """Partially update a customer account.

        Args:
            request: Authenticated admin DRF request with fields to update.
            pk: UUID primary key of the customer.

        Returns:
            200 with updated profile, or 400/404.
        """
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = AccountService.update_admin_customer(
                str(pk), serializer.validated_data
            )
            return Response(UserProfileSerializer(user).data)
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, pk):  # noqa: ARG002
        """Delete a customer account.

        Args:
            request: Authenticated admin DRF request.
            pk: UUID primary key of the customer.

        Returns:
            204 on success, or 404.
        """
        user = self._get_user(pk)
        if not user:
            return Response(
                {"error": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserStatsView(APIView):
    """GET /api/admin/stats/ — platform-wide counts."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):  # noqa: ARG002
        """Return aggregated platform statistics.

        Args:
            request: Authenticated admin DRF request.

        Returns:
            200 with statistics dictionary.
        """
        return Response(AccountService.get_admin_stats())


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
        has_superuser = User.objects.filter(is_superuser=True).exists()
        return Response({"needs_setup": not has_superuser})

    def post(self, request):
        """Create the first superuser account.

        Args:
            request: DRF request with admin account payload.

        Returns:
            201 with profile data, or 403 if a superuser already exists.
        """
        if User.objects.filter(is_superuser=True).exists():
            return Response(
                {"error": "A superuser already exists in the system."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data["account_type"] = "superuser"

        serializer = AdminUserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserProfileSerializer(user).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
