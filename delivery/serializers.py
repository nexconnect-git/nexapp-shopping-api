from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DeliveryPartner, DeliveryReview, DeliveryEarning, Asset, DeliveryAssignment

User = get_user_model()


class DeliveryPartnerSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryPartner
        fields = ['id', 'user', 'vehicle_type', 'vehicle_number', 'license_number',
                  'id_proof', 'is_approved', 'is_available', 'status',
                  'current_latitude', 'current_longitude', 'average_rating',
                  'total_deliveries', 'total_earnings', 'wallet_balance',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'is_approved', 'average_rating', 'total_deliveries',
                            'total_earnings', 'wallet_balance', 'created_at', 'updated_at']

    def get_user(self, obj):
        data = {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'phone': obj.user.phone,
            'force_password_change': obj.user.force_password_change,
        }
        if obj.user.force_password_change and obj.user.temp_password:
            data['temp_password'] = obj.user.temp_password
        return data


class DeliveryPartnerRegistrationSerializer(serializers.Serializer):
    # User fields
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, default='')
    last_name = serializers.CharField(required=False, default='')
    phone = serializers.CharField(max_length=15, required=False, default='')
    # Delivery partner fields
    vehicle_type = serializers.ChoiceField(choices=DeliveryPartner.VEHICLE_CHOICES)
    vehicle_number = serializers.CharField(max_length=20, required=False, default='')
    license_number = serializers.CharField(max_length=50)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.get('password')
        auto_generated_password = None
        if not password:
            auto_generated_password = User.objects.make_random_password()
            password = auto_generated_password

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role='delivery',
        )
        if auto_generated_password:
            user.force_password_change = True
            user.save(update_fields=['force_password_change'])

        partner = DeliveryPartner.objects.create(
            user=user,
            vehicle_type=validated_data['vehicle_type'],
            vehicle_number=validated_data.get('vehicle_number', ''),
            license_number=validated_data['license_number'],
        )
        if auto_generated_password:
            partner.auto_generated_password = auto_generated_password
        return partner


class DeliveryReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)

    class Meta:
        model = DeliveryReview
        fields = ['id', 'delivery_partner', 'customer', 'customer_name', 'order',
                  'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'customer', 'created_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class DeliveryEarningSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = DeliveryEarning
        fields = ['id', 'delivery_partner', 'order', 'order_number', 'amount',
                  'created_at']
        read_only_fields = ['id', 'created_at']


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    vendor_name = serializers.CharField(source='order.vendor.store_name', read_only=True)
    vendor_lat = serializers.DecimalField(
        source='order.vendor.latitude', max_digits=9, decimal_places=6, read_only=True
    )
    vendor_lng = serializers.DecimalField(
        source='order.vendor.longitude', max_digits=9, decimal_places=6, read_only=True
    )
    vendor_address = serializers.CharField(source='order.vendor.address', read_only=True)
    order_total = serializers.DecimalField(
        source='order.total', max_digits=10, decimal_places=2, read_only=True
    )
    order_items = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryAssignment
        fields = [
            'id', 'status', 'current_radius_km',
            'order', 'order_number', 'vendor_name', 'vendor_lat', 'vendor_lng',
            'vendor_address', 'order_total', 'order_items',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_order_items(self, obj):
        return [
            {
                'name': item.product_name,
                'quantity': item.quantity,
                'price': str(item.product_price),
            }
            for item in obj.order.items.all()
        ]


class UpdateLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class AssetSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ['id', 'name', 'asset_type', 'serial_number', 'description',
                  'status', 'assigned_to', 'assigned_to_name', 'purchase_date',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.user.get_full_name() or obj.assigned_to.user.username
        return None
