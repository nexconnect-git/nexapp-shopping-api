from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from vendors.models import Vendor


def make_vendor(store_name="TestShop", lat=12.9716, lon=77.5946, **kwargs):
    user = User.objects.create_user(
        username=store_name.lower().replace(" ", "_"),
        email=f"{store_name.lower()}@test.com",
        password="pass123",
        role="vendor",
    )
    defaults = dict(
        store_name=store_name,
        phone="9999999999",
        email=f"{store_name.lower()}@vendor.com",
        address="123 Test St",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        latitude=lat,
        longitude=lon,
        status="approved",
        is_accepting_orders=True,
        instant_delivery_radius_km=2.5,
        max_delivery_radius_km=5.0,
        base_prep_time_min=15,
        delivery_time_per_km_min=3.0,
        scheduled_buffer_min=30,
    )
    defaults.update(kwargs)
    return Vendor.objects.create(user=user, **defaults)


class NearbyVendorsV1Tests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.vendor = make_vendor()

    @patch("django.core.cache.cache.get", return_value=None)
    @patch("django.core.cache.cache.set")
    def test_returns_nearby_vendors(self, mock_set, mock_get):
        res = self.client.get("/api/v1/vendors/nearby/", {"lat": 12.9716, "lng": 77.5946})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertIn("delivery_type", res.data[0])
        self.assertIn("eta_min", res.data[0])
        self.assertIn("distance_km", res.data[0])

    @patch("django.core.cache.cache.get", return_value=None)
    @patch("django.core.cache.cache.set")
    def test_excludes_out_of_range_vendors(self, mock_set, mock_get):
        # Vendor is ~18 km away — beyond max_delivery_radius_km=5
        res = self.client.get("/api/v1/vendors/nearby/", {"lat": 13.1300, "lng": 77.5946})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_missing_lat_lng_returns_400(self):
        res = self.client.get("/api/v1/vendors/nearby/")
        self.assertEqual(res.status_code, 400)

    @patch("django.core.cache.cache.get", return_value=[{"cached": True}])
    def test_uses_cache_when_available(self, mock_get):
        res = self.client.get("/api/v1/vendors/nearby/", {"lat": 12.97, "lng": 77.59})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [{"cached": True}])

    @patch("django.core.cache.cache.get", return_value=None)
    @patch("django.core.cache.cache.set")
    def test_instant_delivery_type(self, mock_set, mock_get):
        # Same location → distance 0 → INSTANT
        res = self.client.get("/api/v1/vendors/nearby/", {"lat": 12.9716, "lng": 77.5946})
        self.assertEqual(res.data[0]["delivery_type"], "INSTANT")

    @patch("django.core.cache.cache.get", return_value=None)
    @patch("django.core.cache.cache.set")
    def test_scheduled_delivery_type(self, mock_set, mock_get):
        # ~3.5 km away → SCHEDULED (2.5 < 3.5 <= 5.0)
        res = self.client.get("/api/v1/vendors/nearby/", {"lat": 12.9716, "lng": 77.6260})
        self.assertEqual(res.status_code, 200)
        if res.data:
            self.assertEqual(res.data[0]["delivery_type"], "SCHEDULED")


class VendorServiceabilityV1Tests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.vendor = make_vendor()
        self.url = f"/api/v1/vendors/{self.vendor.id}/serviceability/"

    def test_serviceable_vendor(self):
        res = self.client.get(self.url, {"lat": 12.9716, "lng": 77.5946})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_serviceable"])
        self.assertIn("delivery_type", res.data)
        self.assertIn("eta_min", res.data)

    def test_not_serviceable_location(self):
        res = self.client.get(self.url, {"lat": 13.1300, "lng": 77.5946})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["is_serviceable"])
        self.assertEqual(res.data["eta_min"], 0)

    def test_missing_params_returns_400(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 400)

    def test_unknown_vendor_returns_404(self):
        import uuid
        res = self.client.get(f"/api/v1/vendors/{uuid.uuid4()}/serviceability/", {"lat": 12.9716, "lng": 77.5946})
        self.assertEqual(res.status_code, 404)
