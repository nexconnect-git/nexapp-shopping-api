from datetime import time
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Address, User
from orders.actions import RefreshCustomerRecommendationsAction
from orders.models import Cart, CartItem, Coupon, CustomerRecommendationSnapshot, Order, PlatformSetting
from products.models import CatalogProduct, Category, Product
from vendors.models import Vendor


class CustomerFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="customer",
            password="pass12345",
            role="customer",
            phone="9876543210",
        )
        self.vendor_user = User.objects.create_user(
            username="vendor",
            password="pass12345",
            role="vendor",
            phone="9876543211",
        )
        self.category = Category.objects.create(
            name="Grocery",
            slug="grocery",
            show_in_customer_ui=True,
        )
        self.catalog_product = CatalogProduct.objects.create(
            category=self.category,
            name="Test Milk",
            slug="test-milk",
            brand="Nextou",
            unit="500 ml",
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            store_name="FreshLane",
            phone="9876543211",
            email="vendor@example.com",
            address="Indiranagar",
            city="Bengaluru",
            state="Karnataka",
            postal_code="560038",
            latitude=Decimal("12.97160000"),
            longitude=Decimal("77.59460000"),
            status="approved",
            is_open=True,
            opening_time=time(0, 0),
            closing_time=time(23, 59),
            is_accepting_orders=True,
            instant_delivery_radius_km=Decimal("2.50"),
            max_delivery_radius_km=Decimal("20.00"),
        )
        self.product = Product.objects.create(
            vendor=self.vendor,
            catalog_product=self.catalog_product,
            category=self.category,
            name="Test Milk",
            slug="test-milk",
            description="Fresh milk",
            price=Decimal("50.00"),
            compare_price=Decimal("60.00"),
            stock=10,
            unit="500 ml",
            status="active",
            is_available=True,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
        )
        self.address = Address.objects.create(
            user=self.customer,
            label="home",
            full_name="Nikhil",
            phone="9876543210",
            address_line1="MG Road",
            city="Bengaluru",
            state="Karnataka",
            postal_code="560001",
            latitude=Decimal("12.97160000"),
            longitude=Decimal("77.59460000"),
            is_default=True,
        )
        self.platform = PlatformSetting.get_setting()
        self.platform.delivery_base_fee = Decimal("20.00")
        self.platform.delivery_per_km_fee = Decimal("0.00")
        self.platform.free_delivery_above = Decimal("0.00")
        self.platform.platform_fee = Decimal("0.00")
        self.platform.packaging_fee = Decimal("0.00")
        self.platform.small_cart_threshold = Decimal("0.00")
        self.platform.tax_percentage = Decimal("0.00")
        self.platform.surge_fee = Decimal("0.00")
        self.platform.enabled_payment_methods = ["cod"]
        self.platform.save()
        self.client.force_authenticate(self.customer)

    def add_cart_item(self, quantity=2):
        cart, _created = Cart.objects.get_or_create(user=self.customer)
        return CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=quantity,
            price_at_add=self.product.price,
        )

    def test_checkout_preview_returns_price_breakup_and_delivery_quote(self):
        self.add_cart_item()

        response = self.client.post(
            "/api/orders/checkout-preview/",
            {
                "delivery_address_id": str(self.address.id),
                "payment_method": "cod",
                "cod_upi_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["price_breakup"]["item_subtotal"], "100.00")
        self.assertEqual(response.data["price_breakup"]["delivery_fee"], "20.00")
        self.assertFalse(response.data["requires_far_delivery_confirmation"])

    def test_checkout_preview_applies_coupon_discount(self):
        self.add_cart_item()
        Coupon.objects.create(
            code="SAVE10",
            title="Save 10",
            discount_type="fixed",
            discount_value=Decimal("10.00"),
            min_order_amount=Decimal("50.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
            created_by=self.customer,
        )

        response = self.client.post(
            "/api/orders/checkout-preview/",
            {
                "delivery_address_id": str(self.address.id),
                "payment_method": "cod",
                "coupon_code": "SAVE10",
                "cod_upi_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["price_breakup"]["coupon_discount"], "10.00")
        self.assertEqual(response.data["price_breakup"]["final_payable"], "110.00")

    def test_checkout_preview_requires_far_delivery_confirmation(self):
        self.add_cart_item()
        self.vendor.instant_delivery_radius_km = Decimal("0.10")
        self.vendor.save(update_fields=["instant_delivery_radius_km"])
        self.address.latitude = Decimal("12.99160000")
        self.address.save(update_fields=["latitude"])

        response = self.client.post(
            "/api/orders/checkout-preview/",
            {
                "delivery_address_id": str(self.address.id),
                "payment_method": "cod",
                "cod_upi_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.data)
        self.assertEqual(response.data["code"], "far_delivery_confirmation_required")

    def test_checkout_preview_rejects_unserviceable_address(self):
        self.add_cart_item()
        self.address.state = "Kerala"
        self.address.save(update_fields=["state"])

        response = self.client.post(
            "/api/orders/checkout-preview/",
            {
                "delivery_address_id": str(self.address.id),
                "payment_method": "cod",
                "cod_upi_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["code"], "delivery_not_serviceable")

    def test_order_placement_creates_order_and_clears_cart(self):
        self.add_cart_item(quantity=1)

        response = self.client.post(
            "/api/orders/create/",
            {
                "delivery_address_id": str(self.address.id),
                "payment_method": "cod",
                "cod_upi_confirmed": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 1)
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer).exists())

    def test_home_uses_precomputed_recommendation_snapshot(self):
        CustomerRecommendationSnapshot.objects.create(
            user=self.customer,
            recommended_product_ids=[str(self.product.id)],
            flash_deal_product_ids=[str(self.product.id)],
            recommended_store_ids=[str(self.vendor.id)],
            metadata={"source": "test"},
        )

        response = self.client.get(
            "/api/customer/home/",
            {
                "lat": str(self.address.latitude),
                "lng": str(self.address.longitude),
                "city": self.address.city,
                "state": self.address.state,
                "postal_code": self.address.postal_code,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["recommended_products"][0]["id"], str(self.product.id))
        self.assertEqual(response.data["flash_deals"][0]["id"], str(self.product.id))
        self.assertEqual(response.data["nearby_stores"][0]["id"], str(self.vendor.id))
        self.assertIsNotNone(response.data["recommendations_generated_at"])

    def test_refresh_customer_recommendations_creates_snapshot_without_ui_request(self):
        result = RefreshCustomerRecommendationsAction().execute(user_id=str(self.customer.id), limit=8)

        self.assertEqual(result["refreshed"], 1)
        snapshot = CustomerRecommendationSnapshot.objects.get(user=self.customer)
        self.assertIn(str(self.product.id), snapshot.recommended_product_ids)
        self.assertIn(str(self.product.id), snapshot.flash_deal_product_ids)
        self.assertIn(str(self.vendor.id), snapshot.recommended_store_ids)
        self.assertIn(str(self.vendor.id), snapshot.metadata["store_product_ids"])

    def test_store_recommendations_use_customer_taste_snapshot(self):
        second_catalog_product = CatalogProduct.objects.create(
            category=self.category,
            name="Taste Match Apples",
            slug="taste-match-apples",
            brand="Nextou",
            unit="1 kg",
        )
        second_product = Product.objects.create(
            vendor=self.vendor,
            catalog_product=second_catalog_product,
            category=self.category,
            name="Taste Match Apples",
            slug="taste-match-apples",
            description="Fresh apples",
            price=Decimal("120.00"),
            compare_price=Decimal("140.00"),
            stock=10,
            unit="1 kg",
            status="active",
            is_available=True,
            approval_status=Product.APPROVAL_STATUS_APPROVED,
        )
        CustomerRecommendationSnapshot.objects.create(
            user=self.customer,
            recommended_product_ids=[str(self.product.id)],
            flash_deal_product_ids=[str(second_product.id)],
            recommended_store_ids=[str(self.vendor.id)],
            metadata={
                "source": "test",
                "store_product_ids": {
                    str(self.vendor.id): [str(second_product.id), str(self.product.id)],
                },
            },
        )

        response = self.client.get(f"/api/vendors/{self.vendor.id}/recommendations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["results"][0]["product"]["id"], str(second_product.id))
        self.assertEqual(response.data["results"][0]["reason"], "picked_for_you")
        self.assertIsNotNone(response.data["recommendations_generated_at"])
