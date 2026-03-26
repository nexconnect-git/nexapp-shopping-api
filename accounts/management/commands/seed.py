"""
Management command: python manage.py seed

Drops all data and re-seeds the database with realistic demo data:
  - 1 admin
  - 5 customers
  - 5 vendors  (4 approved + 1 pending)
  - 4 delivery partners (3 approved + 1 pending)
  - 12 categories (4 top-level + 8 sub)
  - 36 products spread across vendors
  - Addresses for every customer
  - 12 orders in various states with tracking
  - Product & vendor reviews
  - Cart items for active customers
  - Delivery earnings
  - Notifications (order, delivery, promo, system)
"""

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Reset and seed the database with demo data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        self._clear()
        self.stdout.write(self.style.WARNING('Seeding...'))
        with transaction.atomic():
            admin      = self._create_admin()
            customers  = self._create_customers()
            vendors    = self._create_vendors()
            partners   = self._create_delivery_partners()
            categories = self._create_categories()
            products   = self._create_products(vendors, categories)
            addresses  = self._create_addresses(customers)
            orders     = self._create_orders(customers, vendors, partners, products, addresses)
            self._create_reviews(customers, vendors, products, orders)
            self._create_carts(customers, products)
            self._create_notifications(customers, vendors, orders)
        self._print_summary(admin, customers, vendors, partners, categories, products, orders)

    # ── Clear ────────────────────────────────────────────────────────────────

    def _clear(self):
        from notifications.models import Notification
        from orders.models import OrderTracking, OrderItem, Order, CartItem, Cart
        from products.models import ProductReview, ProductImage, Product, Category
        from vendors.models import VendorReview, Vendor
        from delivery.models import DeliveryEarning, DeliveryReview, DeliveryPartner
        from accounts.models import Address, User

        Notification.objects.all().delete()
        OrderTracking.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        CartItem.objects.all().delete()
        Cart.objects.all().delete()
        ProductReview.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        VendorReview.objects.all().delete()
        Vendor.objects.all().delete()
        DeliveryEarning.objects.all().delete()
        DeliveryReview.objects.all().delete()
        DeliveryPartner.objects.all().delete()
        Address.objects.all().delete()
        User.objects.all().delete()

    # ── Admin ────────────────────────────────────────────────────────────────

    def _create_admin(self):
        from accounts.models import User
        user = User.objects.create_superuser(
            username='admin',
            email='admin@nexconnect.ng',
            password='admin1234',
            first_name='NexConnect',
            last_name='Admin',
            role='admin',
            phone='+2348000000001',
        )
        self.stdout.write(f'  Admin: admin / admin1234')
        return user

    # ── Customers ────────────────────────────────────────────────────────────

    def _create_customers(self):
        from accounts.models import User
        data = [
            ('tunde_bakare',    'tunde@gmail.com',   'Tunde',    'Bakare',   '+2348011111111'),
            ('ngozi_eze',       'ngozi@gmail.com',   'Ngozi',    'Eze',      '+2348022222222'),
            ('seun_oladele',    'seun@gmail.com',    'Seun',     'Oladele',  '+2348033333333'),
            ('blessing_uche',   'blessing@gmail.com','Blessing',  'Uche',     '+2348044444444'),
            ('adeola_hassan',   'adeola@gmail.com',  'Adeola',   'Hassan',   '+2348055555555'),
        ]
        users = []
        for username, email, first, last, phone in data:
            u = User.objects.create_user(
                username=username, email=email, password='pass1234',
                first_name=first, last_name=last, phone=phone, role='customer',
                is_verified=True,
            )
            users.append(u)
            self.stdout.write(f'  Customer: {username} / pass1234')
        return users

    # ── Vendors ──────────────────────────────────────────────────────────────

    def _create_vendors(self):
        from accounts.models import User
        from vendors.models import Vendor

        # (username, email, first, last, phone, store_name, description,
        #  address, city, lat, lng, status, featured, open, close, min_order, radius, avg_rating, total_ratings)
        data = [
            (
                'mama_put_express', 'mpe@nexconnect.ng', 'Chioma', 'Nwachukwu', '+2348066666666',
                'Mama Put Express',
                'Home-style Nigerian cooking — soups, swallows and rice dishes made with love and fresh ingredients.',
                '3 Ojuelegba Road', 'Lagos', '6.509200', '3.361500',
                'approved', True, '07:00', '22:00', 800, 10.0, Decimal('4.72'), 189,
            ),
            (
                'spice_garden_ng', 'sg@nexconnect.ng', 'Emeka', 'Obiora', '+2348077777777',
                'Spice Garden',
                'Premium grills, shawarma, burgers and continental plates for the modern Lagos palate.',
                '18 Adeola Hopewell Street', 'Victoria Island', '6.428900', '3.421300',
                'approved', True, '11:00', '23:00', 1500, 8.0, Decimal('4.55'), 134,
            ),
            (
                'greenleaf_market', 'gm@nexconnect.ng', 'Folake', 'Adeyemi', '+2348088888888',
                'Greenleaf Market',
                'Organic farm produce, fresh vegetables, grains and pantry essentials delivered same-day.',
                '5 Obafemi Awolowo Way', 'Ikeja', '6.601000', '3.347500',
                'approved', False, '06:00', '20:00', 1200, 12.0, Decimal('4.38'), 97,
            ),
            (
                'gadget_zone_ng', 'gz@nexconnect.ng', 'Ifeanyi', 'Nwosu', '+2348099999999',
                'Gadget Zone NG',
                'Authorised dealer of Samsung, Tecno, Infinix & Apple. Accessories and repairs available.',
                '41 Broad Street', 'Lagos Island', '6.454500', '3.396800',
                'approved', True, '09:00', '19:00', 5000, 20.0, Decimal('4.61'), 210,
            ),
            (
                'ankara_couture', 'ac@nexconnect.ng', 'Yetunde', 'Fashola', '+2348010101010',
                'Ankara Couture',
                'Bespoke Ankara fashion, ready-to-wear outfits, accessories and custom tailoring.',
                '7 Lagos-Badagry Expressway', 'Alaba', '6.477000', '3.248000',
                'pending', False, '09:00', '18:00', 2000, 15.0, Decimal('0'), 0,
            ),
        ]

        VENDOR_BANNERS = {
            'mama_put_express': ('1555396273-367ea4eb4db5', 'mpe-banner.jpg'),
            'spice_garden_ng':  ('1544025162-d76538b2a681', 'sg-banner.jpg'),
            'greenleaf_market': ('1542838132-92c53300491e', 'gm-banner.jpg'),
            'gadget_zone_ng':   ('1518770660439-4636190af475', 'gz-banner.jpg'),
            'ankara_couture':   ('1558618666-fcd25c85cd64', 'ac-banner.jpg'),
        }

        vendors = []
        for row in data:
            (uname, email, first, last, phone, store_name, desc, addr, city,
             lat, lng, vstatus, featured, open_t, close_t, min_order,
             radius, avg_rating, total_ratings) = row

            user = User.objects.create_user(
                username=uname, email=email, password='pass1234',
                first_name=first, last_name=last, phone=phone, role='vendor',
                is_verified=vstatus == 'approved',
            )
            vendor = Vendor.objects.create(
                user=user,
                store_name=store_name,
                description=desc,
                phone=phone,
                email=email,
                address=addr,
                city=city,
                state='Lagos',
                postal_code='10001',
                latitude=Decimal(lat),
                longitude=Decimal(lng),
                status=vstatus,
                is_open=vstatus == 'approved',
                opening_time=open_t,
                closing_time=close_t,
                min_order_amount=Decimal(str(min_order)),
                delivery_radius_km=Decimal(str(radius)),
                is_featured=featured,
                average_rating=avg_rating,
                total_ratings=total_ratings,
            )
            if uname in VENDOR_BANNERS:
                photo_id, fname = VENDOR_BANNERS[uname]
                banner = self._fetch_image(
                    f'https://images.unsplash.com/photo-{photo_id}?w=800&h=400&fit=crop&q=80',
                    fname,
                )
                if banner:
                    vendor.banner = banner
                    vendor.save(update_fields=['banner'])
            vendors.append(vendor)
            self.stdout.write(f'  Vendor: {uname} / pass1234  [{vstatus}]')
        return vendors

    # ── Delivery Partners ─────────────────────────────────────────────────────

    def _create_delivery_partners(self):
        from accounts.models import User
        from delivery.models import DeliveryPartner

        # (username, email, first, last, phone, vehicle, vehicle_num, license, approved, status, lat, lng, deliveries, earnings, rating)
        data = [
            ('kunle_ogundimu', 'kunle@nexconnect.ng', 'Kunle', 'Ogundimu', '+2348011223344',
             'motorcycle', 'LG-782-KGA', 'DL-101-NG', True,  'available',   '6.510000', '3.362000', 124, Decimal('62000'), Decimal('4.83')),
            ('aminu_sule',     'aminu@nexconnect.ng', 'Aminu', 'Sule',     '+2348022334455',
             'motorcycle', 'LG-341-MSL', 'DL-102-NG', True,  'on_delivery', '6.431000', '3.419000',  89, Decimal('44500'), Decimal('4.67')),
            ('tola_adewale',   'tola@nexconnect.ng',  'Tola',  'Adewale',  '+2348033445566',
             'bicycle',    'BX-009-TWA', 'DL-103-NG', True,  'offline',     '6.600500', '3.348000',  47, Decimal('23500'), Decimal('4.45')),
            ('peter_udo',      'peter@nexconnect.ng', 'Peter', 'Udo',      '+2348044556677',
             'car',        'LAG-221-PUD','DL-104-NG', False, 'offline',     None,        None,         0, Decimal('0'),     Decimal('0')),
        ]

        partners = []
        for uname, email, first, last, phone, vtype, vnum, lic, approved, pstatus, lat, lng, deliveries, earnings, rating in data:
            user = User.objects.create_user(
                username=uname, email=email, password='pass1234',
                first_name=first, last_name=last, phone=phone, role='delivery',
                is_verified=approved,
            )
            partner = DeliveryPartner.objects.create(
                user=user,
                vehicle_type=vtype,
                vehicle_number=vnum,
                license_number=lic,
                is_approved=approved,
                is_available=approved and pstatus == 'available',
                status=pstatus,
                current_latitude=Decimal(lat) if lat else None,
                current_longitude=Decimal(lng) if lng else None,
                total_deliveries=deliveries,
                total_earnings=earnings,
                average_rating=rating,
            )
            partners.append(partner)
            label = 'approved' if approved else 'pending'
            self.stdout.write(f'  Delivery: {uname} / pass1234  [{label}]')
        return partners

    # ── Categories ────────────────────────────────────────────────────────────

    def _create_categories(self):
        from products.models import Category

        top_level = [
            ('Nigerian Food',  'nigerian-food',  'Traditional Nigerian meals & street food',   1),
            ('Continental',    'continental',    'Western, Asian & international cuisine',       2),
            ('Fresh Produce',  'fresh-produce',  'Farm-fresh fruits, vegetables & dairy',        3),
            ('Electronics',    'electronics',    'Phones, gadgets & accessories',               4),
            ('Fashion',        'fashion',        'Clothing, footwear & accessories',            5),
        ]
        subs = [
            ('nigerian-food', 'Soups & Swallows',  'soups-swallows',   'Egusi, Ogbono, Pounded Yam & more'),
            ('nigerian-food', 'Rice Dishes',        'rice-dishes',      'Jollof, fried rice, coconut rice'),
            ('nigerian-food', 'Small Chops & Snacks','small-chops',     'Puff puff, spring rolls, suya'),
            ('continental',  'Grills & Burgers',   'grills-burgers',   'BBQ, burgers, shawarma'),
            ('continental',  'Drinks & Juices',    'drinks-juices',    'Soft drinks, fresh juice, smoothies'),
            ('fresh-produce','Fruits & Vegetables','fruits-vegetables', 'Seasonal fresh produce'),
            ('fresh-produce','Pantry & Dairy',     'pantry-dairy',     'Eggs, milk, grains & cooking staples'),
            ('electronics',  'Smartphones',        'smartphones',      'Latest mobile phones'),
            ('electronics',  'Accessories',        'tech-accessories', 'Cases, chargers, earbuds & cables'),
        ]

        cats = {}
        for name, slug, desc, order in top_level:
            c = Category.objects.create(name=name, slug=slug, description=desc, display_order=order)
            cats[slug] = c
            self.stdout.write(f'  Category: {name}')

        for parent_slug, name, slug, desc in subs:
            c = Category.objects.create(name=name, slug=slug, description=desc, parent=cats[parent_slug])
            cats[slug] = c

        return cats

    # ── Products ──────────────────────────────────────────────────────────────

    def _make_slug(self, name, vendor_name):
        from products.models import Product
        base = slugify(f"{vendor_name}-{name}")
        slug = base
        suffix = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def _create_products(self, vendors, categories):
        from products.models import Product

        mpe, sg, gm, gz, ac = vendors  # Mama Put, Spice Garden, Greenleaf, Gadget Zone, Ankara Couture

        # (vendor, name, cat_slug, price, compare_price, sku, stock, unit, available, featured, description)
        items = [
            # ── Mama Put Express ── Nigerian Food
            (mpe, 'Egusi Soup + Pounded Yam',    'soups-swallows',  2200, 2800, 'MPE-ESP-01', 40, 'plate', True,  True,
             'Rich egusi soup cooked with assorted meats, palm oil and traditional spices. Served with smooth pounded yam.'),
            (mpe, 'Ogbono Soup + Eba',           'soups-swallows',  2000, 2500, 'MPE-OGE-01', 35, 'plate', True,  False,
             'Thick draw soup made with ground ogbono seeds, assorted meats and stockfish. Served with eba.'),
            (mpe, 'Banga Soup + Starch',         'soups-swallows',  2500, None, 'MPE-BGS-01', 25, 'plate', True,  False,
             'Delta-style banga soup cooked with fresh palm fruit. Paired with native starch.'),
            (mpe, 'Jollof Rice + Chicken',       'rice-dishes',     1800, 2200, 'MPE-JRC-01', 60, 'plate', True,  True,
             'Party-style jollof rice with smoky tomato base, served with a full chicken leg quarter.'),
            (mpe, 'Fried Rice + Beef & Prawns',  'rice-dishes',     2000, 2500, 'MPE-FRP-01', 50, 'plate', True,  False,
             'Colourful fried rice loaded with mixed vegetables, tender beef strips and tiger prawns.'),
            (mpe, 'Coconut Rice + Fish',         'rice-dishes',     1900, None, 'MPE-CRF-01', 30, 'plate', True,  False,
             'Creamy coconut-infused rice served with well-seasoned grilled tilapia.'),
            (mpe, 'Puff Puff (6 pieces)',        'small-chops',      500,  700, 'MPE-PF6-01', 80, 'pack',  True,  False,
             'Soft and fluffy deep-fried dough balls, lightly sweetened. A beloved Nigerian street snack.'),
            (mpe, 'Small Chops Platter',         'small-chops',     3500, 4500, 'MPE-SCP-01', 20, 'platter',True, True,
             'Party platter of spring rolls, samosas, puff puff and peppered gizzard. Serves 2-3.'),

            # ── Spice Garden ── Continental
            (sg,  'Chicken Shawarma (Large)',    'grills-burgers',  2500, 3000, 'SG-CSL-01',  45, 'wrap',  True,  True,
             'Juicy marinated chicken strips, garlic sauce, fresh veggies wrapped in warm flatbread. Large size.'),
            (sg,  'Beef Suya Skewers (5 sticks)','grills-burgers', 2000, None, 'SG-BSS-01',  50, 'pack',  True,  False,
             'Classic Northern Nigerian suya — thinly sliced beef coated in spicy yaji and grilled to perfection.'),
            (sg,  'BBQ Chicken (half)',          'grills-burgers',  3500, 4000, 'SG-BBQ-01',  30, 'portion',True, True,
             'Half chicken slow-grilled over charcoal with house BBQ glaze. Served with coleslaw and chips.'),
            (sg,  'Gourmet Beef Burger',         'grills-burgers',  2800, 3200, 'SG-GBB-01',  35, 'burger', True, False,
             'Double beef patty with cheddar, caramelised onions, jalapeños and smoky mayo on a brioche bun.'),
            (sg,  'Fresh Orange Juice (500ml)',  'drinks-juices',    800,  None, 'SG-FOJ-01', 100,'bottle', True, False,
             'Cold-pressed fresh oranges — no sugar added. Packed with vitamins.'),
            (sg,  'Chapman Special',            'drinks-juices',    1200, None, 'SG-CHS-01',  60, 'glass',  True, False,
             'Classic Nigerian Chapman cocktail with Fanta, Sprite, Ribena, cucumber and ice.'),
            (sg,  'Smoothie Bowl (Mixed Berry)', 'drinks-juices',   1800, 2200, 'SG-SMB-01',  25, 'bowl',   True, True,
             'Thick acai-berry smoothie base topped with banana, granola, honey and chia seeds.'),

            # ── Greenleaf Market ── Fresh Produce
            (gm,  'Roma Tomatoes (1kg)',         'fruits-vegetables', 600, None, 'GM-TOM-01',  90, 'kg',    True, False,
             'Firm, ripe Roma tomatoes — perfect for stew and sauces. Sourced from Kaduna farms.'),
            (gm,  'Ugu (Fluted Pumpkin) Bunch',  'fruits-vegetables', 350, None, 'GM-UGU-01',  70, 'bunch', True, False,
             'Fresh ugu leaves, hand-picked and cleaned. Essential for soups and vegetable stews.'),
            (gm,  'Watermelon (3-4kg)',           'fruits-vegetables',1800, None,'GM-WTM-01',  20, 'piece', True, False,
             'Large seedless watermelon, sweet and well-chilled. Ideal for parties and family.'),
            (gm,  'Pineapple (medium)',           'fruits-vegetables', 700,  900, 'GM-PIN-01',  40, 'piece', True, True,
             'Sweet, ripe pineapple from Edo State farms. Rich in Vitamin C and digestive enzymes.'),
            (gm,  'Mixed Vegetable Pack (500g)',  'fruits-vegetables', 850, None, 'GM-MVP-01',  55, 'pack',  True, True,
             'Ready-to-cook mix of carrots, green beans, sweet corn and green peas. Pre-washed.'),
            (gm,  'Crate of Eggs (30 pieces)',    'pantry-dairy',    2500, 2800, 'GM-EGG-01',  45, 'crate', True, True,
             'Fresh free-range eggs from a local poultry farm. Rich yolk, perfect for frying and baking.'),
            (gm,  'Peak Full Cream Milk (1L)',    'pantry-dairy',    1400, None, 'GM-PKM-01',  80, 'bottle', True, False,
             'Long-life full cream milk. Ideal for tea, cereal and cooking.'),
            (gm,  'Ofada Rice (1kg)',             'pantry-dairy',    1200, 1500, 'GM-OFR-01',  60, 'kg',    True, False,
             'Aromatic Nigerian ofada brown rice, unpolished and nutrient-rich.'),

            # ── Gadget Zone NG ── Electronics
            (gz,  'Samsung Galaxy A55 (128GB)',   'smartphones',    89000,110000,'GZ-SGA55-1', 18, 'unit',  True, True,
             '6.6" Super AMOLED display, 50MP camera, 5000mAh battery. 1 year warranty included.'),
            (gz,  'Tecno Spark 20 Pro+',          'smartphones',    68000, 78000,'GZ-TSP20-1', 22, 'unit',  True, False,
             '6.78" FHD+ display, 108MP main camera, 5000mAh battery with 33W fast charge.'),
            (gz,  'iPhone 15 (128GB, Black)',      'smartphones',   320000,360000,'GZ-IP15-01',  6, 'unit',  True, True,
             'Apple A16 Bionic chip, 48MP camera system, USB-C, Dynamic Island. 1 year Apple warranty.'),
            (gz,  'Infinix Note 40 Pro',           'smartphones',    72000, 85000,'GZ-IN40-01', 20, 'unit',  True, False,
             '6.78" AMOLED, 108MP AI camera, MagSafe wireless charging, 5000mAh battery.'),
            (gz,  'Anker 65W GaN Charger',         'tech-accessories',4500,  5500,'GZ-ANC65-1', 60, 'unit',  True, True,
             'Compact GaN fast charger — charges laptops, tablets and phones simultaneously. 2 USB-C + 1 USB-A.'),
            (gz,  'JBL Tune 130NC TWS Earbuds',    'tech-accessories',18000, 22000,'GZ-JBL13-1', 35, 'unit',  True, True,
             'Active noise cancellation, 40hr battery life, JBL Deep Bass sound. IPX4 water resistant.'),
            (gz,  'Oraimo Screen Protector (2pk)', 'tech-accessories', 1500, 2000,'GZ-OSP-01',  90, 'pack',  True, False,
             'Tempered glass, 9H hardness, anti-fingerprint coating. Universal fit for 6.5–6.8" phones.'),
            (gz,  'Baseus Power Bank 20000mAh',    'tech-accessories', 15000,18000,'GZ-BPB20-1', 28, 'unit',  True, False,
             '20000mAh with 65W fast charge. Charges MacBook in under 2 hours. Slim aluminium body.'),

            # ── Ankara Couture ── Fashion (pending vendor, products hidden publicly)
            (ac,  'Adire Ombre Blouse (S–XL)',     'fashion',         9500, 13000,'AC-AIB-01',  25, 'piece', True, True,
             'Hand-dyed adire tie-dye blouse in rich indigo tones. Available in S, M, L, XL.'),
            (ac,  'Kaftan with Embroidery (M–XXL)', 'fashion',        18000, 24000,'AC-KFE-01',  18, 'piece', True, False,
             "Men's senator kaftan with gold hand-embroidered neckline. Machine-washable fabric."),
            (ac,  'Iro & Buba Coord Set',           'fashion',        25000, 32000,'AC-IBS-01',  12, 'set',   True, True,
             'Traditional Yoruba wrapper and blouse set in vibrant Ankara print. One size fits most.'),
            (ac,  'Beaded Waist Belt',              'fashion',         4500,  6000,'AC-BWB-01',  40, 'piece', True, False,
             'Handcrafted multi-strand beaded waist belt in gold and coral. Adjustable sizing.'),
        ]

        # SKU → (unsplash_photo_id, filename)
        PRODUCT_IMG = {
            'MPE-ESP-01': ('1574484284002-952d92456975', 'egusi-soup.jpg'),
            'MPE-OGE-01': ('1565557623262-b51c2513a641', 'ogbono-soup.jpg'),
            'MPE-BGS-01': ('1540189799613-df32ae82e55f', 'banga-soup.jpg'),
            'MPE-JRC-01': ('1604329760661-e71dc83f8f26', 'jollof-rice.jpg'),
            'MPE-FRP-01': ('1512058564366-18510be2db19', 'fried-rice.jpg'),
            'MPE-CRF-01': ('1536304993831-773bece260d3', 'coconut-rice.jpg'),
            'MPE-PF6-01': ('1626700051175-6818013e1d4f', 'puff-puff.jpg'),
            'MPE-SCP-01': ('1589302168068-964664d93dc0', 'small-chops.jpg'),
            'SG-CSL-01':  ('1621510456681-2330135e5871', 'shawarma.jpg'),
            'SG-BSS-01':  ('1555396273-367ea4eb4db5',   'suya-skewers.jpg'),
            'SG-BBQ-01':  ('1544025162-d76538b2a681',   'bbq-chicken.jpg'),
            'SG-GBB-01':  ('1568901346375-23c9450c58cd', 'burger.jpg'),
            'SG-FOJ-01':  ('1621506289937-a8e1df24dca4', 'orange-juice.jpg'),
            'SG-CHS-01':  ('1546173159-315724a31696',   'chapman-drink.jpg'),
            'SG-SMB-01':  ('1590301157890-4d0fe6a3d1a7', 'smoothie-bowl.jpg'),
            'GM-TOM-01':  ('1546069901-ba9599a7e63c',   'tomatoes.jpg'),
            'GM-UGU-01':  ('1574914629385-bed9a63c7f0e', 'leafy-greens.jpg'),
            'GM-WTM-01':  ('1587049633312-d628ae50a8ae', 'watermelon.jpg'),
            'GM-PIN-01':  ('1550258987-190a2d41a8ba',   'pineapple.jpg'),
            'GM-MVP-01':  ('1576045057995-568f588f82fb', 'mixed-veg.jpg'),
            'GM-EGG-01':  ('1582722872445-44dc5f7e3c8f', 'eggs.jpg'),
            'GM-PKM-01':  ('1550583724-b2692b85b150',   'milk.jpg'),
            'GM-OFR-01':  ('1594491210-f8793b884a57',   'ofada-rice.jpg'),
            'GZ-SGA55-1': ('1610945264803-c22b62d2a7b3', 'samsung-a55.jpg'),
            'GZ-TSP20-1': ('1574953899810-d89b9e7e8578', 'tecno-spark.jpg'),
            'GZ-IP15-01': ('1591337676887-a217a6970a8a', 'iphone-15.jpg'),
            'GZ-IN40-01': ('1598327105854-4a1a3db44e35', 'infinix-note.jpg'),
            'GZ-ANC65-1': ('1625895197185-efcec01c3559', 'anker-charger.jpg'),
            'GZ-JBL13-1': ('1590658268037-6bf12165a8df', 'jbl-earbuds.jpg'),
            'GZ-OSP-01':  ('1598965675045-45c5e72c7d05', 'screen-protector.jpg'),
            'GZ-BPB20-1': ('1588591795084-1770cb3be374', 'power-bank.jpg'),
            'AC-AIB-01':  ('1515886657613-9f3515b0c78f', 'ankara-blouse.jpg'),
            'AC-KFE-01':  ('1583391733956-3750e0ff4e8b', 'kaftan.jpg'),
            'AC-IBS-01':  ('1558618666-fcd25c85cd64',   'iro-buba.jpg'),
            'AC-BWB-01':  ('1611085583191-a3b181a88401', 'beaded-belt.jpg'),
        }

        products = []
        for vendor, name, cat_slug, price, compare_price, sku, stock, unit, available, featured, desc in items:
            p = Product.objects.create(
                vendor=vendor,
                category=categories.get(cat_slug),
                name=name,
                slug=self._make_slug(name, vendor.store_name),
                description=desc,
                price=Decimal(str(price)),
                compare_price=Decimal(str(compare_price)) if compare_price else None,
                sku=sku,
                stock=stock,
                unit=unit,
                is_available=available,
                is_featured=featured,
                average_rating=Decimal(str(round(random.uniform(3.8, 5.0), 2))),
                total_ratings=random.randint(5, 60),
            )
            if sku in PRODUCT_IMG:
                photo_id, fname = PRODUCT_IMG[sku]
                img_file = self._fetch_image(
                    f'https://images.unsplash.com/photo-{photo_id}?w=400&h=400&fit=crop&q=80',
                    fname,
                )
                if img_file:
                    from products.models import ProductImage
                    ProductImage.objects.create(product=p, image=img_file, is_primary=True)
            products.append(p)

        self.stdout.write(f'  Products: {len(products)} created')
        return products

    # ── Image helper ──────────────────────────────────────────────────────────

    def _fetch_image(self, url, filename):
        """Download an image from URL; return ContentFile or None."""
        import urllib.request
        from django.core.files.base import ContentFile
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                return ContentFile(resp.read(), name=filename)
        except Exception as e:
            self.stdout.write(f'    [warn] Image fetch failed for {filename}: {e}')
            return None

    # ── Addresses ─────────────────────────────────────────────────────────────

    def _create_addresses(self, customers):
        from accounts.models import Address

        # (customer_idx, label, full_name, phone, line1, line2, city, state, postal, lat, lng, is_default)
        addr_data = [
            (0, 'home', 'Tunde Bakare',   '+2348011111111', '14 Opebi Road',          '',                  'Ikeja',          'Lagos', '10001', '6.598000', '3.358000', True),
            (0, 'work', 'Tunde Bakare',   '+2348011111111', '2 Kofo Abayomi Street',  'Victoria Island',   'Lagos Island',   'Lagos', '10002', '6.432000', '3.414000', False),
            (1, 'home', 'Ngozi Eze',      '+2348022222222', '7 Glover Road',          '',                  'Ikoyi',          'Lagos', '10003', '6.447000', '3.430000', True),
            (1, 'other','Ngozi Eze',      '+2348022222222', '33 Bode Thomas Street',  '',                  'Surulere',       'Lagos', '10004', '6.501000', '3.355000', False),
            (2, 'home', 'Seun Oladele',   '+2348033333333', '9 Association Avenue',   'Fadeyi',            'Shomolu',        'Lagos', '10005', '6.528000', '3.382000', True),
            (3, 'home', 'Blessing Uche',  '+2348044444444', '21 Adewale Crescent',    '',                  'Lekki Phase 1',  'Lagos', '10006', '6.435000', '3.476000', True),
            (3, 'work', 'Blessing Uche',  '+2348044444444', '10 Idowu Taylor Street', '',                  'Victoria Island','Lagos', '10002', '6.427500', '3.415000', False),
            (4, 'home', 'Adeola Hassan',  '+2348055555555', '5 Admiralty Way',        '',                  'Lekki Phase 1',  'Lagos', '10006', '6.434000', '3.481000', True),
        ]

        addresses = []
        for user_idx, label, full_name, phone, line1, line2, city, state, postal, lat, lng, is_default in addr_data:
            a = Address.objects.create(
                user=customers[user_idx], label=label, full_name=full_name, phone=phone,
                address_line1=line1, address_line2=line2, city=city, state=state,
                postal_code=postal, latitude=Decimal(lat), longitude=Decimal(lng),
                is_default=is_default,
            )
            addresses.append(a)

        self.stdout.write(f'  Addresses: {len(addresses)} created')
        return addresses

    # ── Orders ────────────────────────────────────────────────────────────────

    def _create_orders(self, customers, vendors, partners, products, addresses):
        from orders.models import Order, OrderItem, OrderTracking

        mpe, sg, gm, gz, _ = vendors
        cust0, cust1, cust2, cust3, cust4 = customers
        partner0, partner1, partner2, _ = partners  # kunle, aminu, tola

        # address index references
        addr = {
            'tunde_home': addresses[0],
            'tunde_work': addresses[1],
            'ngozi_home': addresses[2],
            'seun_home':  addresses[4],
            'blessing_home': addresses[5],
            'adeola_home': addresses[7],
        }

        # Products by vendor
        mpe_p = [p for p in products if p.vendor == mpe]
        sg_p  = [p for p in products if p.vendor == sg]
        gm_p  = [p for p in products if p.vendor == gm]
        gz_p  = [p for p in products if p.vendor == gz]

        # (customer, vendor, addr_key, partner|None, status, [(product, qty)], notes)
        orders_spec = [
            # Completed deliveries
            (cust0, mpe, 'tunde_home', partner0.user,  'delivered',
             [(mpe_p[0], 1), (mpe_p[3], 1)], 'Extra pepper please'),
            (cust1, sg,  'ngozi_home', partner1.user,  'delivered',
             [(sg_p[0], 2), (sg_p[4], 2)],   ''),
            (cust3, gm,  'blessing_home', partner2.user, 'delivered',
             [(gm_p[5], 1), (gm_p[6], 2), (gm_p[7], 1)], 'Leave at gate'),

            # Active deliveries
            (cust2, mpe, 'seun_home', partner1.user,  'on_the_way',
             [(mpe_p[4], 1), (mpe_p[6], 2)], ''),
            (cust4, sg,  'adeola_home', partner0.user, 'on_the_way',
             [(sg_p[1], 3), (sg_p[5], 1)],  'Extra napkins'),

            # In-progress orders
            (cust0, gz,  'tunde_work', None, 'ready',
             [(gz_p[0], 1)], 'Include warranty card'),
            (cust1, mpe, 'ngozi_home', None, 'preparing',
             [(mpe_p[1], 1), (mpe_p[7], 1)], ''),
            (cust3, sg,  'blessing_home', None, 'preparing',
             [(sg_p[2], 1), (sg_p[3], 1)],  'Well done, no pink'),

            # Early-stage orders
            (cust4, gm,  'adeola_home', None, 'confirmed',
             [(gm_p[0], 2), (gm_p[4], 1)], ''),
            (cust2, gz,  'seun_home',  None, 'confirmed',
             [(gz_p[5], 1), (gz_p[6], 3)], ''),
            (cust0, sg,  'tunde_home', None, 'placed',
             [(sg_p[2], 1)], ''),

            # Cancelled
            (cust1, gz,  'ngozi_home', None, 'cancelled',
             [(gz_p[2], 1), (gz_p[7], 1)], ''),
        ]

        tracking_chain = {
            'placed':     ['placed'],
            'confirmed':  ['placed', 'confirmed'],
            'preparing':  ['placed', 'confirmed', 'preparing'],
            'ready':      ['placed', 'confirmed', 'preparing', 'ready'],
            'on_the_way': ['placed', 'confirmed', 'preparing', 'ready', 'picked_up', 'on_the_way'],
            'delivered':  ['placed', 'confirmed', 'preparing', 'ready', 'picked_up', 'on_the_way', 'delivered'],
            'cancelled':  ['placed', 'cancelled'],
        }
        descriptions = {
            'placed':    'Order placed by customer.',
            'confirmed': 'Order confirmed by vendor.',
            'preparing': 'Vendor is preparing your order.',
            'ready':     'Order is ready for pickup.',
            'picked_up': 'Picked up by delivery partner.',
            'on_the_way':'Your order is on the way.',
            'delivered': 'Order delivered successfully.',
            'cancelled': 'Order was cancelled.',
        }

        orders = []
        for customer, vendor, addr_key, delivery_user, ostatus, order_items, notes in orders_spec:
            subtotal = sum(p.price * qty for p, qty in order_items)
            delivery_fee = Decimal('700') if ostatus != 'cancelled' else Decimal('0')
            total = subtotal + delivery_fee

            order = Order.objects.create(
                customer=customer,
                vendor=vendor,
                delivery_address=addr[addr_key],
                delivery_partner=delivery_user,
                status=ostatus,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                discount=Decimal('0'),
                total=total,
                notes=notes,
                estimated_delivery_time=random.choice([25, 30, 35, 40, 45]),
            )

            for product, qty in order_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=qty,
                    subtotal=product.price * qty,
                )

            for s in tracking_chain.get(ostatus, []):
                OrderTracking.objects.create(order=order, status=s, description=descriptions[s])

            orders.append(order)

        self.stdout.write(f'  Orders: {len(orders)} created')
        return orders

    # ── Reviews ───────────────────────────────────────────────────────────────

    def _create_reviews(self, customers, vendors, products, orders):
        from products.models import ProductReview
        from vendors.models import VendorReview

        mpe, sg, gm, gz, _ = vendors
        cust0, cust1, cust2, cust3, cust4 = customers

        # Product reviews — (product_idx_in_products, customer, rating, comment)
        product_reviews = [
            (0,  cust0, 5, 'Best egusi I\'ve had delivered. The pounded yam was perfectly smooth!'),
            (0,  cust1, 4, 'Tasty but portion could be bigger for the price.'),
            (3,  cust0, 5, 'Party jollof on point! Smoky and well-seasoned.'),
            (3,  cust2, 5, 'Exactly like mama\'s jollof. Will definitely reorder.'),
            (8,  cust1, 5, 'Giant shawarma, very filling. The garlic sauce is addictive.'),
            (8,  cust3, 4, 'Good shawarma but took a while to arrive.'),
            (10, cust4, 5, 'The BBQ chicken is unmatched. Perfectly charred and juicy.'),
            (15, cust0, 4, 'Tomatoes were very fresh. Great value for money.'),
            (20, cust3, 5, 'Eggs arrived safely packed. All 30 intact!'),
            (24, cust0, 5, 'Samsung A55 is fast and camera is excellent. Arrived sealed.'),
            (28, cust2, 4, 'Anker charger charges my phone super fast. Compact design.'),
            (29, cust4, 5, 'JBL earbuds sound incredible and noise cancellation works great.'),
        ]

        for prod_idx, customer, rating, comment in product_reviews:
            if prod_idx < len(products):
                try:
                    ProductReview.objects.create(
                        product=products[prod_idx],
                        customer=customer,
                        rating=rating,
                        comment=comment,
                    )
                except Exception:
                    pass  # skip duplicate

        # Vendor reviews
        vendor_reviews = [
            (mpe, cust0, 5, 'Consistent quality every time. Food arrives hot and well-packaged.'),
            (mpe, cust2, 4, 'Great food, slightly late on one delivery but food quality makes up for it.'),
            (sg,  cust1, 5, 'Spice Garden never disappoints. Best suya in Lagos!'),
            (sg,  cust4, 4, 'Good variety of food. Presentation is great too.'),
            (gm,  cust3, 5, 'Always fresh produce. You can tell they source carefully.'),
            (gz,  cust0, 5, 'Legit products with warranty. Very professional packaging.'),
        ]

        for vendor, customer, rating, comment in vendor_reviews:
            try:
                VendorReview.objects.create(vendor=vendor, customer=customer, rating=rating, comment=comment)
            except Exception:
                pass

        self.stdout.write(f'  Reviews: {len(product_reviews) + len(vendor_reviews)} created')

    # ── Carts ─────────────────────────────────────────────────────────────────

    def _create_carts(self, customers, products):
        from orders.models import Cart, CartItem

        mpe_p = [p for p in products if p.vendor.store_name == 'Mama Put Express']
        sg_p  = [p for p in products if p.vendor.store_name == 'Spice Garden']
        gz_p  = [p for p in products if p.vendor.store_name == 'Gadget Zone NG']

        # (customer, [(product, qty)])
        cart_data = [
            (customers[1], [(sg_p[0], 1), (sg_p[5], 2)]),   # Ngozi — Shawarma + Chapman
            (customers[2], [(mpe_p[3], 2), (mpe_p[6], 1)]), # Seun — Jollof + Puff Puff
            (customers[4], [(gz_p[1], 1), (gz_p[4], 1)]),   # Adeola — Tecno + Charger
        ]

        count = 0
        for customer, items in cart_data:
            cart = Cart.objects.create(user=customer)
            for product, qty in items:
                CartItem.objects.create(cart=cart, product=product, quantity=qty)
                count += 1

        self.stdout.write(f'  Cart items: {count} created across {len(cart_data)} carts')

    # ── Notifications ─────────────────────────────────────────────────────────

    def _create_notifications(self, customers, vendors, orders):
        from notifications.models import Notification

        cust0, cust1, cust2, cust3, cust4 = customers
        delivered_orders = [o for o in orders if o.status == 'delivered']
        on_the_way_orders = [o for o in orders if o.status == 'on_the_way']

        notifs = []

        # Order notifications
        for order in delivered_orders:
            notifs.append(Notification(
                user=order.customer,
                title='Order Delivered!',
                message=f'Your order #{order.order_number} has been delivered. Enjoy your order!',
                notification_type='order',
                is_read=True,
                data={'order_id': str(order.id), 'order_number': order.order_number},
            ))

        for order in on_the_way_orders:
            notifs.append(Notification(
                user=order.customer,
                title='Your Order is On the Way',
                message=f'Order #{order.order_number} has been picked up and is heading to you.',
                notification_type='delivery',
                is_read=False,
                data={'order_id': str(order.id), 'order_number': order.order_number},
            ))

        # Promo notifications
        notifs += [
            Notification(user=cust0, title='Weekend Special — 10% Off!',
                         message='Get 10% off all orders from Mama Put Express this weekend. Use code: WEEKEND10.',
                         notification_type='promo', is_read=False),
            Notification(user=cust1, title='Flash Sale: Gadget Zone',
                         message='Up to 15% off selected smartphones today only. Shop now before stock runs out!',
                         notification_type='promo', is_read=True),
            Notification(user=cust2, title='New Vendor Alert!',
                         message='Ankara Couture is coming soon to NexConnect. Watch this space!',
                         notification_type='promo', is_read=False),
            Notification(user=cust3, title='Free Delivery This Weekend',
                         message='Order from Greenleaf Market this Saturday and get free delivery. No minimum order.',
                         notification_type='promo', is_read=False),
            Notification(user=cust4, title='Rate Your Last Order',
                         message='How was your last order from Spice Garden? Leave a review and earn 50 reward points.',
                         notification_type='promo', is_read=False),
        ]

        # System notifications
        notifs += [
            Notification(user=cust0, title='Welcome to NexConnect!',
                         message='Your account is verified. Start exploring hundreds of vendors near you.',
                         notification_type='system', is_read=True),
            Notification(user=cust1, title='Password Changed',
                         message='Your password was changed successfully. If this wasn\'t you, contact support.',
                         notification_type='system', is_read=True),
            Notification(user=cust3, title='New Address Saved',
                         message='Your delivery address at Lekki Phase 1 has been saved successfully.',
                         notification_type='system', is_read=True),
        ]

        Notification.objects.bulk_create(notifs)
        self.stdout.write(f'  Notifications: {len(notifs)} created')

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self, admin, customers, vendors, partners, categories, products, orders):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 58))
        self.stdout.write(self.style.SUCCESS('  Database seeded successfully'))
        self.stdout.write(self.style.SUCCESS('=' * 58))
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('LOGIN CREDENTIALS'))
        self.stdout.write('')
        self.stdout.write('  ADMIN')
        self.stdout.write('    admin / admin1234')
        self.stdout.write('')
        self.stdout.write('  CUSTOMERS  (password: pass1234)')
        for c in customers:
            self.stdout.write(f'    {c.username}')
        self.stdout.write('')
        self.stdout.write('  VENDORS  (password: pass1234)')
        for v in vendors:
            self.stdout.write(f'    {v.user.username:<25}  [{v.status}]  {v.store_name}')
        self.stdout.write('')
        self.stdout.write('  DELIVERY PARTNERS  (password: pass1234)')
        for p in partners:
            label = 'approved' if p.is_approved else 'pending'
            self.stdout.write(f'    {p.user.username:<25}  [{label}]  {p.vehicle_type}')
        self.stdout.write('')
        self.stdout.write(
            f'  {len(categories)} categories  |  {len(products)} products  |  '
            f'{len(orders)} orders'
        )
        self.stdout.write(self.style.SUCCESS('=' * 58))
