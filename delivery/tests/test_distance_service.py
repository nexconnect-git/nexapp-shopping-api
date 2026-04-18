from django.test import SimpleTestCase

from delivery.services.distance import (
    INSTANT, SCHEDULED, NOT_SERVICEABLE,
    compute_delivery_type, compute_distance_km, compute_eta,
)
from delivery.services.serviceability import ServiceabilityResult, check_serviceability


class ComputeDeliveryTypeTests(SimpleTestCase):

    def test_within_instant_radius(self):
        self.assertEqual(compute_delivery_type(1.0, 2.5, 5.0), INSTANT)

    def test_on_instant_radius_boundary(self):
        self.assertEqual(compute_delivery_type(2.5, 2.5, 5.0), INSTANT)

    def test_between_instant_and_max(self):
        self.assertEqual(compute_delivery_type(3.0, 2.5, 5.0), SCHEDULED)

    def test_on_max_radius_boundary(self):
        self.assertEqual(compute_delivery_type(5.0, 2.5, 5.0), SCHEDULED)

    def test_beyond_max_radius(self):
        self.assertEqual(compute_delivery_type(5.1, 2.5, 5.0), NOT_SERVICEABLE)

    def test_zero_distance(self):
        self.assertEqual(compute_delivery_type(0.0, 2.5, 5.0), INSTANT)


class ComputeEtaTests(SimpleTestCase):

    def test_instant_eta_no_buffer(self):
        eta = compute_eta(1.0, 15, 3.0, 30, INSTANT)
        self.assertEqual(eta, 18)  # 15 + 1.0*3 = 18

    def test_scheduled_eta_includes_buffer(self):
        eta = compute_eta(3.0, 15, 3.0, 30, SCHEDULED)
        self.assertEqual(eta, 54)  # 15 + 3*3 + 30 = 54

    def test_rounding(self):
        eta = compute_eta(1.0, 15, 3.3, 0, INSTANT)
        self.assertEqual(eta, 18)  # 15 + 3.3 = 18.3 → rounds to 18

    def test_zero_distance(self):
        eta = compute_eta(0.0, 15, 3.0, 30, INSTANT)
        self.assertEqual(eta, 15)


class ComputeDistanceKmTests(SimpleTestCase):

    def test_same_point(self):
        d = compute_distance_km(12.9716, 77.5946, 12.9716, 77.5946)
        self.assertAlmostEqual(d, 0.0, places=3)

    def test_known_distance(self):
        # Approx 1 degree lat ≈ 111 km — coarse sanity check
        d = compute_distance_km(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 111.19, delta=0.5)


class CheckServiceabilityTests(SimpleTestCase):

    VENDOR = dict(vendor_lat=12.9716, vendor_lon=77.5946)
    BASE = dict(
        instant_radius_km=2.5,
        max_radius_km=5.0,
        base_prep_time_min=15,
        delivery_time_per_km_min=3.0,
        scheduled_buffer_min=30,
    )

    def _call(self, cust_lat, cust_lon):
        return check_serviceability(
            **self.VENDOR,
            customer_lat=cust_lat,
            customer_lon=cust_lon,
            **self.BASE,
        )

    def test_instant_delivery(self):
        result = self._call(12.9800, 77.5946)
        self.assertEqual(result.delivery_type, INSTANT)
        self.assertTrue(result.is_serviceable)
        self.assertGreater(result.eta_min, 0)

    def test_scheduled_delivery(self):
        result = self._call(12.9950, 77.5946)
        self.assertEqual(result.delivery_type, SCHEDULED)
        self.assertTrue(result.is_serviceable)

    def test_not_serviceable(self):
        result = self._call(13.1000, 77.5946)
        self.assertEqual(result.delivery_type, NOT_SERVICEABLE)
        self.assertFalse(result.is_serviceable)
        self.assertEqual(result.eta_min, 0)

    def test_result_is_frozen_dataclass(self):
        result = self._call(12.9800, 77.5946)
        self.assertIsInstance(result, ServiceabilityResult)
        with self.assertRaises(Exception):
            result.delivery_type = "INSTANT"  # frozen

    def test_distance_km_rounded(self):
        result = self._call(12.9716, 77.5946)
        self.assertEqual(result.distance_km, 0.0)
