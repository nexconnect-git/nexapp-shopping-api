from rest_framework import status, viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

from .models import User, Address
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    AddressSerializer,
    ChangePasswordSerializer,
    AdminUserUpdateSerializer,
    AdminUserSerializer,
)
from .permissions import IsAdminRole, IsSuperUser
from rest_framework.permissions import AllowAny, IsAuthenticated


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
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
    permission_classes = [AllowAny]

    def post(self, request):
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'current_password': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.force_password_change = False
        user.temp_password = ''
        user.save(update_fields=['password', 'force_password_change', 'temp_password'])
        return Response({'detail': 'Password updated successfully.'})


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AdminUserViewSet(viewsets.ModelViewSet):
    """GET/POST/DELETE admin and superuser accounts (superuser only)."""
    permission_classes = [IsAuthenticated, IsSuperUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(is_staff=True).order_by('-created_at')


# ── Admin views ────────────────────────────────────────────────────────────────

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminCustomerListView(APIView):
    """GET /api/admin/customers/ — list all customers (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = User.objects.filter(role='customer').order_by('-created_at')

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                username__icontains=search
            ) | User.objects.filter(
                role='customer', email__icontains=search
            ) | User.objects.filter(
                role='customer', first_name__icontains=search
            ) | User.objects.filter(
                role='customer', last_name__icontains=search
            )
            qs = qs.distinct()

        is_verified = request.query_params.get('is_verified')
        if is_verified is not None:
            qs = qs.filter(is_verified=is_verified.lower() == 'true')

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = UserProfileSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCustomerDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/customers/<id>/ — manage a single customer."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk, role='customer')
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserProfileSerializer(user).data)

    def patch(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(user).data)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserStatsView(APIView):
    """GET /api/admin/stats/ — platform-wide counts."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from orders.models import Order
        from vendors.models import Vendor
        from products.models import Product
        from delivery.models import DeliveryPartner
        from django.db.models import Sum

        revenue = Order.objects.filter(status='delivered').aggregate(total=Sum('total'))['total'] or 0

        return Response({
            'customers': User.objects.filter(role='customer').count(),
            'vendors': Vendor.objects.count(),
            'pending_vendors': Vendor.objects.filter(status='pending').count(),
            'delivery_partners': DeliveryPartner.objects.count(),
            'pending_delivery_partners': DeliveryPartner.objects.filter(is_approved=False).count(),
            'products': Product.objects.count(),
            'orders': Order.objects.count(),
            'orders_placed': Order.objects.filter(status='placed').count(),
            'orders_delivering': Order.objects.filter(status__in=['picked_up', 'on_the_way']).count(),
            'orders_delivered': Order.objects.filter(status='delivered').count(),
            'total_revenue': revenue,
        })


class SetupSuperUserView(APIView):
    """Allows creating the first superuser if none exists."""
    permission_classes = [AllowAny]

    def get(self, request):
        has_superuser = User.objects.filter(is_superuser=True).exists()
        return Response({"needs_setup": not has_superuser})

    def post(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return Response({"error": "A superuser already exists in the system."}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        data['account_type'] = 'superuser'
        
        serializer = AdminUserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
