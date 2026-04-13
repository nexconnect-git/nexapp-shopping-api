from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from delivery.serializers import AssetSerializer
from delivery.data.asset_repo import AssetRepository


class AdminAssetListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = AssetRepository.get_all(
            asset_type=request.query_params.get("type"),
            status=request.query_params.get("status"),
            assigned_to=request.query_params.get("assigned_to"),
        )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AssetSerializer(page, many=True).data)

    def post(self, request):
        serializer = AssetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminAssetDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        try:
            asset = AssetRepository.get_by_id(pk, select_related=["assigned_to__user"])
            return Response(AssetSerializer(asset).data)
        except Exception:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            asset = AssetRepository.get_by_id(pk, select_related=["assigned_to__user"])
        except Exception:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = AssetSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        try:
            asset = AssetRepository.get_by_id(pk)
            asset.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
