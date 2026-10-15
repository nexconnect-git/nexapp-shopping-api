from unittest.mock import patch
from django.utils import timezone
from accounts.models.mobile_otp import MobileOTP
from helpers.phone_helpers import normalize_phone
"""Run: manage.py test orders.redesign_regression_checks --settings=backend.config.local_sqlite"""
from datetime import time
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.request import Request

from backend.actions.customer_flow.explore import GetCustomerExploreAction
from products.data.product_repository import ProductRepository
from vendors.helpers.public_vendor_helpers import sort_vendor_cards
from vendors.data import VendorProductRepository
from invoices.data import InvoiceRepository
from invoices.models import Invoice

from accounts.models import Address, User
from orders.actions.checkout import calculate_checkout_preview, public_price_breakup
from orders.actions.ordering import CreateOrdersFromCartAction
from orders.actions.reorder import ReorderAction
from orders.models import Cart, CartItem, Order, OrderItem
from orders.models.setting import PlatformSetting
from products.models import CatalogProduct, Product, Category
from vendors.models import Vendor, FulfillmentNode, FulfillmentNodeInventory


class CustomerRedesignRegressionChecks(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='redesign-customer', phone='9000000081', email='customer@example.test', role='customer')
        self.other = User.objects.create_user(username='redesign-other', phone='9000000082', email='other@example.test', role='customer')
        owner = User.objects.create_user(username='redesign-store', phone='9000000083', email='store@example.test', role='vendor')
        self.vendor = Vendor.objects.create(user=owner, store_name='QA store', phone='9000000083', email='store@example.test', address='Test address', city='Bengaluru', state='Karnataka', postal_code='560001', latitude='12.9716', longitude='77.5946', status='approved', is_open=True, opening_time=time(0), closing_time=time(23,59))
        catalog=CatalogProduct.objects.create(name='QA apples',slug='qa-catalog-apples')
        self.product = Product.objects.create(catalog_product=catalog,vendor=self.vendor, name='QA apples', slug='qa-apples', price='120', stock=10, status='active', approval_status='approved')
        self.address = Address.objects.create(user=self.customer, full_name='QA customer', phone='9000000081', address_line1='QA only', city='Bengaluru', state='Karnataka', postal_code='560001', latitude='12.9716', longitude='77.5946')
        self.cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.client = APIClient()
        self.client.force_authenticate(self.customer)
        PlatformSetting.get_setting()

    def test_instant_category_filter_excludes_scheduled_only_products(self):
        self.product.is_instant_delivery = False
        self.product.save(update_fields=["is_instant_delivery"])
        response = self.client.get("/api/products/list/", {"instant_only": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.product.pk), [str(item["id"]) for item in response.data["results"]])
        response = self.client.get("/api/products/list/")
        self.assertIn(str(self.product.pk), [str(item["id"]) for item in response.data["results"]])

    def test_discount_filter_uses_real_compare_price(self):
        self.product.compare_price = Decimal('150')
        self.product.save(update_fields=['compare_price'])
        action = GetCustomerExploreAction()
        request = Request(APIRequestFactory().get('/api/customer/explore/', {'min_discount': '15'}))
        self.assertIn(self.product.pk, action._apply_filters(ProductRepository.get_all(), request).values_list('pk', flat=True))
        request = Request(APIRequestFactory().get('/api/customer/explore/', {'min_discount': '25'}))
        self.assertNotIn(self.product.pk, action._apply_filters(ProductRepository.get_all(), request).values_list('pk', flat=True))

    def test_store_price_sort_orders_real_inventory_both_directions(self):
        catalog = CatalogProduct.objects.create(name='QA bananas', slug='qa-catalog-bananas')
        from_product = Product.objects.create(catalog_product=catalog, vendor=self.vendor, name='QA bananas', slug='qa-bananas', price='60', stock=10, status='active', approval_status='approved')
        # The customer repository requires a visible category for store inventory.
        category = Category.objects.create(name='QA produce', slug='qa-produce', is_active=True, show_in_customer_ui=True)
        Product.objects.filter(pk__in=[self.product.pk, from_product.pk]).update(category=category)
        repository = VendorProductRepository()
        self.assertEqual(list(repository.get_customer_visible_for_vendor(self.vendor, sort='price_asc').values_list('price', flat=True)), [Decimal('60'), Decimal('120')])
        self.assertEqual(list(repository.get_customer_visible_for_vendor(self.vendor, sort='price_desc').values_list('price', flat=True)), [Decimal('120'), Decimal('60')])

    def test_delivery_sort_keeps_unknown_promises_last(self):
        records = [{'store_name': 'Unknown'}, {'store_name': 'Slow', 'estimated_delivery_minutes': 30}, {'store_name': 'Fast', 'estimated_delivery_minutes': 20}]
        self.assertEqual([item['store_name'] for item in sort_vendor_cards(records, 'delivery_time')], ['Fast', 'Slow', 'Unknown'])

    def test_vendor_node_excludes_inventory_from_another_merchant(self):
        owner = User.objects.create_user(username='other-store-owner', phone='9000000085', role='vendor')
        other_vendor = Vendor.objects.create(user=owner, store_name='Other QA store', phone='9000000085', email='other-store@example.test', address='QA', city='Bengaluru', state='Karnataka', postal_code='560001', status='approved')
        self.product.vendor = other_vendor
        self.product.save(update_fields=['vendor'])
        node = FulfillmentNode.objects.create(vendor=self.vendor, code='qa-owned-node', name='QA owned node', node_type='vendor_store')
        FulfillmentNodeInventory.objects.create(node=node, product=self.product, stock=10)
        response = self.client.get('/api/products/list/', {'fulfillment_node_id': str(node.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.product.pk), [str(item['id']) for item in response.data['results']])

    def preview(self):
        return public_price_breakup(calculate_checkout_preview(self.customer, self.address.pk, payment_method='cod', cod_upi_confirmed=True))

    def place(self, key, quote):
        return CreateOrdersFromCartAction().execute(self.customer, self.address.pk, cod_upi_confirmed=True, client_price_breakup=quote, client_idempotency_key=key)

    def test_changed_price_rejects_without_order_stock_or_cart_side_effect(self):
        quote=self.preview()
        self.product.price=Decimal('125');self.product.save(update_fields=['price'])
        with self.assertRaises(ValueError) as error:
            self.place('price-change',quote)
        self.assertEqual(error.exception.args[0]['code'],'quote_changed')
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())
        self.product.refresh_from_db();self.assertEqual(self.product.stock,10)
        self.assertEqual(self.cart.items.get().quantity,2)

    def test_submission_retry_returns_same_order_after_basket_cleared(self):
        first=self.place('same-request',self.preview())
        retry=self.place('same-request',{'final_payable':'999999'})
        self.assertEqual(first[0].pk,retry[0].pk)
        self.assertEqual(Order.objects.filter(customer=self.customer).count(),1)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,8)
        self.assertFalse(self.cart.items.exists())

    def test_missing_cod_confirmation_cannot_create_order(self):
        with self.assertRaises(ValueError):
            CreateOrdersFromCartAction().execute(self.customer,self.address.pk)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def old_order(self,status='delivered'):
        order=Order.objects.create(customer=self.customer,vendor=self.vendor,delivery_address=self.address,status=status,subtotal='240',total='270')
        OrderItem.objects.create(order=order,product=self.product,product_name=self.product.name,product_price='110',quantity=4,subtotal='440')
        return order

    def test_reorder_preview_is_read_only_and_reports_stock_and_price_changes(self):
        order=self.old_order();self.product.stock=1;self.product.save(update_fields=['stock'])
        preview=ReorderAction().execute(self.customer,order.pk,preview=True)
        self.assertEqual(preview['items'][0]['product_id'], str(self.product.pk))
        self.assertEqual(preview['items'][0]['quantity'],1)
        self.assertEqual(preview['items'][0]['previous_quantity'],4)
        self.assertEqual(preview['items'][0]['price'],'120.00')
        self.assertEqual(self.cart.items.get().quantity,2)
        ReorderAction().execute(self.customer,order.pk)
        self.assertEqual(self.cart.items.get().quantity,1)

    def test_unavailable_reorder_preserves_current_basket(self):
        order=self.old_order();self.product.is_available=False;self.product.save(update_fields=['is_available'])
        with self.assertRaises(ValueError):ReorderAction().execute(self.customer,order.pk)
        self.assertEqual(self.cart.items.get().quantity,2)

    def test_order_history_pagination_and_search_are_server_owned(self):
        for _ in range(21):self.old_order()
        page=self.client.get('/api/orders/list/?page=1')
        self.assertEqual(page.status_code,200);self.assertEqual(page.data['count'],21)
        self.assertTrue(page.data['next']);self.assertEqual(len(page.data['results']),20)
        older=self.client.get('/api/orders/list/?page=2')
        self.assertEqual(len(older.data['results']),1)
        missing=self.client.get('/api/orders/list/?search=no-such-item')
        self.assertEqual(missing.data['count'],0)
        store_match = self.client.get('/api/orders/list/', {'search': self.vendor.store_name})
        self.assertEqual(store_match.data['count'], 21)
        self.assertEqual(store_match.data['summary']['all'], 21)
        self.client.force_authenticate(self.other)
        private_search = self.client.get('/api/orders/list/', {'search': self.vendor.store_name})
        self.assertEqual(private_search.data['count'], 0)

    def test_cancellation_records_reason_and_rejects_other_customer(self):
        order=self.old_order(status='placed')
        self.client.force_authenticate(self.other)
        forbidden=self.client.post(f'/api/orders/{order.pk}/cancel/',{'reason':'Placed by mistake'},format='json')
        self.assertEqual(forbidden.status_code,400)
        order.refresh_from_db();self.assertEqual(order.status,'placed')
        self.client.force_authenticate(self.customer)
        response=self.client.post(f'/api/orders/{order.pk}/cancel/',{'reason':'Placed by mistake'},format='json')
        self.assertEqual(response.status_code,200)
        order.refresh_from_db();self.assertEqual(order.status,'cancelled')
        self.assertIn('Placed by mistake',order.tracking.get(status='cancelled').description)

    def test_customer_cannot_access_another_customers_order_or_issue(self):
        order=self.old_order()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/orders/{order.pk}/').status_code,404)
        self.assertEqual(self.client.post('/api/orders/issues/',{'order':str(order.pk),'issue_type':'mismatch','description':'QA'},format='json').status_code,404)

    def test_confirmation_reads_saved_order_and_hides_other_customer_details(self):
        order = self.old_order(status='placed')
        response = self.client.get(f'/api/customer/orders/{order.pk}/confirmation/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], str(order.pk))
        self.assertEqual(response.data['items_count'], 4)
        self.assertEqual(response.data['remaining_items_count'], 0)
        self.assertFalse(response.data['has_delivery_partner'])
        self.assertEqual(response.data['items_preview'][0]['quantity'], 4)
        self.assertEqual(response.data['items_preview'][0]['subtotal'], '440.00')
        self.assertIsNone(response.data['items_preview'][0]['image'])
        self.client.force_authenticate(self.other)
        private = self.client.get(f'/api/customer/orders/{order.pk}/confirmation/')
        self.assertEqual(private.status_code, 404)
        self.assertNotIn('delivery_address', private.data)

    def test_receipt_retries_reuse_owned_invoice_and_deny_other_customer(self):
        order = self.old_order()
        def prepared(invoice_id):
            return InvoiceRepository.update(InvoiceRepository.get_by_id(invoice_id), pdf_file='qa/owned-receipt.pdf')
        payload = {'order': str(order.pk), 'invoice_type': 'customer_receipt'}
        with patch('invoices.actions.invoice_actions.generate_pdf_invoice', side_effect=prepared) as generate:
            first = self.client.post('/api/invoices/generate/', payload, format='json')
            second = self.client.post('/api/invoices/generate/', payload, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(Invoice.objects.filter(order=order).count(), 1)
        self.client.force_authenticate(self.other)
        private = self.client.post('/api/invoices/generate/', payload, format='json')
        self.assertEqual(private.status_code, 403)
        self.assertNotIn('pdf_file', private.data)

    def test_address_pagination_is_complete_and_private(self):
        for number in range(21):
            Address.objects.create(user=self.customer, full_name=f'QA {number}', phone='9000000081', address_line1='QA only', city='Bengaluru', state='Karnataka', postal_code='560001')
        Address.objects.create(user=self.other, full_name='Other customer', phone='9000000082', address_line1='Private', city='Bengaluru', state='Karnataka', postal_code='560001')
        first = self.client.get('/api/auth/addresses/?page=1')
        second = self.client.get('/api/auth/addresses/?page=2')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['count'], 22)
        ids = [address['id'] for address in first.data['results'] + second.data['results']]
        self.assertEqual(len(ids), 22)
        self.assertEqual(len(set(ids)), 22)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/auth/addresses/{self.address.pk}/').status_code, 404)

    def test_default_address_patch_preserves_details_and_one_default(self):
        self.address.is_default = True
        self.address.save()
        second = Address.objects.create(user=self.customer, full_name='QA Office', phone='9000000081', address_line1='QA office', city='Bengaluru', state='Karnataka', postal_code='560001')
        response = self.client.patch(f'/api/auth/addresses/{second.pk}/', {'is_default': True}, format='json')
        self.assertEqual(response.status_code, 200)
        second.refresh_from_db()
        self.address.refresh_from_db()
        self.assertTrue(second.is_default)
        self.assertFalse(self.address.is_default)
        self.assertEqual(second.address_line1, 'QA office')
        self.assertEqual(Address.objects.filter(user=self.customer, is_default=True).count(), 1)

    def test_otp_success_exposes_server_cooldown_without_disclosing_code(self):
        self.client.force_authenticate(None)
        with patch('accounts.actions.auth_actions.RequestMobileOTPAction._queue_email_fallback', return_value=True):
            response = self.client.post('/api/auth/mobile/request-login-otp/', {'phone': self.customer.phone, 'email': self.customer.email}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['resend_after_seconds'], 60)
        self.assertGreater(response.data['expires_in_seconds'], 0)
        self.assertNotIn('otp', response.data)
        self.assertNotIn('dev_otp', response.data)
        cooldown = self.client.post('/api/auth/mobile/request-login-otp/', {'phone': self.customer.phone, 'email': self.customer.email}, format='json')
        self.assertEqual(cooldown.status_code, 400)
        self.assertEqual(cooldown.data['code'], 'otp_cooldown')
        self.assertTrue(0 < cooldown.data['retry_after_seconds'] <= 60)

    def test_otp_invalid_and_expired_are_distinct_without_authenticating(self):
        self.client.force_authenticate(None)
        phone = normalize_phone(self.customer.phone)
        record, code = MobileOTP.create_code(phone, 'login', email=self.customer.email)
        wrong = str((int(code) + 1) % 1000000).zfill(6)
        invalid = self.client.post('/api/auth/mobile/verify-login-otp/', {'phone': phone, 'email': self.customer.email, 'otp': wrong}, format='json')
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data['code'], 'otp_invalid')
        MobileOTP.objects.filter(pk=record.pk).update(expires_at=timezone.now() - timezone.timedelta(seconds=1))
        expired = self.client.post('/api/auth/mobile/verify-login-otp/', {'phone': phone, 'email': self.customer.email, 'otp': code}, format='json')
        self.assertEqual(expired.status_code, 400)
        self.assertEqual(expired.data['code'], 'otp_expired')
        record.refresh_from_db()
        self.assertFalse(record.is_used)
        self.assertNotIn('tokens', expired.data)

    def test_otp_rate_limit_reports_actual_retry_window(self):
        self.client.force_authenticate(None)
        phone = normalize_phone(self.customer.phone)
        for _ in range(5):
            MobileOTP.create_code(phone, 'login', email=self.customer.email)
        response = self.client.post('/api/auth/mobile/request-login-otp/', {'phone': phone, 'email': self.customer.email}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'otp_rate_limited')
        self.assertTrue(0 < response.data['retry_after_seconds'] <= 900)
        self.assertEqual(MobileOTP.objects.filter(phone=phone).count(), 5)

    def platform_inventory(self):
        category = Category.objects.create(name='Platform QA produce', slug='platform-qa-produce', is_active=True, show_in_customer_ui=True)
        self.product.category = category
        self.product.save(update_fields=['category'])
        node = FulfillmentNode.objects.create(code='qa-platform-stock', name='QA platform origin', node_type='platform_dark_store', city='Bengaluru', state='Karnataka', postal_code='560001', latitude=self.address.latitude, longitude=self.address.longitude)
        inventory = FulfillmentNodeInventory.objects.create(node=node, product=self.product, stock=10)
        return node, inventory

    def test_platform_node_promise_uses_actual_owned_available_inventory(self):
        node, inventory = self.platform_inventory()
        query = {'lat': str(self.address.latitude), 'lng': str(self.address.longitude), 'city': self.address.city, 'state': self.address.state, 'postal_code': self.address.postal_code}
        response = self.client.get('/api/customer/location/serviceability/', query)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_serviceable'])
        self.assertEqual(response.data['fulfillment_node']['id'], str(node.pk))
        self.assertEqual(response.data['fulfillment_node']['vendor_id'], '')
        self.assertEqual(response.data['nearest_store']['id'], str(self.vendor.pk))
        empty_owner = User.objects.create_user(username='platform-no-inventory', role='vendor')
        empty_merchant = Vendor.objects.create(user=empty_owner, store_name='No platform stock', phone='9000000090', email='empty@example.test', address='QA origin', city=self.address.city, state=self.address.state, postal_code=self.address.postal_code, latitude=self.address.latitude, longitude=self.address.longitude, status='approved', opening_time=time(0), closing_time=time(23,59))
        empty_child = Category.objects.create(name='No node inventory child', slug='no-node-inventory-child', parent=self.product.category, is_active=True, show_in_customer_ui=True)
        home = self.client.get('/api/customer/home/', query)
        self.assertEqual(home.status_code, 200)
        self.assertIn(str(self.vendor.pk), [store['id'] for store in home.data['nearby_stores']])
        self.assertNotIn(str(empty_merchant.pk), [store['id'] for store in home.data['nearby_stores']])
        root_category = next(category for category in home.data['categories'] if category['id'] == str(self.product.category_id))
        self.assertNotIn(str(empty_child.pk), [child['id'] for child in root_category['children']])

    def test_reserved_platform_inventory_does_not_promise_delivery(self):
        node, inventory = self.platform_inventory()
        inventory.reserved_stock = inventory.stock
        inventory.save(update_fields=['reserved_stock'])
        response = self.client.get('/api/customer/location/serviceability/', {'lat': str(self.address.latitude), 'lng': str(self.address.longitude), 'state': self.address.state})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_serviceable'])
        self.assertIsNone(response.data['fulfillment_node'])

    def test_platform_node_preserves_store_conflict_and_existing_basket(self):
        node, inventory = self.platform_inventory()
        owner = User.objects.create_user(username='platform-second-owner', role='vendor')
        merchant = Vendor.objects.create(user=owner, store_name='Second platform merchant', phone='9000000089', email='second@example.test', address='QA origin', city=self.address.city, state=self.address.state, postal_code=self.address.postal_code, latitude=self.address.latitude, longitude=self.address.longitude, status='approved', opening_time=time(0), closing_time=time(23,59))
        product = Product.objects.create(catalog_product=self.product.catalog_product, category=self.product.category, vendor=merchant, name='Second merchant apples', slug='platform-second-apples', price='75', stock=10, status='active', approval_status='approved')
        FulfillmentNodeInventory.objects.create(node=node, product=product, stock=10)
        response = self.client.post('/api/orders/cart/add/', {'product_id':str(product.pk), 'quantity':1, 'fulfillment_node_id':str(node.pk)}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'cart_store_conflict')
        self.assertEqual(CartItem.objects.get(cart=self.cart).product_id, self.product.pk)
        self.assertEqual(CartItem.objects.get(cart=self.cart).quantity, 2)
