# NexConnect Backend

Django REST Framework API for the NexConnect multi-vendor food/goods delivery platform.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 4.x + Django REST Framework |
| Auth | SimpleJWT (access 1 day / refresh 7 days, rotation enabled) |
| Database | SQLite (dev) — swap `DATABASES` for PostgreSQL in production |
| CORS | django-cors-headers (`CORS_ALLOW_ALL_ORIGINS=True` in dev) |
| Filters | django-filter, DRF SearchFilter, OrderingFilter |
| Pagination | `PageNumberPagination`, 20 items/page |

## Project Layout

```
backend/
├── accounts/       # User model, auth, addresses, admin user views
├── products/       # Categories, products, product reviews
├── orders/         # Cart, order creation, order tracking
├── vendors/        # Vendor registration, dashboard, vendor reviews, admin vendor views
├── delivery/       # Delivery partner registration, delivery workflow, admin delivery views
├── notifications/  # In-app notification model and views
└── backend/        # Django project config (settings, urls, admin_urls)
```

## Data Model

### User (`accounts.User`)

Custom user model with a `role` field.

| Field | Type | Values |
|---|---|---|
| `username` | CharField | unique |
| `email` | EmailField | unique |
| `role` | CharField | `customer` · `vendor` · `delivery` · `admin` |
| `phone` | CharField | optional |
| `avatar` | ImageField | optional |
| `is_verified` | BooleanField | default False |

### Vendor (`vendors.Vendor`)

One-to-one with User (role=`vendor`).

| Field | Notes |
|---|---|
| `store_name`, `description` | Store identity |
| `logo`, `banner` | Images (upload_to set) |
| `phone`, `email` | Contact |
| `address`, `city`, `state`, `postal_code` | Location text |
| `latitude`, `longitude` | Decimal(9,6) — used for distance calc |
| `status` | `pending` · `approved` · `rejected` · `suspended` |
| `is_open`, `opening_time`, `closing_time` | Hours |
| `min_order_amount`, `delivery_radius_km` | Constraints |
| `average_rating`, `total_ratings`, `is_featured` | Aggregated, read-only |

### DeliveryPartner (`delivery.DeliveryPartner`)

One-to-one with User (role=`delivery`).

| Field | Notes |
|---|---|
| `vehicle_type` | `bicycle` · `motorcycle` · `car` · `van` |
| `vehicle_number`, `license_number` | IDs |
| `is_approved` | Admin controlled |
| `status` | `offline` · `available` · `on_delivery` |
| `current_latitude`, `current_longitude` | Real-time location |
| `total_deliveries`, `total_earnings` | Aggregated |

### Order (`orders.Order`)

```
STATUS flow:
placed → confirmed → preparing → ready → picked_up → on_the_way → delivered
                                        ↘ cancelled (from placed or confirmed)
```

Delivery fee formula: `30 + 5 × distance_km` (Haversine from vendor → delivery address).

### OrderTracking (`orders.OrderTracking`)

One event per status transition. Stores `latitude`/`longitude` for delivery partner location when set.

### Notification (`notifications.Notification`)

| Field | Values |
|---|---|
| `notification_type` | `order` · `delivery` · `promo` · `system` |
| `data` | JSONField — contains `order_id`, `order_number` |

Notifications are created automatically:
- Vendor notified → order placed, order cancelled
- Customer notified → order confirmed/preparing/ready (by vendor), picked_up/on_the_way/delivered (by delivery)

---

## API Reference

Base URL: `http://localhost:8000/api`

All authenticated endpoints require the header:
```
Authorization: Bearer <access_token>
```

---

### Auth — `/api/auth/`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `register/` | Public | Create user account. Body: `username, email, password, role, first_name?, last_name?, phone?` |
| POST | `login/` | Public | Returns `{ user, tokens }`. Body: `username, password` |
| GET | `profile/` | Required | Get current user profile |
| PUT | `profile/` | Required | Update user profile |
| GET | `addresses/` | Required | List user delivery addresses |
| POST | `addresses/` | Required | Create address |
| PUT | `addresses/{id}/` | Required | Update address |
| DELETE | `addresses/{id}/` | Required | Delete address |

**Register response:**
```json
{
  "user": { "id": 1, "username": "...", "role": "customer", ... },
  "tokens": { "access": "...", "refresh": "..." }
}
```

---

### Vendors — `/api/vendors/`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `register/` | Public | Create vendor account + store in one call |
| GET | `list/` | Public | List approved vendors. Query: `search`, `city`, `is_open`, `is_featured` |
| GET | `nearby/` | Public | Vendors within radius. Query: `lat`, `lng`, `radius_km` (default 5) |
| GET | `{id}/` | Public | Vendor detail + products |
| GET | `dashboard/` | Vendor | Stats + recent orders |
| GET | `profile/` | Vendor | Own store profile |
| PATCH | `profile/` | Vendor | Update own store profile |
| GET | `orders/` | Vendor | All orders for this vendor. Query: `status` |
| PATCH | `orders/{id}/status/` | Vendor | Update order status (`confirmed`/`preparing`/`ready`) |
| GET/POST | `{vendor_id}/reviews/` | Mixed | List or create vendor review |
| GET | `products/` | Vendor | List own products |
| POST | `products/` | Vendor | Create product |
| GET/PUT/DELETE | `products/{id}/` | Vendor | Manage own product |

**Vendor registration body (flat — no nested `user` object):**
```json
{
  "username": "store1", "email": "owner@example.com", "password": "pass1234",
  "first_name": "Jane", "last_name": "Doe", "phone": "+1234567890",
  "store_name": "Jane's Kitchen", "description": "...",
  "vendor_email": "store@example.com",
  "address": "123 Main St", "city": "Lagos", "state": "Lagos", "postal_code": "10001",
  "latitude": 6.524379, "longitude": 3.379206
}
```

---

### Products — `/api/products/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `categories/` | Public | Flat list of all categories |
| GET | `list/` | Public | Paginated products. Query: `search`, `category`, `vendor`, `min_price`, `max_price`, `in_stock`, `ordering` |
| GET | `featured/` | Public | Featured products list |
| GET | `{id}/` | Public | Product detail |
| GET/POST | `{product_id}/reviews/` | Mixed | List or create product review |

---

### Cart & Orders — `/api/orders/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `cart/` | Required | Get current cart |
| POST | `cart/add/` | Required | Add item. Body: `product_id, quantity` |
| PATCH | `cart/items/{id}/` | Required | Update item quantity |
| DELETE | `cart/items/{id}/` | Required | Remove item |
| DELETE | `cart/clear/` | Required | Empty cart |
| POST | `create/` | Required | Place order from cart. Body: `delivery_address_id, notes?` |
| GET | `list/` | Required | Customer's orders. Query: `status` |
| GET | `{id}/` | Required | Order detail |
| POST | `{id}/cancel/` | Required | Cancel order (only `placed`/`confirmed`) |
| GET | `{id}/tracking/` | Required | Order tracking timeline |

**Create order response:** Array of orders (one per vendor in cart).

---

### Delivery — `/api/delivery/`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `register/` | Public | Create delivery partner account. Returns `{ user, partner, tokens }` |
| GET | `dashboard/` | Delivery | Stats + active orders |
| GET | `available-orders/` | Delivery | `ready` orders near partner location |
| POST | `accept/{orderId}/` | Delivery | Accept and assign order (status → `picked_up`) |
| PATCH | `update-status/{orderId}/` | Delivery | Update status (`picked_up`/`on_the_way`/`delivered`) |
| POST | `update-location/` | Delivery | Update GPS. Body: `latitude, longitude` |
| GET | `history/` | Delivery | Completed deliveries |
| GET | `earnings/` | Delivery | Earning records |

**Delivery partner registration body:**
```json
{
  "username": "rider1", "email": "rider@example.com", "password": "pass1234",
  "first_name": "John", "last_name": "Doe", "phone": "+1234567890",
  "vehicle_type": "motorcycle",
  "vehicle_number": "ABC-1234",
  "license_number": "DL-567890"
}
```

---

### Notifications — `/api/notifications/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `list/` | Required | All notifications for current user |
| PATCH | `{id}/read/` | Required | Mark single notification as read |
| POST | `mark-all-read/` | Required | Mark all as read |
| GET | `unread-count/` | Required | Returns `{ count: N }` |

---

### Admin — `/api/admin/`

All endpoints require `role=admin`.

| Method | Path | Description |
|---|---|---|
| GET | `stats/` | Platform counts: customers, vendors, delivery_partners, products, orders, orders_placed, orders_delivering, orders_delivered |
| GET | `customers/` | Paginated customers. Query: `search`, `is_verified`, `page` |
| GET/PATCH/DELETE | `customers/{id}/` | Manage single customer |
| GET | `vendors/` | Paginated vendors. Query: `search`, `status`, `page` |
| POST | `vendors/{id}/status/` | Set vendor status. Body: `{ "status": "approved"/"rejected"/"suspended"/"pending" }` |
| GET | `delivery-partners/` | Paginated delivery partners. Query: `search`, `is_approved`, `status`, `page` |
| GET/PATCH | `delivery-partners/{id}/` | Manage single delivery partner |
| POST | `delivery-partners/{id}/approve/` | Approve or reject. Body: `{ "action": "approve"/"reject" }` |

---

## Permissions

| Class | Location | Rule |
|---|---|---|
| `IsAuthenticated` | DRF built-in | Valid JWT required |
| `IsAdminRole` | `accounts/permissions.py` | `request.user.role == 'admin'` |
| `AllowAny` | DRF built-in | No auth required |

---

## Running Locally

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API available at `http://localhost:8000/api/`

Django admin at `http://localhost:8000/admin/`

---

## Environment / Production Notes

Before deploying, change these in `settings.py`:

```python
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
CORS_ALLOWED_ORIGINS = ['https://yourfrontend.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
    }
}
```

Also configure `MEDIA_ROOT` / `MEDIA_URL` and a storage backend (e.g. S3) for image uploads.
