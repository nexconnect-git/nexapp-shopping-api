"""Public banner endpoint for the customer app home carousel."""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from orders.models import PlatformBanner


class PlatformBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformBanner
        fields = ['id', 'title', 'subtitle', 'badge_text', 'cta_label', 'cta_url', 'image', 'bg_gradient']


class BannerListView(APIView):
    """GET /api/orders/banners/ — returns active banners ordered by display_order."""
    permission_classes = [AllowAny]

    def get(self, request):
        banners = PlatformBanner.objects.filter(is_active=True)
        return Response(PlatformBannerSerializer(banners, many=True, context={'request': request}).data)
