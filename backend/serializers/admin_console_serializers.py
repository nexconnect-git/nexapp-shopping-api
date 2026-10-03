import base64
import binascii
import re

from rest_framework import serializers

from orders.models import Order, OrderIssue, PlatformSetting


class AdminOrderFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)
    vendor = serializers.UUIDField(required=False)
    customer = serializers.UUIDField(required=False)
    delivery_partner = serializers.UUIDField(required=False)
    order = serializers.UUIDField(required=False)
    method = serializers.ChoiceField(choices=['cod', 'razorpay', ''], required=False)
    verified = serializers.ChoiceField(choices=['0', '1', ''], required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    amount_min = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    amount_max = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    issue_state = serializers.ChoiceField(choices=['open', ''], required=False)
    delivery_state = serializers.ChoiceField(choices=['unassigned', 'in_transit', ''], required=False)
    ordering = serializers.ChoiceField(choices=['placed_at', '-placed_at', 'total', '-total', 'status', '-status', 'order_number', '-order_number'], required=False)

    def validate(self, data):
        for low, high in [('date_from', 'date_to'), ('amount_min', 'amount_max')]:
            if low in data and high in data and data[low] > data[high]:
                raise serializers.ValidationError({high: 'Must be greater than or equal to the minimum.'})
        return data


class AdminIssueFilterSerializer(AdminOrderFilterSerializer):
    status = serializers.ChoiceField(choices=OrderIssue.STATUS_CHOICES, required=False)
    issue_type = serializers.ChoiceField(choices=OrderIssue.ISSUE_TYPE_CHOICES, required=False)
    assignee = serializers.UUIDField(required=False)
    queue = serializers.CharField(max_length=60, required=False)
    priority = serializers.ChoiceField(choices=['normal', 'high', 'urgent'], required=False)
    due = serializers.ChoiceField(choices=['overdue', 'upcoming'], required=False)


class AdminPageFeatureConfigSerializer(serializers.Serializer):
    applications = serializers.ListField(child=serializers.DictField(), required=False, max_length=4)
    global_settings = serializers.DictField(required=False)
    is_enabled = serializers.BooleanField(required=False)

    def validate_applications(self, value):
        apps, pages = set(), set()
        for app in value:
            key = app.get('id')
            if key not in ('vendor-app', 'delivery-app', 'customer-app', 'mobile-customer') or key in apps:
                raise serializers.ValidationError('Application IDs must be supported and unique.')
            apps.add(key)
            if not isinstance(app.get('pages'), list) or len(app['pages']) > 200:
                raise serializers.ValidationError('Applications require a page list of at most 200 records.')
            for page in app['pages']:
                if not isinstance(page, dict) or not isinstance(page.get('id'), str) or not 1 <= len(page['id']) <= 120 or page['id'] in pages or page.get('appId') != key:
                    raise serializers.ValidationError('Page IDs must be unique and match their application.')
                pages.add(page['id'])
                route = page.get('route', '')
                if not isinstance(route, str) or not route.startswith('/') or route.startswith('//') or any(char in route for char in ('?', '#', '\\')):
                    raise serializers.ValidationError('Page routes must be application paths.')
                if page.get('status') not in ('enabled', 'disabled', 'partial'):
                    raise serializers.ValidationError('Unknown page status.')
                if not isinstance(page.get('features', []), list) or len(page.get('features', [])) > 50:
                    raise serializers.ValidationError('Features must be a list.')
                features = set()
                for feature in page.get('features', []):
                    if not isinstance(feature, dict) or not isinstance(feature.get('id'), str) or not 1 <= len(feature['id']) <= 120 or feature['id'] in features or feature.get('status') not in ('enabled', 'disabled'):
                        raise serializers.ValidationError('Feature IDs and states must be valid and unique.')
                    features.add(feature['id'])
        return value

    def validate_global_settings(self, value):
        allowed={'requireAuthentication','maintenanceMode','enabledByDefault','pageDisabledAlerts','featureAccessRequests','bulkActionAlerts'}
        if set(value)-allowed or any(type(item) is not bool for item in value.values()):
            raise serializers.ValidationError('Global settings must contain supported boolean values.')
        if value.get('requireAuthentication') is False:
            raise serializers.ValidationError('Authentication requirements are enforced by application guards and cannot be disabled here.')
        return value


class SupportCaseUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderIssue.STATUS_CHOICES, required=False)
    assignee = serializers.UUIDField(required=False, allow_null=True)
    queue = serializers.CharField(max_length=60, required=False)
    priority = serializers.ChoiceField(choices=['normal', 'high', 'urgent'], required=False)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    resolution_type = serializers.ChoiceField(choices=['', 'refund', 'replacement', 'compensation', 'explanation'], required=False)
    admin_notes = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    refund_method = serializers.ChoiceField(choices=['', 'wallet', 'razorpay', 'manual'], required=False, allow_blank=True)


class AdminPlatformSettingsSerializer(serializers.ModelSerializer):
    enabled_payment_methods = serializers.ListField(child=serializers.ChoiceField(choices=PlatformSetting.DEFAULT_PAYMENT_METHODS), min_length=1)
    cancellation_allowed_statuses = serializers.ListField(child=serializers.ChoiceField(choices=['placed', 'confirmed', 'preparing', 'ready']))

    class Meta:
        model = PlatformSetting
        fields = ['upi_id', 'cod_payment_qr', 'enabled_payment_methods', 'delivery_base_fee', 'delivery_per_km_fee', 'free_delivery_above', 'platform_fee', 'packaging_fee', 'small_cart_threshold', 'small_cart_fee', 'tax_percentage', 'surge_fee', 'cancellation_window_minutes', 'cancellation_allowed_statuses']
        extra_kwargs = {key: {'min_value': 0} for key in ['delivery_base_fee', 'delivery_per_km_fee', 'free_delivery_above', 'platform_fee', 'packaging_fee', 'small_cart_threshold', 'small_cart_fee', 'surge_fee', 'cancellation_window_minutes']}
        extra_kwargs['tax_percentage'] = {'min_value': 0, 'max_value': 100}

    def validate_enabled_payment_methods(self, value):
        return list(dict.fromkeys(value))

    def validate_upi_id(self, value):
        if value and not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+', value):
            raise serializers.ValidationError('Enter a valid UPI ID.')
        return value

    def validate_cod_payment_qr(self, value):
        if not value:
            return value
        if not value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')):
            raise serializers.ValidationError('Upload a PNG, JPEG or WebP image.')
        try:
            content = base64.b64decode(value.split(',', 1)[1], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise serializers.ValidationError('The image encoding is invalid.') from exc
        if len(content) > 3 * 1024 * 1024:
            raise serializers.ValidationError('QR images must be smaller than 3 MB.')
        if not (content.startswith(b'\x89PNG\r\n\x1a\n') or content.startswith(b'\xff\xd8\xff') or (content.startswith(b'RIFF') and content[8:12] == b'WEBP')):
            raise serializers.ValidationError('The file is not a supported image.')
        return value
