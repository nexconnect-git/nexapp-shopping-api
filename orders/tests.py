from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from helpers.status_helpers import (
    normalize_assignment_status,
    normalize_order_delivery_status,
    normalize_order_status,
    normalize_payment_status,
)
from orders.models import Cart, CartItem, InventoryReservation
from products.models import CatalogProduct, Category, Product
from vendors.models import Vendor


class DirectStoreContractSmokeTests(SimpleTestCase):
    def test_order_statuses_are_normalized_for_frontend_contract(self):
        self.assertEqual(normalize_order_status("placed"), "created")
        self.assertEqual(normalize_order_status("ready"), "ready_for_pickup")
        self.assertEqual(normalize_order_status("on_the_way"), "out_for_delivery")
        self.assertEqual(normalize_order_status("delivered"), "delivered")
        self.assertEqual(normalize_order_status("custom_hold"), "custom_hold")
        self.assertEqual(normalize_order_status(""), "created")

    def test_assignment_statuses_are_normalized_for_delivery_contract(self):
        self.assertEqual(normalize_assignment_status("searching"), "assigned")
        self.assertEqual(normalize_assignment_status("notified"), "assigned")
        self.assertEqual(normalize_assignment_status("accepted"), "accepted")
        self.assertEqual(normalize_assignment_status("timed_out"), "timed_out")
        self.assertEqual(normalize_assignment_status(""), "assigned")

    def test_payment_status_reflects_refund_and_verification_state(self):
        self.assertEqual(
            normalize_payment_status(
                SimpleNamespace(refund_status="processed", is_payment_verified=True, total=10, status="delivered")
            ),
            "refunded",
        )
        self.assertEqual(
            normalize_payment_status(
                SimpleNamespace(refund_status="initiated", is_payment_verified=True, total=10, status="cancelled")
            ),
            "refund_initiated",
        )
        self.assertEqual(
            normalize_payment_status(
                SimpleNamespace(refund_status="none", is_payment_verified=True, total=10, status="confirmed")
            ),
            "success",
        )
        self.assertEqual(
            normalize_payment_status(
                SimpleNamespace(refund_status="none", is_payment_verified=False, total=10, status="placed")
            ),
            "pending",
        )

    def test_delivery_status_uses_store_ready_and_assignment_context(self):
        self.assertEqual(
            normalize_order_delivery_status(SimpleNamespace(status="ready"), "accepted"),
            "accepted",
        )
        self.assertEqual(
            normalize_order_delivery_status(SimpleNamespace(status="ready"), "searching"),
            "available",
        )
        self.assertEqual(
            normalize_order_delivery_status(SimpleNamespace(status="picked_up")),
            "picked_up",
        )
        self.assertEqual(
            normalize_order_delivery_status(SimpleNamespace(status="confirmed"), "notified"),
            "assigned",
        )

    def test_inventory_reservation_default_expiry_is_future_hold_window(self):
        before = timezone.now()
        expiry = InventoryReservation.default_expiry()
        after = timezone.now()

        self.assertGreaterEqual(expiry, before + timedelta(minutes=14, seconds=59))
        self.assertLessEqual(expiry, after + timedelta(minutes=15, seconds=1))


class DirectStoreIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="pass12345",
            role="customer",
        )
        self.vendor_user = User.objects.create_user(
            username="vendor",
            email="vendor@example.com",
            password="pass12345",
            role="vendor",
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            store_name="Fresh Store",
            phone="9999999999",
            email="store@example.com",
            address="1 Market Street",
            city="Mumbai",
            state="MH",
            postal_code="400001",
            latitude=Decimal("19.07600000"),
            longitude=Decimal("72.87770000"),
            status="approved",
            is_open=True,
            is_accepting_orders=True,
        )
        self.category = Category.objects.create(
            name="Fruit",
            slug="fruit",
            is_active=True,
            show_in_customer_ui=True,
        )
        self.catalog_product = CatalogProduct.objects.create(
            category=self.category,
            name="Apple",
            slug="apple",
            unit="kg",
            is_active=True,
        )
        self.product = Product.objects.create(
            vendor=self.vendor,
            catalog_product=self.catalog_product,
            category=self.category,
            name="Apple",
            slug="apple-store",
            price=Decimal("120.00"),
            stock=25,
            status="active",
            is_available=True,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
        )
        self.second_catalog_product = CatalogProduct.objects.create(
            category=self.category,
            name="Banana",
            slug="banana",
            unit="dozen",
            is_active=True,
        )
        self.second_product = Product.objects.create(
            vendor=self.vendor,
            catalog_product=self.second_catalog_product,
            category=self.category,
            name="Banana",
            slug="banana-store",
            price=Decimal("60.00"),
            stock=30,
            status="active",
            is_available=True,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
        )

    def test_customer_category_alias_is_public_and_uses_canonical_view(self):
        response = self.client.get("/api/customer/categories/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        category_names = [item["name"] for item in payload.get("results", payload)]
        self.assertIn("Fruit", category_names)

    def test_replace_cart_alias_swaps_vendor_cart_atomically_with_price_snapshot(self):
        self.client.force_authenticate(user=self.customer)
        add_response = self.client.post(
            "/api/orders/cart/add/",
            {"product_id": str(self.product.id), "quantity": 1},
            format="json",
        )

        self.assertEqual(add_response.status_code, 201)

        replace_response = self.client.post(
            "/api/customer/cart/replace/",
            {"product_id": str(self.second_product.id), "quantity": 2},
            format="json",
        )

        self.assertEqual(replace_response.status_code, 200)
        cart = Cart.objects.get(user=self.customer)
        items = list(CartItem.objects.filter(cart=cart).select_related("product"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product, self.second_product)
        self.assertEqual(items[0].quantity, 2)
        self.assertEqual(items[0].price_at_add, self.second_product.price)

    def test_sellable_vendor_product_requires_catalog_parent(self):
        product = Product(
            vendor=self.vendor,
            category=self.category,
            name="Loose Item",
            slug="loose-item",
            price=Decimal("10.00"),
            stock=5,
            status="active",
            is_available=True,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
        )

        with self.assertRaises(ValidationError) as context:
            product.clean()

        self.assertIn("catalog_product", context.exception.message_dict)

    def test_inventory_reservation_commit_and_release_updates_ledger_status(self):
        cart = Cart.objects.create(user=self.customer)
        reservation = InventoryReservation.objects.create(
            cart=cart,
            product=self.product,
            vendor=self.vendor,
            quantity=2,
            price_at_reservation=self.product.price,
            reserved_until=InventoryReservation.default_expiry(),
        )

        reservation.commit()
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, InventoryReservation.STATUS_COMMITTED)
        self.assertIsNotNone(reservation.committed_at)

        reservation.release()
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, InventoryReservation.STATUS_RELEASED)
        self.assertIsNotNone(reservation.released_at)
