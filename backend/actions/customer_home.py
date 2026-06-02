from orders.views import BannerListView
from products.data.category_repository import CategoryRepository
from products.data.product_repository import ProductRepository
from products.serializers import CategorySerializer, ProductListSerializer
from vendors.views import VendorListView


class GetCustomerHomeAction:
    def execute(self, request) -> dict:
        categories = CategoryRepository.get_customer_visible()
        stores_response = VendorListView()._get_uncached(request)
        stores = stores_response.data
        if isinstance(stores, dict):
            stores = stores.get("results", [])

        products = (
            ProductRepository.get_all(
                select_related=["vendor", "category", "catalog_product"],
                prefetch_related=["images", "catalog_product__images"],
            )
            .filter(category__is_active=True, category__show_in_customer_ui=True)
            .order_by("-is_featured", "-total_orders", "name")[:16]
        )
        banners = BannerListView().get(request).data

        return {
            "categories": CategorySerializer(categories[:12], many=True, context={"request": request}).data,
            "nearby_stores": stores[:12] if isinstance(stores, list) else [],
            "recommended_products": ProductListSerializer(products, many=True, context={"request": request}).data,
            "banners": banners,
        }
