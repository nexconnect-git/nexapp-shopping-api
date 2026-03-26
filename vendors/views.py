import math
from datetime import timedelta
from collections import defaultdict

from rest_framework import status, viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import (
    Vendor, VendorReview,
    VendorOnboarding, VendorBankDetails,
    VendorDocument, VendorServiceableArea,
    VendorHoliday, VendorAuditLog,
    VendorPayout, DeliveryPartnerPayout,
)
from .serializers import (
    VendorRegistrationSerializer,
    VendorSerializer,
    AdminVendorSerializer,
    VendorListSerializer,
    VendorReviewSerializer,
    VendorFullOnboardSerializer,
    VendorOnboardingSerializer,
    VendorBankDetailsSerializer,
    VendorDocumentSerializer,
    DocumentVerifySerializer,
    VendorServiceableAreaSerializer,
    VendorHolidaySerializer,
    VendorAuditLogSerializer,
    VendorPayoutSerializer,
    DeliveryPartnerPayoutSerializer,
)
from products.models import Product
from products.serializers import ProductSerializer, ProductCreateUpdateSerializer
from orders.models import Order
from notifications.models import Notification
from accounts.permissions import IsAdminRole, IsVendor, IsApprovedVendor
from rest_framework.pagination import PageNumberPagination


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class VendorRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        from rest_framework_simplejwt.tokens import RefreshToken
        from accounts.serializers import UserProfileSerializer
        refresh = RefreshToken.for_user(vendor.user)
        return Response(
            {
                "user": UserProfileSerializer(vendor.user).data,
                "vendor": VendorSerializer(vendor).data,
                "vendor_status": vendor.status,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VendorListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorListSerializer

    def get_queryset(self):
        qs = Vendor.objects.filter(status="approved")
        search = self.request.query_params.get("search")
        city = self.request.query_params.get("city")
        is_open = self.request.query_params.get("is_open")
        is_featured = self.request.query_params.get("is_featured")
        category = self.request.query_params.get("category")

        if search:
            qs = qs.filter(store_name__icontains=search)
        if city:
            qs = qs.filter(city__iexact=city)
        if is_open is not None:
            qs = qs.filter(is_open=is_open.lower() == "true")
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured.lower() == "true")
        if category:
            qs = qs.filter(
                Q(products__category__slug=category) |
                Q(products__category__parent__slug=category)
            ).distinct()
        return qs


class VendorDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(status="approved")

    def retrieve(self, request, *args, **kwargs):
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor).data
        products = Product.objects.filter(vendor=vendor, is_available=True)
        vendor_data["products"] = ProductSerializer(products, many=True).data
        return Response(vendor_data)


class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        vendor = request.user.vendor_profile
        total_orders = Order.objects.filter(vendor=vendor).count()
        total_products = Product.objects.filter(vendor=vendor).count()
        recent_orders = Order.objects.filter(vendor=vendor).order_by("-placed_at")[:10]

        from orders.serializers import OrderSerializer

        return Response(
            {
                "total_orders": total_orders,
                "total_products": total_products,
                "average_rating": vendor.average_rating,
                "total_ratings": vendor.total_ratings,
                "recent_orders": OrderSerializer(recent_orders, many=True).data,
            }
        )


class VendorProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductCreateUpdateSerializer
        return ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)


class VendorOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get_queryset(self):
        qs = Order.objects.filter(vendor=self.request.user.vendor_profile)
        order_status = self.request.query_params.get("status")
        if order_status:
            qs = qs.filter(status=order_status)
        return qs

    def get_serializer_class(self):
        from orders.serializers import OrderSerializer

        return OrderSerializer


class VendorUpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        try:
            order = Order.objects.get(
                pk=pk, vendor=request.user.vendor_profile
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        allowed_transitions = {
            "placed": ["confirmed", "cancelled"],
            "confirmed": ["preparing", "cancelled"],
            "preparing": ["ready"],
        }
        current_allowed = allowed_transitions.get(order.status, [])
        if new_status not in current_allowed:
            return Response(
                {"error": f"Cannot transition from '{order.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate OTP when marking ready for delivery
        if new_status == "ready":
            import random
            order.delivery_otp = str(random.randint(100000, 999999))

        order.status = new_status
        order.save(update_fields=["status", "delivery_otp", "updated_at"])

        from orders.models import OrderTracking

        description_map = {
            "confirmed": "Order confirmed by vendor.",
            "preparing": "Order is being prepared.",
            "ready": "Order is ready for pickup by delivery partner.",
            "cancelled": "Order was rejected/cancelled by vendor.",
        }
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            description=description_map.get(new_status, f"Order {new_status} by vendor."),
        )

        status_messages = {
            "confirmed": "Your order has been confirmed by the vendor.",
            "preparing": "Your order is being prepared.",
            "ready": "Your order is ready! A delivery partner will pick it up soon.",
            "cancelled": f"Your order #{order.order_number} was cancelled by the vendor.",
        }
        Notification.objects.create(
            user=order.customer,
            title=f"Order {new_status.capitalize()}",
            message=status_messages.get(new_status, f"Your order status is now {new_status}."),
            notification_type="order",
            data={"order_id": str(order.id), "order_number": order.order_number},
        )

        from orders.serializers import OrderSerializer

        return Response(OrderSerializer(order).data)


class VendorProfileView(APIView):
    """GET/PATCH /api/vendors/profile/ — authenticated vendor's own profile."""
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        vendor = request.user.vendor_profile
        return Response(VendorSerializer(vendor).data)

    def patch(self, request):
        vendor = request.user.vendor_profile
        serializer = VendorSerializer(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NearbyVendorsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return Response(
                {"error": "lat and lng query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        radius_km = float(request.query_params.get("radius_km", 5))
        vendors = Vendor.objects.filter(status="approved")
        category = request.query_params.get("category")
        if category:
            vendors = vendors.filter(
                Q(products__category__slug=category) |
                Q(products__category__parent__slug=category)
            ).distinct()
        nearby = []

        for vendor in vendors:
            distance = haversine(
                lat, lng, float(vendor.latitude), float(vendor.longitude)
            )
            if distance <= radius_km:
                vendor_data = VendorListSerializer(vendor).data
                vendor_data["distance_km"] = round(distance, 2)
                nearby.append(vendor_data)

        nearby.sort(key=lambda v: v["distance_km"])
        return Response(nearby)


class AdminVendorListView(APIView):
    """GET/POST /api/admin/vendors/ — list all vendors or create one (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Vendor.objects.select_related('user').order_by('-created_at')
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(store_name__icontains=search) | Vendor.objects.filter(city__icontains=search)
            qs = qs.distinct()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AdminVendorSerializer(page, many=True).data)

    def post(self, request):
        """Create a new vendor (user + vendor profile) as admin."""
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        return Response(AdminVendorSerializer(vendor).data, status=status.HTTP_201_CREATED)


class AdminVendorDetailView(APIView):
    """GET/PATCH/DELETE /api/admin/vendors/<id>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get(self, pk):
        try:
            return Vendor.objects.select_related('user').get(pk=pk)
        except Vendor.DoesNotExist:
            return None

    def get(self, request, pk):
        vendor = self._get(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminVendorSerializer(vendor).data)

    def patch(self, request, pk):
        vendor = self._get(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminVendorSerializer(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        vendor = self._get(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        vendor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorStatusView(APIView):
    """POST /api/admin/vendors/<id>/status/ — approve/reject/suspend a vendor."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk)
        except Vendor.DoesNotExist:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        new_status = request.data.get('status')
        allowed = ['pending', 'approved', 'rejected', 'suspended']
        if new_status not in allowed:
            return Response({'error': f"status must be one of: {', '.join(allowed)}"}, status=status.HTTP_400_BAD_REQUEST)
        vendor.status = new_status
        vendor.save(update_fields=['status'])
        return Response(VendorSerializer(vendor).data)


class VendorReviewViewSet(viewsets.ModelViewSet):
    serializer_class = VendorReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        vendor_id = self.kwargs.get("vendor_id")
        if vendor_id:
            return VendorReview.objects.filter(vendor_id=vendor_id)
        return VendorReview.objects.all()

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


# ── Admin Onboarding Views ────────────────────────────────────────────────────

def _get_vendor_or_404(pk):
    try:
        return Vendor.objects.select_related('user').get(pk=pk)
    except Vendor.DoesNotExist:
        return None


def _log(vendor, action, description, request=None, metadata=None):
    ip = None
    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
    VendorAuditLog.objects.create(
        vendor=vendor,
        action=action,
        description=description,
        performed_by=request.user if request else None,
        ip_address=ip,
        metadata=metadata,
    )


class AdminVendorOnboardView(APIView):
    """
    POST /api/admin/vendors/onboard/
    Full vendor creation: user account + store + onboarding + bank + areas + holidays.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = VendorFullOnboardSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        data = AdminVendorSerializer(vendor).data
        if hasattr(vendor, 'auto_generated_password'):
            data['temp_password'] = vendor.auto_generated_password
        return Response(data, status=status.HTTP_201_CREATED)


class AdminVendorOnboardingDetailView(APIView):
    """GET/PATCH /api/admin/vendors/<pk>/onboarding/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)
        return Response(VendorOnboardingSerializer(onboarding).data)

    def patch(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)
        serializer = VendorOnboardingSerializer(onboarding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(vendor, 'profile_updated', 'Onboarding details updated.', request)
        return Response(serializer.data)


class AdminVendorKYCReviewView(APIView):
    """POST /api/admin/vendors/<pk>/kyc-review/  — approve or reject KYC"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

        action   = request.data.get('action')
        reason   = request.data.get('rejection_reason', '')
        allowed  = ('approve', 'reject')
        if action not in allowed:
            return Response({'error': f'action must be one of: {", ".join(allowed)}'}, status=status.HTTP_400_BAD_REQUEST)
        if action == 'reject' and not reason.strip():
            return Response({'error': 'rejection_reason is required when rejecting.'}, status=status.HTTP_400_BAD_REQUEST)

        onboarding, _ = VendorOnboarding.objects.get_or_create(vendor=vendor)
        if action == 'approve':
            onboarding.kyc_status        = 'verified'
            onboarding.onboarding_status = 'approved'
            onboarding.rejection_reason  = ''
            vendor.status = 'approved'
            vendor.save(update_fields=['status'])
            audit_action = 'kyc_approved'
            desc = 'KYC verified and vendor account approved.'
        else:
            onboarding.kyc_status        = 'rejected'
            onboarding.onboarding_status = 'rejected'
            onboarding.rejection_reason  = reason
            vendor.status = 'rejected'
            vendor.save(update_fields=['status'])
            audit_action = 'kyc_rejected'
            desc = f'KYC rejected: {reason}'

        onboarding.reviewed_at = timezone.now()
        onboarding.reviewed_by = request.user
        onboarding.save()
        _log(vendor, audit_action, desc, request)

        return Response(VendorOnboardingSerializer(onboarding).data)


class AdminVendorBankDetailsView(APIView):
    """GET/PUT /api/admin/vendors/<pk>/bank/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        bank, _ = VendorBankDetails.objects.get_or_create(vendor=vendor)
        return Response(VendorBankDetailsSerializer(bank).data)

    def put(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        bank, created = VendorBankDetails.objects.get_or_create(vendor=vendor)
        serializer = VendorBankDetailsSerializer(bank, data=request.data, partial=not created)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(vendor, 'bank_updated', 'Bank details updated.', request)
        return Response(serializer.data)


class AdminVendorBankVerifyView(APIView):
    """POST /api/admin/vendors/<pk>/bank/verify/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            bank = vendor.bank_details
        except VendorBankDetails.DoesNotExist:
            return Response({'error': 'Bank details not found.'}, status=status.HTTP_404_NOT_FOUND)
        bank.is_verified = True
        bank.save(update_fields=['is_verified'])
        _log(vendor, 'bank_verified', 'Bank details verified.', request)
        return Response(VendorBankDetailsSerializer(bank).data)


class AdminVendorDocumentListView(APIView):
    """GET/POST /api/admin/vendors/<pk>/documents/"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        docs = VendorDocument.objects.filter(vendor=vendor)
        return Response(VendorDocumentSerializer(docs, many=True).data)

    def post(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=vendor)
        _log(vendor, 'document_uploaded',
             f'Document uploaded: {serializer.instance.get_document_type_display()}', request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminVendorDocumentVerifyView(APIView):
    """POST /api/admin/vendors/<pk>/documents/<doc_pk>/verify/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk, doc_pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            doc = VendorDocument.objects.get(pk=doc_pk, vendor=vendor)
        except VendorDocument.DoesNotExist:
            return Response({'error': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DocumentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['action'] == 'verify':
            doc.status          = 'verified'
            doc.rejection_reason= ''
            doc.verified_by     = request.user
            doc.verified_at     = timezone.now()
            audit_action = 'document_verified'
            desc = f'Document verified: {doc.get_document_type_display()}'
        else:
            doc.status           = 'rejected'
            doc.rejection_reason = serializer.validated_data['rejection_reason']
            doc.verified_by      = request.user
            doc.verified_at      = timezone.now()
            audit_action = 'document_rejected'
            desc = f'Document rejected: {doc.get_document_type_display()} — {doc.rejection_reason}'

        doc.save()
        _log(vendor, audit_action, desc, request)
        return Response(VendorDocumentSerializer(doc).data)


class AdminVendorServiceableAreaView(APIView):
    """GET/POST /api/admin/vendors/<pk>/serviceable-areas/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        areas = VendorServiceableArea.objects.filter(vendor=vendor)
        return Response(VendorServiceableAreaSerializer(areas, many=True).data)

    def post(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorServiceableAreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, created = VendorServiceableArea.objects.get_or_create(
            vendor=vendor,
            pincode=serializer.validated_data['pincode'],
            defaults={
                'city':  serializer.validated_data.get('city', ''),
                'state': serializer.validated_data.get('state', ''),
            }
        )
        if created:
            _log(vendor, 'serviceable_area_added', f'Pincode {obj.pincode} added.', request)
        return Response(VendorServiceableAreaSerializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdminVendorServiceableAreaDetailView(APIView):
    """DELETE /api/admin/vendors/<pk>/serviceable-areas/<area_pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk, area_pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            area = VendorServiceableArea.objects.get(pk=area_pk, vendor=vendor)
        except VendorServiceableArea.DoesNotExist:
            return Response({'error': 'Area not found.'}, status=status.HTTP_404_NOT_FOUND)
        area.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorHolidayView(APIView):
    """GET/POST /api/admin/vendors/<pk>/holidays/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        holidays = VendorHoliday.objects.filter(vendor=vendor)
        return Response(VendorHolidaySerializer(holidays, many=True).data)

    def post(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, created = VendorHoliday.objects.get_or_create(
            vendor=vendor,
            date=serializer.validated_data['date'],
            defaults={'reason': serializer.validated_data.get('reason', '')}
        )
        _log(vendor, 'holiday_added', f'Holiday on {obj.date} added.', request)
        return Response(VendorHolidaySerializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdminVendorHolidayDetailView(APIView):
    """DELETE /api/admin/vendors/<pk>/holidays/<holiday_pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk, holiday_pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            holiday = VendorHoliday.objects.get(pk=holiday_pk, vendor=vendor)
        except VendorHoliday.DoesNotExist:
            return Response({'error': 'Holiday not found.'}, status=status.HTTP_404_NOT_FOUND)
        holiday.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorAuditLogView(APIView):
    """GET /api/admin/vendors/<pk>/audit-logs/"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
        logs = VendorAuditLog.objects.filter(vendor=vendor)
        return Response(VendorAuditLogSerializer(logs, many=True).data)


class AdminVendorSalesReportView(APIView):
    """GET /api/admin/vendors/<pk>/sales-report/?period=30d|90d|12m"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        from orders.models import Order, OrderItem
        vendor = _get_vendor_or_404(pk)
        if not vendor:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

        period = request.query_params.get('period', '30d')
        now = timezone.now()
        if period == '90d':
            start_date = now - timedelta(days=90)
        elif period == '12m':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)

        orders = Order.objects.filter(vendor=vendor, placed_at__gte=start_date)

        total_revenue = orders.exclude(status='cancelled').aggregate(
            rev=Sum('total'))['rev'] or 0
        total_orders = orders.count()
        delivered_orders = orders.filter(status='delivered').count()
        cancelled_orders = orders.filter(status='cancelled').count()
        avg_order_value = (float(total_revenue) / (total_orders - cancelled_orders)
                           if (total_orders - cancelled_orders) > 0 else 0)

        orders_by_status = dict(
            orders.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )

        monthly_data_qs = (
            orders.exclude(status='cancelled')
            .annotate(month=TruncMonth('placed_at'))
            .values('month')
            .annotate(revenue=Sum('total'), order_count=Count('id'))
            .order_by('month')
        )
        monthly_data = [
            {
                'month': entry['month'].strftime('%Y-%m'),
                'revenue': float(entry['revenue'] or 0),
                'orders': entry['order_count'],
            }
            for entry in monthly_data_qs
        ]

        top_products = (
            OrderItem.objects.filter(order__vendor=vendor, order__placed_at__gte=start_date)
            .exclude(order__status='cancelled')
            .values('product_id', 'product_name')
            .annotate(total_sold=Sum('quantity'), revenue=Sum('subtotal'))
            .order_by('-revenue')[:10]
        )
        top_products_data = [
            {
                'product_id': str(p['product_id']),
                'name': p['product_name'],
                'total_sold': p['total_sold'],
                'revenue': float(p['revenue'] or 0),
            }
            for p in top_products
        ]

        return Response({
            'total_revenue': float(total_revenue),
            'total_orders': total_orders,
            'delivered_orders': delivered_orders,
            'cancelled_orders': cancelled_orders,
            'average_order_value': round(avg_order_value, 2),
            'orders_by_status': orders_by_status,
            'monthly_data': monthly_data,
            'top_products': top_products_data,
        })


# ── Payout Views ──────────────────────────────────────────────────────────────

class VendorPayoutListView(generics.ListAPIView):
    """GET /api/vendors/payouts/"""
    permission_classes = [IsAuthenticated, IsApprovedVendor]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        return VendorPayout.objects.filter(vendor=self.request.user.vendor_profile)


class AdminVendorPayoutListView(generics.ListCreateAPIView):
    """GET/POST /api/admin/payouts/vendors/"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VendorPayoutSerializer

    def get_queryset(self):
        qs = VendorPayout.objects.select_related('vendor').all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        vid = self.request.query_params.get('vendor_id')
        if vid:
            qs = qs.filter(vendor_id=vid)
        return qs


class AdminVendorPayoutDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/admin/payouts/vendors/<pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VendorPayoutSerializer
    queryset = VendorPayout.objects.all()


class AdminDeliveryPayoutListView(generics.ListCreateAPIView):
    """GET/POST /api/admin/payouts/delivery/"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DeliveryPartnerPayoutSerializer

    def get_queryset(self):
        qs = DeliveryPartnerPayout.objects.select_related('delivery_partner').all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        partner_id = self.request.query_params.get('partner_id')
        if partner_id:
            qs = qs.filter(delivery_partner_id=partner_id)
        return qs


class AdminDeliveryPayoutDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/admin/payouts/delivery/<pk>/"""
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DeliveryPartnerPayoutSerializer
    queryset = DeliveryPartnerPayout.objects.all()

