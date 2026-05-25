"""Public banner endpoint for the customer app home carousel."""

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers, status

from accounts.permissions import IsAdminRole
from helpers.cache_helpers import cached_api_response
from helpers.serializer_fields import SafeImageField
from helpers.validators import validate_image_upload
from orders.data.banner_repo import PlatformBannerRepository
from orders.models import PlatformBanner


class PlatformBannerSerializer(serializers.ModelSerializer):
    image = SafeImageField(read_only=True)

    class Meta:
        model = PlatformBanner
        fields = ['id', 'title', 'subtitle', 'badge_text', 'cta_label', 'cta_url', 'image', 'bg_gradient']


class AdminPlatformBannerSerializer(serializers.ModelSerializer):
    image = SafeImageField(required=False, allow_null=True)

    class Meta:
        model = PlatformBanner
        fields = [
            'id', 'title', 'subtitle', 'badge_text', 'cta_label', 'cta_url',
            'image', 'bg_gradient', 'display_order', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_image(self, value):
        if value:
            try:
                validate_image_upload(value, label="banner image")
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return value


class BannerListView(APIView):
    """GET /api/orders/banners/ — returns active banners ordered by display_order."""
    permission_classes = [AllowAny]

    def get(self, request):
        return cached_api_response(
            request,
            'orders:banners',
            300,
            lambda: self._get_uncached(request),
            include_user=False,
        )

    def _get_uncached(self, request):
        banners = PlatformBannerRepository.get_active()
        return Response(PlatformBannerSerializer(banners, many=True, context={'request': request}).data)


class AdminBannerListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        banners = PlatformBannerRepository.get_all()
        return Response(AdminPlatformBannerSerializer(banners, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = AdminPlatformBannerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminBannerDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        return PlatformBannerRepository.get_by_id(pk)

    def get(self, request, pk):
        banner = self._get_object(pk)
        if not banner:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminPlatformBannerSerializer(banner, context={'request': request}).data)

    def patch(self, request, pk):
        banner = self._get_object(pk)
        if not banner:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminPlatformBannerSerializer(banner, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        banner = self._get_object(pk)
        if not banner:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        banner.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
