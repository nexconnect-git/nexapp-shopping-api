import os
import django
import urllib.request
from django.core.files.base import ContentFile
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from vendors.models import Vendor
from products.models import Category, Product, ProductImage

User = get_user_model()

# --- Dummy Image Helper ---
def download_image(url, filename):
    print(f"Downloading image from {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 200:
                return ContentFile(response.read(), name=filename)
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return None

def clear_db():
    print("Clearing old data...")
    ProductImage.objects.all().delete()
    Product.objects.all().delete()
    Category.objects.all().delete()
    Vendor.objects.all().delete()
    User.objects.filter(role='vendor').delete()

def seed_db():
    clear_db()

    categories_data = [
        {"name": "Food", "slug": "food", "icon": "restaurant"},
        {"name": "Groceries", "slug": "groceries", "icon": "local_grocery_store"},
        {"name": "Pharmacy", "slug": "pharmacy", "icon": "local_pharmacy"},
        {"name": "Electronics", "slug": "electronics", "icon": "devices"},
        {"name": "Fashion", "slug": "fashion", "icon": "checkroom"},
    ]

    cats = {}
    for c_data in categories_data:
        cat = Category.objects.create(
            name=c_data["name"],
            slug=c_data["slug"],
            description=f"Fresh and handpicked {c_data['name'].lower()}",
            is_active=True
        )
        cats[c_data["slug"]] = cat
        print(f"Created category: {cat.name}")

    vendors_data = [
        {
            "store_name": "The Spice Garden",
            "cat_slug": "food",
            "desc": "Authentic local food and multi-cuisine restaurant.",
            "banner": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&q=80",
            "products": [
                {"name": "Grilled Chicken Wrap", "price": "12.99", "img": "https://images.unsplash.com/photo-1626804475297-41609ea004eb?w=600&q=80"},
                {"name": "Spicy Veg Noodles", "price": "8.50", "img": "https://images.unsplash.com/photo-1612927601601-6638404737ce?w=600&q=80"},
                {"name": "Butter Chicken Bowl", "price": "14.99", "img": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=600&q=80"},
            ]
        },
        {
            "store_name": "Fresh Market Daily",
            "cat_slug": "groceries",
            "desc": "Your daily destination for fresh organic groceries.",
            "banner": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=600&q=80",
            "products": [
                {"name": "Organic Fruit Basket", "price": "24.00", "img": "https://images.unsplash.com/photo-1610832958506-aa56368176cf?w=600&q=80"},
                {"name": "Whole Wheat Bread", "price": "4.50", "img": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&q=80"},
                {"name": "Fresh Farm Milk 1L", "price": "2.99", "img": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=600&q=80"},
            ]
        },
        {
            "store_name": "City Core Pharmacy",
            "cat_slug": "pharmacy",
            "desc": "Fast local pharmacy with everyday essentials.",
            "banner": "https://images.unsplash.com/photo-1585435557343-3b092031a831?w=600&q=80",
            "products": [
                {"name": "Vitamin C 1000mg", "price": "15.00", "img": "https://images.unsplash.com/photo-1584308666744-24d5e1dc7fb6?w=600&q=80"},
                {"name": "First Aid Kit", "price": "29.99", "img": "https://images.unsplash.com/photo-1603398938378-e54eab446dde?w=600&q=80"},
                {"name": "Protein Powder", "price": "45.00", "img": "https://images.unsplash.com/photo-1579722820308-d74e571900a9?w=600&q=80"},
            ]
        },
        {
            "store_name": "Tech Haven Electronics",
            "cat_slug": "electronics",
            "desc": "Latest gadgets, laptops, and premium accessories.",
            "banner": "https://images.unsplash.com/photo-1491933382434-500287f9b54b?w=600&q=80",
            "products": [
                {"name": "Sony WH-1000XM5 Headphones", "price": "348.00", "img": "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?w=600&q=80"},
                {"name": "Mechanical Gaming Keyboard", "price": "89.99", "img": "https://images.unsplash.com/photo-1595225476474-87563907a212?w=600&q=80"},
                {"name": "4K Ultra HD Monitor", "price": "299.00", "img": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600&q=80"},
            ]
        },
        {
            "store_name": "Vogue Fashion Boutique",
            "cat_slug": "fashion",
            "desc": "Trendy and modern fashion apparel for everyone.",
            "banner": "https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?w=600&q=80",
            "products": [
                {"name": "Classic Denim Jacket", "price": "65.00", "img": "https://images.unsplash.com/photo-1576871337622-98d48d1cf531?w=600&q=80"},
                {"name": "Cotton White T-Shirt", "price": "19.99", "img": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80"},
                {"name": "Leather Chelsea Boots", "price": "120.00", "img": "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?w=600&q=80"},
            ]
        }
    ]

    for i, v_data in enumerate(vendors_data):
        # Create user
        user = User.objects.create_user(
            username=f'vendor{i}',
            email=f'vendor{i}@test.com',
            password='password123',
            role='vendor',
            first_name='Vendor',
            last_name=str(i)
        )
        
        # Create vendor
        vendor = Vendor.objects.create(
            user=user,
            store_name=v_data["store_name"],
            description=v_data["desc"],
            phone="1234567890",
            email=f'vendor{i}@test.com',
            address="123 Market St",
            city="Metropolis",
            state="NY",
            postal_code="10001",
            status="approved",
            is_open=True,
            is_featured=True,
            average_rating=4.5,
            total_ratings=120
        )

        banner_file = download_image(v_data["banner"], f"banner_{i}.jpg")
        if banner_file:
            vendor.banner.save(f"banner_{i}.jpg", banner_file)

        print(f"Created vendor: {vendor.store_name}")

        category = cats[v_data["cat_slug"]]

        # Create products
        for j, p_data in enumerate(v_data["products"]):
            prod = Product.objects.create(
                vendor=vendor,
                category=category,
                name=p_data["name"],
                slug=f"{category.slug}-p{i}-{j}",
                description=f"High quality {p_data['name']}",
                price=Decimal(p_data["price"]),
                stock=50,
                is_available=True,
                is_featured=True,
                average_rating=4.8,
                total_ratings=45
            )

            p_img_file = download_image(p_data["img"], f"prod_{i}_{j}.jpg")
            if p_img_file:
                ProductImage.objects.create(
                    product=prod,
                    is_primary=True,
                    image=p_img_file
                )
            print(f"  -> Added product: {prod.name}")

    print("Database successfully seeded with Vendors, Categories, and Products!")

if __name__ == '__main__':
    seed_db()
