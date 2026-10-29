"""Regression coverage for the simplified marketplace's retained contracts."""

from datetime import time, timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Address, AdminPermissionGrant, User
from accounts.models.wallet import Wallet, WalletTransaction
from backend.data.admin_console_repository import AdminConsoleRepository
from delivery.models import DeliveryAssignment, DeliveryPartner
from orders.models import Order, PlatformSetting
from orders.models.operations import RefundLedger
from products.models import CatalogProduct, CatalogProductImage, Category, Product
from support.models import SupportTicket
from vendors.data.order_repo import VendorOrderRepository
from vendors.models import DeliveryPartnerPayout, Vendor, VendorPayout


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class SimplifiedMarketplaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user("simple-customer", role="customer", email="simple-customer@example.test")
        cls.vendor_user = User.objects.create_user("simple-vendor", role="vendor", email="simple-vendor@example.test")
        cls.driver_user = User.objects.create_user("simple-driver", role="delivery", email="simple-driver@example.test")
        cls.admin = User.objects.create_superuser("simple-admin", "simple-admin@example.test", "test-password", role="admin")
        cls.vendor = Vendor.objects.create(
            user=cls.vendor_user, store_name="Local store", phone="9876543210",
            email="simple-vendor@example.test", address="Market road", city="Mumbai",
            state="Maharashtra", postal_code="400001", latitude="19.0760", longitude="72.8777",
            status="approved", is_open=True, is_accepting_orders=True,
            opening_time=time(0, 0), closing_time=time(23, 59), min_order_amount=0,
        )
        cls.address = Address.objects.create(
            user=cls.customer, full_name="Customer", phone="9876543210",
            address_line1="10 Market road", city="Mumbai", state="Maharashtra",
            postal_code="400001", latitude="19.0761", longitude="72.8778",
        )
        cls.category = Category.objects.create(name="Essentials", slug="simple-essentials")
        cls.catalog = CatalogProduct.objects.create(name="Rice", slug="simple-rice", category=cls.category)
        CatalogProductImage.objects.create(catalog_product=cls.catalog, image="catalog/rice.png", is_primary=True)
        cls.product = Product.objects.create(
            vendor=cls.vendor, catalog_product=cls.catalog, category=cls.category,
            name="Rice", slug="simple-rice", price="100.00", stock=20,
            approval_status="approved", status="active",
        )
        cls.driver = DeliveryPartner.objects.create(
            user=cls.driver_user, vehicle_type="bicycle", license_number="TEST",
            is_approved=True, is_available=True, status="available",
            current_latitude="19.0760", current_longitude="72.8777",
        )
        PlatformSetting.get_setting()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.customer)

    def post(self, url, body=None, user=None, expected=200, format="json"):
        self.client.force_authenticate(user or self.customer)
        response = self.client.post(url, body or {}, format=format)
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def add_and_place_order(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        payload = {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True}
        preview = self.post("/api/orders/checkout-preview/", payload)
        self.assertIn("price_breakup", preview)
        payload["client_price_breakup"] = preview["price_breakup"]
        result = self.post("/api/orders/create/", payload, expected=201)
        self.assertEqual(len(result), 1)
        return Order.objects.get(pk=result[0]["id"])

    def test_complete_customer_vendor_driver_handoff(self):
        order = self.add_and_place_order()
        for command, status in [("accept", "confirmed"), ("start-preparing", "preparing"), ("mark-ready", "ready")]:
            result = self.post(f"/api/vendors/orders/{order.pk}/{command}/", user=self.vendor_user)
            self.assertEqual(result["status"], status)
        self.assertFalse(DeliveryAssignment.objects.filter(order=order).exists(), "Ready must not automatically start search")
        self.post(f"/api/vendors/orders/{order.pk}/start-delivery-search/", user=self.vendor_user)
        assignment = DeliveryAssignment.objects.get(order=order)
        # Simulate only the external RQ worker's notification step.
        assignment.status = "notified"
        assignment.last_search_at = timezone.now()
        assignment.save()
        assignment.notified_partners.add(self.driver)
        self.post(f"/api/delivery/requests/{assignment.pk}/accept/", user=self.driver_user)
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")
        invalid_pickup = "000000" if order.pickup_otp != "000000" else "111111"
        self.post(f"/api/vendors/orders/{order.pk}/verify-pickup-otp/", {"otp": invalid_pickup}, user=self.vendor_user, expected=400)
        self.post(f"/api/vendors/orders/{order.pk}/verify-pickup-otp/", {"otp": order.pickup_otp}, user=self.vendor_user)
        self.client.force_authenticate(self.driver_user)
        response = self.client.patch(f"/api/delivery/update-status/{order.pk}/", {"status": "on_the_way"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.post(f"/api/delivery/confirm/{order.pk}/", {"otp": order.delivery_otp}, user=self.driver_user, expected=400)
        image = BytesIO()
        Image.new("RGB", (4, 4), "white").save(image, format="PNG")
        proof = SimpleUploadedFile("proof.png", image.getvalue(), content_type="image/png")
        self.post(f"/api/delivery/confirm/{order.pk}/", {"otp": order.delivery_otp, "photo": proof}, user=self.driver_user, format="multipart")
        order.refresh_from_db()
        self.assertEqual(order.status, "delivered")
        self.assertTrue(order.delivery_photo)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.total_deliveries, 1)

    def test_cancelled_search_cannot_be_accepted(self):
        order = Order.objects.create(customer=self.customer, vendor=self.vendor, delivery_address=self.address, status="ready", subtotal=100, total=100)
        self.post(f"/api/vendors/orders/{order.pk}/start-delivery-search/", user=self.vendor_user)
        assignment = DeliveryAssignment.objects.get(order=order)
        assignment.notified_partners.add(self.driver)
        self.post(f"/api/vendors/orders/{order.pk}/cancel-delivery-search/", user=self.vendor_user)
        self.post(f"/api/delivery/requests/{assignment.pk}/accept/", user=self.driver_user, expected=404)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "cancelled")

    def test_history_and_attention_filters_do_not_drop_records(self):
        for status in ["placed", "ready", "delivered", "cancelled"]:
            Order.objects.create(customer=self.customer, vendor=self.vendor, delivery_address=self.address, status=status, subtotal=100, total=100)
        history = VendorOrderRepository().get_vendor_orders(self.vendor, params={"view": "history"})
        self.assertEqual(set(history.values_list("status", flat=True)), {"delivered", "cancelled"})
        attention = AdminConsoleRepository.filtered_orders({"needs_attention": True})
        self.assertEqual(set(attention.values_list("status", flat=True)), {"placed", "ready"})
        counts = AdminConsoleRepository.order_summary(AdminConsoleRepository.orders())
        self.assertEqual(counts, {"total": 4, "new": 1, "active": 2, "needs_attention": 2})

    def test_admin_orders_summary_and_permission_boundary(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/admin/orders/?needs_attention=true")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("summary", response.data)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/admin/orders/").status_code, 403)
        self.post("/api/delivery/set-availability/", {"is_available": True}, user=self.customer, expected=403)

    def test_simple_home_skips_growth_and_recommendation_work(self):
        with patch("backend.actions.customer_flow.home.CustomerFlowRepository.recommendation_snapshot") as recommendations, patch("backend.actions.customer_flow.home.GetCustomerBuyAgainAction.execute") as buy_again:
            response = self.client.get("/api/customer/home/?layout=simple&lat=19.076&lng=72.8777&state=Maharashtra&city=Mumbai&postal_code=400001")
        self.assertEqual(response.status_code, 200, response.data)
        recommendations.assert_not_called()
        buy_again.assert_not_called()
        self.assertEqual(response.data["coupons"], [])
        self.assertEqual(response.data["recommended_products"], [])
        self.assertEqual([section["key"] for section in response.data["sections"]], ["categories", "nearby_stores"])

    def test_failed_checkout_keeps_cart_and_does_not_create_order(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        self.vendor.is_open = False
        self.vendor.save(update_fields=["is_open"])
        self.post("/api/orders/create/", {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True}, expected=400)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.get("/api/orders/cart/").data["total_items"], 1)

    def test_legacy_scheduled_order_remains_readable(self):
        scheduled = timezone.now() + timedelta(days=1)
        order = Order.objects.create(customer=self.customer, vendor=self.vendor, delivery_address=self.address, subtotal=100, total=95, discount=5, coupon_discount=5, scheduled_for=scheduled)
        response = self.client.get(f"/api/orders/{order.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["scheduled_for"])
        self.assertEqual(float(response.data["discount"]), 5)

    def test_expired_assignment_cannot_be_accepted_and_can_be_retried(self):
        order = Order.objects.create(customer=self.customer, vendor=self.vendor, delivery_address=self.address, status="ready", subtotal=100, total=100)
        assignment = DeliveryAssignment.objects.create(order=order, status="notified", last_search_at=timezone.now() - timedelta(minutes=2))
        assignment.notified_partners.add(self.driver)
        self.post(f"/api/delivery/requests/{assignment.pk}/accept/", user=self.driver_user, expected=404)
        assignment.status = "timed_out"
        assignment.save(update_fields=["status"])
        self.post(f"/api/vendors/orders/{order.pk}/start-delivery-search/", user=self.vendor_user)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "searching")
        self.assertEqual(DeliveryAssignment.objects.filter(order=order).count(), 1)

    def test_changed_quote_and_duplicate_submission_are_safe(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        payload = {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True, "client_idempotency_key": "simple-retry"}
        preview = self.post("/api/orders/checkout-preview/", payload)
        payload["client_price_breakup"] = {**preview["price_breakup"], "final_payable": "999999.00"}
        rejected = self.post("/api/orders/create/", payload, expected=400)
        self.assertEqual(rejected["code"], "quote_changed")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.get("/api/orders/cart/").data["total_items"], 1)
        payload["client_price_breakup"] = preview["price_breakup"]
        first = self.post("/api/orders/create/", payload, expected=201)
        repeated = self.post("/api/orders/create/", payload, expected=201)
        self.assertEqual(first[0]["id"], repeated[0]["id"])
        self.assertEqual(Order.objects.count(), 1)

    def test_out_of_stock_checkout_keeps_cart(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        self.product.stock = 0
        self.product.save(update_fields=["stock"])
        self.post("/api/orders/create/", {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True}, expected=400)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.get("/api/orders/cart/").data["total_items"], 1)

    def test_scheduled_only_product_is_rejected_for_asap_checkout(self):
        self.product.is_instant_delivery = False
        self.product.save(update_fields=["is_instant_delivery"])
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        self.post("/api/orders/create/", {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True, "scheduled_for": None}, expected=400)
        self.assertFalse(Order.objects.exists())

    def test_stock_controls_preserve_concurrent_update_protection(self):
        result = self.post("/api/vendors/bulk-update-stock/", {"updates": [{"id": str(self.product.pk), "stock": 5, "expected_stock": 19}]}, user=self.vendor_user)
        self.assertEqual(result["updated"], [])
        self.assertTrue(result["errors"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)
        result = self.post("/api/vendors/bulk-update-stock/", {"updates": [{"id": str(self.product.pk), "stock": 5, "expected_stock": 20}]}, user=self.vendor_user)
        self.assertIn(str(self.product.pk), result["updated"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_owned_orders_and_approved_vendor_access_are_enforced(self):
        other = User.objects.create_user("other-customer", role="customer")
        order = Order.objects.create(customer=other, vendor=self.vendor, delivery_address=self.address, subtotal=100, total=100)
        self.assertEqual(self.client.get(f"/api/orders/{order.pk}/").status_code, 404)
        self.vendor.status = "pending"
        self.vendor.save(update_fields=["status"])
        self.client.force_authenticate(self.vendor_user)
        self.assertEqual(self.client.get("/api/vendors/products/").status_code, 403)

    def test_unserviceable_or_foreign_addresses_cannot_place_an_order(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        self.address.state = "Karnataka"
        self.address.latitude = "12.9716"
        self.address.longitude = "77.5946"
        self.address.save(update_fields=["state", "latitude", "longitude"])
        self.post("/api/orders/create/", {"delivery_address_id": str(self.address.pk), "payment_method": "cod", "cod_upi_confirmed": True}, expected=400)
        self.assertFalse(Order.objects.exists())


    def test_mixed_store_cart_requires_explicit_replacement(self):
        self.post("/api/orders/cart/add/", {"product_id": str(self.product.pk), "quantity": 1}, expected=201)
        other_user = User.objects.create_user("second-vendor", role="vendor")
        other_vendor = Vendor.objects.create(user=other_user, store_name="Second store", status="approved", is_open=True, is_accepting_orders=True)
        other_product = Product.objects.create(vendor=other_vendor, catalog_product=self.catalog, category=self.category, name="Other rice", slug="other-rice", price=100, stock=10, approval_status="approved", status="active")
        result = self.post("/api/orders/cart/add/", {"product_id": str(other_product.pk), "quantity": 1}, expected=409)
        self.assertEqual(result["code"], "cart_store_conflict")
        cart = self.client.get("/api/orders/cart/").data
        self.assertEqual(cart["total_items"], 1)
        self.assertEqual(str(cart["items"][0]["product"]["id"]), str(self.product.pk))

    def test_existing_credits_refunds_and_payouts_remain_accessible(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.customer)
        wallet.balance = 75
        wallet.save(update_fields=["balance"])
        transaction = WalletTransaction.objects.create(wallet=wallet, amount=75, transaction_type="credit", source="refund", description="Existing order refund")
        response = self.client.get("/api/auth/wallet/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(float(response.data["balance"]), 75)
        self.assertIn(str(transaction.pk), [row["id"] for row in response.data["transactions"]])
        now = timezone.now()
        vendor_payout = VendorPayout.objects.create(vendor=self.vendor, period_start=now-timedelta(days=7), period_end=now, net_payout=90)
        driver_payout = DeliveryPartnerPayout.objects.create(delivery_partner=self.driver_user, period_start=now-timedelta(days=7), period_end=now, total_earnings=30)
        for user, endpoint, payout in [(self.vendor_user, "/api/vendors/payouts/", vendor_payout), (self.driver_user, "/api/delivery/payouts/", driver_payout)]:
            self.client.force_authenticate(user)
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIn(str(payout.pk), [row["id"] for row in response.data["results"]])
            self.post(f"{endpoint}{payout.pk}/approve/", user=user)
            payout.refresh_from_db()
            self.assertEqual(payout.status, "approved")
        order = Order.objects.create(customer=self.customer, vendor=self.vendor, delivery_address=self.address, status="cancelled", subtotal=100, total=100)
        refund = RefundLedger.objects.create(order=order, customer=self.customer, amount=75, status="requested")
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/admin/refund-ledger/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(str(refund.pk), [row["id"] for row in response.data["results"]])


    def test_support_workspace_uses_existing_ticket_actions_with_granular_permissions(self):
        ticket = SupportTicket.objects.create(vendor=self.vendor, subject="Existing billing question", message="Please review this payout.")
        reader = User.objects.create_user("support-reader", role="admin")
        AdminPermissionGrant.objects.create(user=reader, permission="support.view")
        self.client.force_authenticate(reader)
        response = self.client.get("/api/admin/support/tickets/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(str(ticket.pk), [row["id"] for row in response.data["results"]])
        endpoint = f"/api/admin/support/tickets/{ticket.pk}/respond/"
        body = {"admin_response": "Reviewed your existing record.", "status": "in_progress"}
        self.assertEqual(self.client.patch(endpoint, body, format="json").status_code, 403)
        AdminPermissionGrant.objects.create(user=reader, permission="support.manage")
        self.assertEqual(self.client.patch(endpoint, body, format="json").status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "in_progress")
        self.assertEqual(ticket.admin_response, body["admin_response"])
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/admin/support/tickets/").status_code, 403)
