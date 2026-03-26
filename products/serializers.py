from rest_framework import serializers
from django.utils.text import slugify
from .models import Category, Product, ProductImage, ProductReview
from vendors.serializers import VendorListSerializer


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    subcategory_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'parent',
                  'parent_name', 'is_active', 'display_order', 'children',
                  'subcategory_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else None

    def get_subcategory_count(self, obj):
        return obj.children.count()


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary', 'is_ai_generated', 'display_order']
        read_only_fields = ['id']

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None



class ProductReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)

    class Meta:
        model = ProductReview
        fields = ['id', 'product', 'customer', 'customer_name', 'rating', 'comment',
                  'created_at']
        read_only_fields = ['id', 'customer', 'created_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    vendor = VendorListSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'vendor', 'category', 'name', 'slug', 'description',
                  'price', 'compare_price', 'sku', 'stock', 'unit', 'weight',
                  'is_available', 'is_featured', 'average_rating', 'total_ratings',
                  'total_orders', 'discount_percentage', 'in_stock', 'images',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'average_rating', 'total_ratings', 'total_orders',
                            'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    vendor_name = serializers.CharField(source='vendor.store_name', read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'price', 'compare_price', 'unit',
                  'is_available', 'is_featured', 'average_rating', 'total_ratings',
                  'discount_percentage', 'in_stock', 'primary_image', 'vendor_name']

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'category', 'name', 'slug', 'description', 'price',
                  'compare_price', 'sku', 'stock', 'unit', 'weight',
                  'is_available', 'is_featured', 'images']
        read_only_fields = ['id']
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def _unique_slug(self, base, instance=None):
        slug = slugify(base)
        qs = Product.objects.all()
        if instance:
            qs = qs.exclude(pk=instance.pk)
        candidate, n = slug, 1
        while qs.filter(slug=candidate).exists():
            candidate = f'{slug}-{n}'
            n += 1
        return candidate

    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user.vendor_profile
        if not validated_data.get('slug'):
            validated_data['slug'] = self._unique_slug(validated_data['name'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = self._unique_slug(
                validated_data.get('name', instance.name), instance
            )
        return super().update(instance, validated_data)
