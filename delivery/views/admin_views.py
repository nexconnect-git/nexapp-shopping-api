from django.db.models import Sum
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from delivery.actions import AdminGeneratePartnerTemporaryPasswordAction, AdminReassignDeliveryAction
from delivery.models import DeliveryEarning
from delivery.serializers import (
    DeliveryPartnerRegistrationSerializer,
    DeliveryPartnerSerializer,
)
from delivery.data.partner_repo import DeliveryPartnerRepository
from orders.serializers import OrderSerializer


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminDeliveryPartnerListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = DeliveryPartnerRepository.get_base_queryset()

        search = request.query_params.get("search")
        if search:
            qs = (
                qs.filter(user__username__icontains=search)
                | DeliveryPartnerRepository.get_base_queryset().filter(user__email__icontains=search)
                | DeliveryPartnerRepository.get_base_queryset().filter(user__first_name__icontains=search)
            ).distinct()

        is_approved = request.query_params.get("is_approved")
        if is_approved is not None:
            qs = qs.filter(is_approved=is_approved.lower() == "true")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(DeliveryPartnerSerializer(page, many=True).data)

    def post(self, request):
        serializer = DeliveryPartnerRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        data = DeliveryPartnerSerializer(partner, context={"request": request}).data
        temporary_password = (
            getattr(partner, "auto_generated_password", "")
            or data.get("user", {}).get("temp_password", "")
        )
        if temporary_password:
            data["temp_password"] = temporary_password
        return Response(data, status=status.HTTP_201_CREATED)


class AdminDeliveryPartnerDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            partner = DeliveryPartnerRepository.get_by_id(pk)
            return Response(DeliveryPartnerSerializer(partner).data)
        except Exception:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            partner = DeliveryPartnerRepository.get_by_id(pk)
        except Exception:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = DeliveryPartnerSerializer(partner, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        try:
            partner = DeliveryPartnerRepository.get_by_id(pk)
            partner.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)


class AdminDeliveryPartnerEarningsCalculationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            partner = DeliveryPartnerRepository.get_by_id(pk)
        except Exception:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        qs = DeliveryEarning.objects.filter(delivery_partner=partner)
        if start_date:
            qs = qs.filter(created_at__gte=start_date + "T00:00:00Z")
        if end_date:
            qs = qs.filter(created_at__lte=end_date + "T23:59:59Z")

        total = qs.aggregate(total_amount=Sum("amount"))["total_amount"] or 0
        return Response(
            {
                "total_amount": float(total),
                "total_deliveries": qs.count(),
            }
        )


class AdminDeliveryPartnerApprovalView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            partner = DeliveryPartnerRepository.get_by_id(pk)
        except Exception:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action == "approve":
            DeliveryPartnerRepository.update(partner, is_approved=True, status="available")
            return Response({"status": "approved", **DeliveryPartnerSerializer(partner).data})
        elif action == "reject":
            DeliveryPartnerRepository.update(partner, is_approved=False, status="offline")
            return Response({"status": "rejected", **DeliveryPartnerSerializer(partner).data})
        else:
            return Response({"error": "action must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)


class AdminDeliveryPartnerTemporaryPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            partner, temporary_password = AdminGeneratePartnerTemporaryPasswordAction.execute(pk)
        except ValueError:
            return Response({"error": "Delivery partner not found."}, status=status.HTTP_404_NOT_FOUND)

        data = DeliveryPartnerSerializer(partner, context={"request": request}).data
        data["temp_password"] = temporary_password
        return Response(data)


class AdminDeliveryReassignView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        delivery_partner_id = str(request.data.get("delivery_partner_id") or "").strip()
        reason = str(request.data.get("reason") or "").strip()
        try:
            order = AdminReassignDeliveryAction.execute(
                str(pk),
                request.user,
                delivery_partner_id=delivery_partner_id,
                reason=reason,
                request=request,
            )
            return Response(
                {
                    "status": "reassigned",
                    "order": OrderSerializer(order).data,
                }
            )
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
