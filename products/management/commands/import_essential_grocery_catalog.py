import mimetypes
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.models import CatalogProduct, CatalogProductImage, Category, VendorCatalogGrant
from vendors.models import Vendor


ESSENTIAL_GROCERY_TERMS = [
    ("Rice", "Pantry Staples", "kg"),
    ("Wheat flour", "Pantry Staples", "kg"),
    ("Pasta", "Pantry Staples", "pack"),
    ("Oats", "Pantry Staples", "pack"),
    ("Bread", "Bakery", "piece"),
    ("Milk", "Dairy", "litre"),
    ("Yogurt", "Dairy", "cup"),
    ("Butter", "Dairy", "pack"),
    ("Eggs", "Protein", "dozen"),
    ("Chicken breast", "Protein", "kg"),
    ("Lentils", "Protein", "kg"),
    ("Chickpeas", "Protein", "can"),
    ("Apples", "Fruits", "kg"),
    ("Bananas", "Fruits", "dozen"),
    ("Oranges", "Fruits", "kg"),
    ("Potatoes", "Vegetables", "kg"),
    ("Onions", "Vegetables", "kg"),
    ("Tomatoes", "Vegetables", "kg"),
    ("Carrots", "Vegetables", "kg"),
    ("Spinach", "Vegetables", "bunch"),
    ("Cooking oil", "Pantry Staples", "litre"),
    ("Sugar", "Pantry Staples", "kg"),
    ("Salt", "Pantry Staples", "pack"),
    ("Tea", "Beverages", "pack"),
]


class Command(BaseCommand):
    help = "Import essential household grocery catalog products from Open Food Facts."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=len(ESSENTIAL_GROCERY_TERMS))
        parser.add_argument("--grant-approved-vendors", action="store_true")
        parser.add_argument("--no-images", action="store_true")

    def handle(self, *args, **options):
        limit = min(options["limit"], len(ESSENTIAL_GROCERY_TERMS))
        created = 0
        updated = 0
        image_count = 0
        grant_count = 0

        for name, category_name, fallback_unit in ESSENTIAL_GROCERY_TERMS[:limit]:
            scraped = self.fetch_open_food_facts_item(name)
            category = self.get_or_create_category(category_name)
            catalog_product, was_created = self.upsert_catalog_product(
                name=name,
                category=category,
                fallback_unit=fallback_unit,
                scraped=scraped,
            )
            if was_created:
                created += 1
            else:
                updated += 1

            if not options["no_images"] and scraped.get("image_url"):
                if self.attach_image(catalog_product, scraped["image_url"]):
                    image_count += 1

            if options["grant_approved_vendors"]:
                for vendor in Vendor.objects.filter(status="approved"):
                    _, grant_created = VendorCatalogGrant.objects.get_or_create(
                        vendor=vendor,
                        catalog_product=catalog_product,
                    )
                    if grant_created:
                        grant_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Catalog import complete: {created} created, {updated} updated, "
            f"{image_count} images attached, {grant_count} grants created."
        ))

    def fetch_open_food_facts_item(self, term):
        params = urlencode({
            "search_terms": term,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 5,
            "fields": "product_name,brands,categories_tags,image_front_url,image_url,quantity,code",
        })
        url = f"https://world.openfoodfacts.org/cgi/search.pl?{params}"
        request = Request(url, headers={"User-Agent": "NexConnectCatalogImporter/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                import json
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Open Food Facts lookup failed for {term}: {exc}"))
            return self.fetch_wikimedia_image(term)

        for product in data.get("products", []):
            product_name = (product.get("product_name") or "").strip()
            image_url = product.get("image_front_url") or product.get("image_url")
            if product_name and image_url:
                return {
                    "name": product_name,
                    "brand": (product.get("brands") or "").split(",")[0].strip(),
                    "image_url": image_url,
                    "barcode": product.get("code") or "",
                    "quantity": product.get("quantity") or "",
                }
        return self.fetch_wikimedia_image(term)

    def fetch_wikimedia_image(self, term):
        params = urlencode({
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"file:{term} food",
            "gsrnamespace": 6,
            "gsrlimit": 1,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 800,
        })
        url = f"https://commons.wikimedia.org/w/api.php?{params}"
        request = Request(url, headers={"User-Agent": "NexConnectCatalogImporter/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                import json
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Wikimedia lookup failed for {term}: {exc}"))
            return {}

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            image_info = (page.get("imageinfo") or [{}])[0]
            image_url = image_info.get("thumburl") or image_info.get("url")
            if image_url:
                return {
                    "name": term,
                    "brand": "",
                    "image_url": image_url,
                    "barcode": "",
                    "quantity": "",
                }
        return {}

    def get_or_create_category(self, category_name):
        slug = slugify(category_name)
        category, _ = Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name": category_name,
                "description": f"Essential household {category_name.lower()} items.",
                "is_active": True,
                "show_in_customer_ui": True,
            },
        )
        return category

    def upsert_catalog_product(self, name, category, fallback_unit, scraped):
        display_name = scraped.get("name") or name
        base_slug = slugify(name)
        catalog_product, created = CatalogProduct.objects.get_or_create(
            slug=base_slug,
            defaults={
                "name": display_name[:200],
                "category": category,
                "description": self.description_for(name, scraped),
                "brand": scraped.get("brand", "")[:120],
                "unit": fallback_unit,
                "barcode": scraped.get("barcode", "")[:100],
                "search_keywords": f"{name}, grocery, household essentials",
                "compliance_notes": "Imported from Open Food Facts public read API where available.",
                "is_active": True,
            },
        )
        if not created:
            catalog_product.category = category
            catalog_product.name = display_name[:200]
            catalog_product.description = self.description_for(name, scraped)
            catalog_product.brand = scraped.get("brand", "")[:120]
            catalog_product.unit = fallback_unit
            if scraped.get("barcode"):
                catalog_product.barcode = scraped["barcode"][:100]
            catalog_product.search_keywords = f"{name}, grocery, household essentials"
            catalog_product.compliance_notes = "Imported from Open Food Facts public read API where available."
            catalog_product.is_active = True
            catalog_product.save()
        return catalog_product, created

    def description_for(self, name, scraped):
        parts = [f"Essential household grocery item: {name}."]
        if scraped.get("quantity"):
            parts.append(f"Sample scraped package quantity: {scraped['quantity']}.")
        parts.append("Vendor controls price, stock, availability, and store-specific handling details.")
        return " ".join(parts)

    def attach_image(self, catalog_product, image_url):
        if catalog_product.images.exists():
            return False
        request = Request(image_url, headers={"User-Agent": "NexConnectCatalogImporter/1.0"})
        try:
            with urlopen(request, timeout=25) as response:
                content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
                data = response.read()
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Image download failed for {catalog_product.name}: {exc}"))
            return False

        extension = mimetypes.guess_extension(content_type) or ".jpg"
        filename = f"{slugify(catalog_product.name)}{extension}"
        image = CatalogProductImage(catalog_product=catalog_product, is_primary=True)
        image.image.save(filename, ContentFile(data), save=True)
        return True
