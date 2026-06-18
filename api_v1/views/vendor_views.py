from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api_v1.actions import NearbyVendorsV1Action, VendorServiceabilityV1Action
from api_v1.helpers import parse_lat_lng


class NearbyVendorsV1View(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lat, lng = parse_lat_lng(request.query_params)
        if lat is None or lng is None:
            return Response({'error': 'lat and lng are required.'}, status=400)

        results = NearbyVendorsV1Action().execute(
            lat=lat,
            lng=lng,
            category=request.query_params.get('category'),
        )
        return Response(results)


class VendorServiceabilityV1View(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        lat, lng = parse_lat_lng(request.query_params)
        if lat is None or lng is None:
            return Response({'error': 'lat and lng are required.'}, status=400)

        result, error, response_status = VendorServiceabilityV1Action().execute(pk, lat, lng)
        if error:
            return Response(error, status=response_status)
        return Response(result, status=response_status)
