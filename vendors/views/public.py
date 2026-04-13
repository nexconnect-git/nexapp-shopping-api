from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.serializers import UserProfileSerializer

from vendors.serializers.public import VendorRegistrationSerializer, VendorListSerializer, VendorSerializer
from vendors.data import VendorRepository
from backend.utils import haversine

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

class VendorRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        refresh = RefreshToken.for_user(vendor.user)
        return Response({
            "user": UserProfileSerializer(vendor.user).data,
            "vendor": VendorSerializer(vendor).data,
            "vendor_status": vendor.status,
            "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)}
        }, status=status.HTTP_201_CREATED)

class VendorListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorListSerializer

    def get_queryset(self):
        repo = VendorRepository()
        search = self.request.query_params.get("search")
        city = self.request.query_params.get("city")
        is_open = self.request.query_params.get("is_open")
        is_featured = self.request.query_params.get("is_featured")
        category = self.request.query_params.get("category")
        return repo.get_approved_vendors(search, city, is_open, is_featured, category)

class VendorDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get_queryset(self):
        return VendorRepository().filter(status="approved")

    def retrieve(self, request, *args, **kwargs):
        vendor = self.get_object()
        vendor_data = VendorSerializer(vendor).data
        from vendors.data import VendorProductRepository
        available_products = VendorProductRepository().filter(vendor=vendor, is_available=True)
        from products.serializers import ProductSerializer
        vendor_data["products"] = ProductSerializer(available_products, many=True).data
        return Response(vendor_data)

class NearbyVendorsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return Response({"error": "lat and lng reqd."}, status=400)
        
        radius_km = float(request.query_params.get("radius_km", 5))
        category = request.query_params.get("category")
        
        vendors = VendorRepository().get_approved_vendors(category=category)
        nearby = []
        for v in vendors:
            distance = haversine(lat, lng, float(v.latitude), float(v.longitude))
            if distance <= radius_km:
                data = VendorListSerializer(v).data
                data["distance_km"] = round(distance, 2)
                nearby.append(data)
        
        nearby.sort(key=lambda x: x["distance_km"])
        return Response(nearby)
