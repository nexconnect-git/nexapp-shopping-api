"""
Tests for vendor-initiated delivery search flow.

Covers:
  - StartDeliverySearchAction
  - CancelDeliverySearchAction
  - POST /vendors/orders/<pk>/start-delivery-search/
  - POST /vendors/orders/<pk>/cancel-delivery-search/
  - Signal no longer auto-triggers on order_placed
  - UpdateOrderStatusAction no longer triggers search on ready
"""

from datetime import time
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from vendors.models import Vendor
from orders.actions.ordering import CreateOrdersFromCartAction
from orders.models import Cart, CartItem, Order
from products.models import Product
from delivery.models import DeliveryAssignment
from notifications.models import Notification
from vendors.actions import StartDeliverySearchAction, CancelDeliverySearchAction, UpdateOrderStatusAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_vendor_user(username="vendor1"):
    user = User.objects.create_user(
        username=username, password="pass", role="vendor",
        email=f"{username}@test.com",
    )
    vendor = Vendor.objects.create(
        user=user, store_name="Test Store", phone="1234567890",
        email=f"{username}@test.com", address="123 St", city="City",
        state="ST", postal_code="560001", latitude="12.9716", longitude="77.5946", status="approved",
        opening_time=time(0, 0), closing_time=time(23, 59),
    )
    return user, vendor


def make_customer_user(username="customer1"):
    return User.objects.create_user(
        username=username, password="pass", role="customer",
        email=f"{username}@test.com",
    )


def make_order(vendor, customer, status="ready"):
    from accounts.models import Address
    addr = Address.objects.create(
        user=customer, full_name="Test", phone="9876543210",
        address_line1="1 Main St", city="City", state="ST",
        postal_code="560001", latitude="12.9716", longitude="77.5946",
    )
    return Order.objects.create(
        customer=customer,
        vendor=vendor,
        delivery_address=addr,
        status=status,
        order_number=f"ORD-{Order.objects.count() + 1:05d}",
        subtotal="10.00",
        delivery_fee="2.00",
        total="12.00",
    )


# ---------------------------------------------------------------------------
# StartDeliverySearchAction
# ---------------------------------------------------------------------------

class StartDeliverySearchActionTests(TestCase):

    def setUp(self):
        self.vendor_user, self.vendor = make_vendor_user()
        self.customer = make_customer_user()
        self.order = make_order(self.vendor, self.customer, status="ready")

    @patch("vendors.actions.orders.search_and_notify_partners")
    def test_creates_assignment_and_enqueues_search(self, mock_task):
        mock_task.delay = MagicMock()
        StartDeliverySearchAction().execute(self.order)

        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.status, "searching")
        self.assertEqual(assignment.current_radius_km, 2.0)
        mock_task.delay.assert_called_once_with(str(assignment.id))

    @patch("vendors.actions.orders.search_and_notify_partners")
    def test_resets_assignment_on_retry(self, mock_task):
        mock_task.delay = MagicMock()
        # Pre-existing timed_out assignment
        assignment = DeliveryAssignment.objects.create(
            order=self.order, status="timed_out", current_radius_km=10.0
        )

        StartDeliverySearchAction().execute(self.order)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "searching")
        self.assertEqual(assignment.current_radius_km, 2.0)

    def test_raises_if_search_already_in_progress(self):
        DeliveryAssignment.objects.create(order=self.order, status="searching")
        with self.assertRaises(ValueError) as ctx:
            StartDeliverySearchAction().execute(self.order)
        self.assertIn("already in progress", str(ctx.exception))

    def test_raises_if_notified_search_in_progress(self):
        DeliveryAssignment.objects.create(order=self.order, status="notified")
        with self.assertRaises(ValueError) as ctx:
            StartDeliverySearchAction().execute(self.order)
        self.assertIn("already in progress", str(ctx.exception))

    def test_raises_if_partner_already_assigned(self):
        partner_user = User.objects.create_user(username="dp1", password="pass", role="delivery")
        self.order.delivery_partner = partner_user
        self.order.save()
        with self.assertRaises(ValueError) as ctx:
            StartDeliverySearchAction().execute(self.order)
        self.assertIn("already assigned", str(ctx.exception))

    @patch("vendors.actions.orders.search_and_notify_partners")
    def test_works_after_cancelled_assignment(self, mock_task):
        mock_task.delay = MagicMock()
        DeliveryAssignment.objects.create(order=self.order, status="cancelled")
        StartDeliverySearchAction().execute(self.order)
        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.status, "searching")


# ---------------------------------------------------------------------------
# CancelDeliverySearchAction
# ---------------------------------------------------------------------------

class CancelDeliverySearchActionTests(TestCase):

    def setUp(self):
        self.vendor_user, self.vendor = make_vendor_user("vendor2")
        self.customer = make_customer_user("customer2")
        self.order = make_order(self.vendor, self.customer, status="ready")

    def test_cancels_searching_assignment(self):
        assignment = DeliveryAssignment.objects.create(order=self.order, status="searching")
        CancelDeliverySearchAction().execute(self.order)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "cancelled")

    def test_cancels_notified_assignment_and_deletes_notifications(self):
        assignment = DeliveryAssignment.objects.create(order=self.order, status="notified")
        partner_user = User.objects.create_user(username="dp2", password="pass", role="delivery")
        # Simulate a pending partner notification
        Notification.objects.create(
            user=partner_user,
            title="New Delivery Request",
            message="test",
            notification_type="delivery",
            data={"assignment_id": str(assignment.id), "type": "assignment_request"},
        )

        CancelDeliverySearchAction().execute(self.order)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "cancelled")
        self.assertEqual(
            Notification.objects.filter(
                data__assignment_id=str(assignment.id),
                data__type="assignment_request",
            ).count(),
            0,
        )

    def test_raises_if_no_assignment_exists(self):
        with self.assertRaises(ValueError) as ctx:
            CancelDeliverySearchAction().execute(self.order)
        self.assertIn("No active search", str(ctx.exception))

    def test_raises_if_assignment_already_accepted(self):
        DeliveryAssignment.objects.create(order=self.order, status="accepted")
        with self.assertRaises(ValueError) as ctx:
            CancelDeliverySearchAction().execute(self.order)
        self.assertIn("No active search to cancel", str(ctx.exception))

    def test_raises_if_assignment_timed_out(self):
        DeliveryAssignment.objects.create(order=self.order, status="timed_out")
        with self.assertRaises(ValueError) as ctx:
            CancelDeliverySearchAction().execute(self.order)
        self.assertIn("No active search to cancel", str(ctx.exception))

    def test_raises_if_partner_already_assigned(self):
        partner_user = User.objects.create_user(username="dp3", password="pass", role="delivery")
        self.order.delivery_partner = partner_user
        self.order.save()
        DeliveryAssignment.objects.create(order=self.order, status="accepted")
        with self.assertRaises(ValueError) as ctx:
            CancelDeliverySearchAction().execute(self.order)
        self.assertIn("already assigned", str(ctx.exception))


# ---------------------------------------------------------------------------
# UpdateOrderStatusAction — no auto-trigger on ready
# ---------------------------------------------------------------------------

class UpdateOrderStatusNoAutoTriggerTests(TestCase):

    def test_marking_ready_does_not_create_assignment(self):
        vendor_user, vendor = make_vendor_user("vendor3")
        customer = make_customer_user("customer3")
        order = make_order(vendor, customer, status="preparing")

        UpdateOrderStatusAction().execute(order, "ready")

        self.assertFalse(DeliveryAssignment.objects.filter(order=order).exists())

    def test_signal_does_not_auto_create_assignment_on_order_placed(self):
        """The order_placed signal must NOT create a DeliveryAssignment."""
        from backend.events import order_placed
        vendor_user, vendor = make_vendor_user("vendor4")
        customer = make_customer_user("customer4")
        order = make_order(vendor, customer, status="placed")

        order_placed.send(sender=Order, order=order)

        self.assertFalse(DeliveryAssignment.objects.filter(order=order).exists())


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class DeliverySearchEndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.vendor_user, self.vendor = make_vendor_user("vendor5")
        self.customer = make_customer_user("customer5")
        self.order = make_order(self.vendor, self.customer, status="ready")
        self.client.force_authenticate(user=self.vendor_user)

    @patch("vendors.actions.orders.search_and_notify_partners")
    def test_start_delivery_search_returns_200(self, mock_task):
        mock_task.delay = MagicMock()
        url = f"/api/vendors/orders/{self.order.id}/start-delivery-search/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeliveryAssignment.objects.get(order=self.order).status, "searching")

    @patch("vendors.actions.orders.search_and_notify_partners")
    def test_start_delivery_search_idempotency_error_when_already_searching(self, mock_task):
        mock_task.delay = MagicMock()
        DeliveryAssignment.objects.create(order=self.order, status="searching")
        url = f"/api/vendors/orders/{self.order.id}/start-delivery-search/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn("already in progress", response.data["error"])

    def test_cancel_delivery_search_returns_200(self):
        DeliveryAssignment.objects.create(order=self.order, status="searching")
        url = f"/api/vendors/orders/{self.order.id}/cancel-delivery-search/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeliveryAssignment.objects.get(order=self.order).status, "cancelled")

    def test_cancel_delivery_search_no_active_search_returns_400(self):
        url = f"/api/vendors/orders/{self.order.id}/cancel-delivery-search/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn("No active search", response.data["error"])

    def test_start_delivery_search_requires_auth(self):
        self.client.logout()
        url = f"/api/vendors/orders/{self.order.id}/start-delivery-search/"
        response = self.client.post(url)
        self.assertIn(response.status_code, [401, 403])

    def test_start_delivery_search_rejects_non_vendor(self):
        self.client.force_authenticate(user=self.customer)
        url = f"/api/vendors/orders/{self.order.id}/start-delivery-search/"
        response = self.client.post(url)
        self.assertIn(response.status_code, [403, 404])


class VendorOperationsEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vendor_user, self.vendor = make_vendor_user("vendor_ops")
        self.customer = make_customer_user("customer_ops")
        self.client.force_authenticate(user=self.vendor_user)
        self.order = make_order(self.vendor, self.customer, status="placed")

    def test_operations_summary_returns_live_metrics(self):
        Product.objects.create(
            vendor=self.vendor,
            name="Low Stock Item",
            slug="low-stock-item",
            price="25.00",
            stock=1,
            low_stock_threshold=3,
        )
        response = self.client.get("/api/vendors/operations/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["orders"]["new"], 1)
        self.assertEqual(response.data["alerts"]["low_stock"], 1)
        self.assertIn("auto_order_acceptance", response.data["store"])

    def test_live_orders_returns_vendor_orders(self):
        other_user, other_vendor = make_vendor_user("other_vendor")
        other_customer = make_customer_user("other_customer")
        make_order(other_vendor, other_customer, status="placed")

        response = self.client.get("/api/vendors/live-orders/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.order.id))

    def test_store_settings_patch_updates_vendor_controls(self):
        response = self.client.patch(
            "/api/vendors/store-settings/",
            {
                "is_accepting_orders": False,
                "auto_order_acceptance": True,
                "base_prep_time_min": 12,
                "min_order_amount": "99.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.vendor.refresh_from_db()
        self.assertFalse(self.vendor.is_accepting_orders)
        self.assertTrue(self.vendor.auto_order_acceptance)
        self.assertEqual(self.vendor.base_prep_time_min, 12)
        self.assertEqual(str(self.vendor.min_order_amount), "99.00")

    def test_order_action_endpoints_move_order_through_prep_flow(self):
        accept_url = f"/api/vendors/orders/{self.order.id}/accept/"
        preparing_url = f"/api/vendors/orders/{self.order.id}/start-preparing/"
        ready_url = f"/api/vendors/orders/{self.order.id}/mark-ready/"

        response = self.client.post(accept_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")

        response = self.client.post(preparing_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "preparing")

        response = self.client.post(ready_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ready")

    def test_reject_order_endpoint_requires_vendor_ownership(self):
        other_user, other_vendor = make_vendor_user("reject_other")
        other_order = make_order(other_vendor, self.customer, status="placed")
        response = self.client.post(
            f"/api/vendors/orders/{other_order.id}/reject/",
            {"reason": "Cannot fulfill"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class VendorAutoAcceptTests(TestCase):
    def test_create_order_auto_confirms_when_vendor_auto_accept_enabled(self):
        vendor_user, vendor = make_vendor_user("auto_vendor")
        vendor.auto_order_acceptance = True
        vendor.save(update_fields=["auto_order_acceptance"])
        customer = make_customer_user("auto_customer")
        address = customer.addresses.create(
            full_name="Auto Customer",
            phone="9876543210",
            address_line1="1 Main St",
            city="City",
            state="ST",
            postal_code="560001",
            latitude="12.9716",
            longitude="77.5946",
        )
        product = Product.objects.create(
            vendor=vendor,
            name="Auto Product",
            slug="auto-product",
            price="50.00",
            stock=5,
        )
        cart = Cart.objects.create(user=customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)

        orders = CreateOrdersFromCartAction().execute(customer, str(address.id), cod_upi_confirmed=True)

        self.assertEqual(len(orders), 1)
        orders[0].refresh_from_db()
        self.assertEqual(orders[0].status, "confirmed")
        self.assertTrue(orders[0].tracking.filter(status="confirmed").exists())
