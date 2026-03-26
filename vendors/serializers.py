from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Vendor, VendorReview,
    VendorOnboarding, VendorBankDetails,
    VendorDocument, VendorServiceableArea,
    VendorHoliday, VendorAuditLog,
    VendorPayout, DeliveryPartnerPayout,
)
from .utils import validate_pan, validate_gstin, validate_ifsc

User = get_user_model()


# ── Vendor ────────────────────────────────────────────────────────────────────

class VendorSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'id', 'user_info', 'store_name', 'description', 'logo', 'banner',
            'phone', 'email', 'address', 'city', 'state', 'postal_code',
            'latitude', 'longitude',
            'vendor_type', 'vendor_tier',
            'status', 'is_open', 'opening_time', 'closing_time',
            'min_order_amount', 'delivery_radius_km',
            'fulfillment_type', 'dispatch_sla_hours', 'return_policy',
            'packaging_preferences', 'auto_order_acceptance', 'cancellation_rules',
            'average_rating', 'total_ratings', 'is_featured',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'average_rating', 'total_ratings',
            'is_featured', 'created_at', 'updated_at',
        ]

    def get_user_info(self, obj):
        data = {
            'id':                   str(obj.user.id),
            'username':             obj.user.username,
            'email':                obj.user.email,
            'first_name':           obj.user.first_name,
            'last_name':            obj.user.last_name,
            'phone':                obj.user.phone,
            'force_password_change': obj.user.force_password_change,
        }
        if obj.user.force_password_change and obj.user.temp_password:
            data['temp_password'] = obj.user.temp_password
        return data


class AdminVendorSerializer(VendorSerializer):
    class Meta(VendorSerializer.Meta):
        read_only_fields = ['id', 'average_rating', 'total_ratings', 'created_at', 'updated_at']


class VendorListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            'id', 'store_name', 'logo', 'city', 'state', 'is_open',
            'average_rating', 'total_ratings', 'delivery_radius_km',
            'min_order_amount', 'is_featured', 'vendor_type', 'vendor_tier',
        ]


# ── VendorOnboarding ──────────────────────────────────────────────────────────

class VendorOnboardingSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VendorOnboarding
        fields = [
            'id', 'vendor', 'legal_name', 'vendor_type',
            'contact_person_name', 'contact_person_email', 'contact_person_phone',
            'gst_registered', 'pan_number', 'gstin', 'cin_udyam',
            'fssai_license', 'trademark_number', 'business_addresses',
            'kyc_status', 'onboarding_status', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'reviewed_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'vendor', 'kyc_status', 'onboarding_status', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'reviewed_by_name',
            'created_at', 'updated_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return (f'{obj.reviewed_by.first_name} {obj.reviewed_by.last_name}'.strip()
                    or obj.reviewed_by.username)
        return None

    def validate_pan_number(self, value):
        if value and not validate_pan(value):
            raise serializers.ValidationError('Invalid PAN format. Expected: AAAAA9999A')
        return value.upper() if value else value

    def validate_gstin(self, value):
        if value and not validate_gstin(value):
            raise serializers.ValidationError('Invalid GSTIN format. Expected 15-character GST number.')
        return value.upper() if value else value


# ── VendorBankDetails ─────────────────────────────────────────────────────────

class VendorBankDetailsSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    masked_account = serializers.CharField(source='masked_account_number', read_only=True)

    class Meta:
        model = VendorBankDetails
        fields = [
            'id', 'vendor',
            'account_holder_name', 'account_number', 'masked_account',
            'ifsc_code', 'bank_name', 'branch_name', 'account_type',
            'upi_id', 'settlement_cycle', 'commission_percentage',
            'is_verified', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'vendor', 'masked_account', 'is_verified', 'created_at', 'updated_at']

    def validate_ifsc_code(self, value):
        if value and not validate_ifsc(value):
            raise serializers.ValidationError('Invalid IFSC code. Format: AAAA0NNNNNN')
        return value.upper() if value else value

    def update(self, instance, validated_data):
        account_number = validated_data.pop('account_number', None)
        if account_number:
            instance.set_account_number(account_number)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        account_number = validated_data.pop('account_number', None)
        instance = super().create(validated_data)
        if account_number:
            instance.set_account_number(account_number)
            instance.save(update_fields=['account_number_enc'])
        return instance


# ── VendorDocument ────────────────────────────────────────────────────────────

class VendorDocumentSerializer(serializers.ModelSerializer):
    verified_by_name    = serializers.SerializerMethodField(read_only=True)
    document_type_label = serializers.CharField(source='get_document_type_display', read_only=True)

    class Meta:
        model = VendorDocument
        fields = [
            'id', 'vendor', 'document_type', 'document_type_label',
            'file', 'original_filename', 'file_size_bytes',
            'status', 'rejection_reason',
            'verified_by_name', 'verified_at', 'uploaded_at',
        ]
        read_only_fields = [
            'id', 'original_filename', 'file_size_bytes', 'status',
            'rejection_reason', 'verified_by_name', 'verified_at', 'uploaded_at',
        ]

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return (f'{obj.verified_by.first_name} {obj.verified_by.last_name}'.strip()
                    or obj.verified_by.username)
        return None

    def create(self, validated_data):
        file_obj = validated_data.get('file')
        if file_obj:
            validated_data['original_filename'] = file_obj.name
            validated_data['file_size_bytes']   = file_obj.size
        return super().create(validated_data)


class DocumentVerifySerializer(serializers.Serializer):
    action           = serializers.ChoiceField(choices=['verify', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('rejection_reason', '').strip():
            raise serializers.ValidationError({'rejection_reason': 'Required when rejecting a document.'})
        return attrs


# ── VendorServiceableArea ─────────────────────────────────────────────────────

class VendorServiceableAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorServiceableArea
        fields = ['id', 'vendor', 'pincode', 'city', 'state', 'is_active']
        read_only_fields = ['id', 'vendor']


# ── VendorHoliday ─────────────────────────────────────────────────────────────

class VendorHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorHoliday
        fields = ['id', 'vendor', 'date', 'reason']
        read_only_fields = ['id', 'vendor']


# ── VendorAuditLog ────────────────────────────────────────────────────────────

class VendorAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField(read_only=True)
    action_label      = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = VendorAuditLog
        fields = [
            'id', 'action', 'action_label', 'description',
            'performed_by_name', 'ip_address', 'metadata', 'created_at',
        ]

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return (f'{obj.performed_by.first_name} {obj.performed_by.last_name}'.strip()
                    or obj.performed_by.username)
        return 'System'


# ── Full Onboarding (admin single-request create) ─────────────────────────────

class VendorFullOnboardSerializer(serializers.Serializer):
    """
    Admin creates a vendor with full onboarding data in one request.
    Sections mirror the 6-step frontend wizard.
    """
    # Step 1 — credentials
    username   = serializers.CharField()
    password   = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, default='', allow_blank=True)
    last_name  = serializers.CharField(required=False, default='', allow_blank=True)

    # Step 2 — basic details
    store_name     = serializers.CharField(max_length=200)
    vendor_type    = serializers.ChoiceField(choices=['individual', 'company', 'partnership'], default='individual')
    description    = serializers.CharField(required=False, default='', allow_blank=True)
    phone          = serializers.CharField(max_length=15)
    email          = serializers.EmailField()
    address        = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)
    city           = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    state          = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    postal_code    = serializers.CharField(max_length=10,  required=False, default='', allow_blank=True)
    latitude       = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, default=0)
    longitude      = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, default=0)
    gst_registered = serializers.BooleanField(default=False)

    # Step 3 — legal & compliance
    legal_name           = serializers.CharField(required=False, default='', allow_blank=True)
    contact_person_name  = serializers.CharField(required=False, default='', allow_blank=True)
    contact_person_email = serializers.EmailField(required=False, allow_blank=True, default='')
    contact_person_phone = serializers.CharField(required=False, default='', allow_blank=True)
    pan_number           = serializers.CharField(max_length=10, required=False, default='', allow_blank=True)
    gstin                = serializers.CharField(max_length=15, required=False, default='', allow_blank=True)
    cin_udyam            = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    fssai_license        = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    trademark_number     = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    business_addresses   = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    # Step 4 — bank & payment
    account_holder_name   = serializers.CharField(required=False, default='', allow_blank=True)
    account_number        = serializers.CharField(required=False, default='', allow_blank=True)
    ifsc_code             = serializers.CharField(max_length=11, required=False, default='', allow_blank=True)
    bank_name             = serializers.CharField(required=False, default='', allow_blank=True)
    branch_name           = serializers.CharField(required=False, default='', allow_blank=True)
    account_type          = serializers.ChoiceField(choices=['savings', 'current'], default='current', required=False)
    upi_id                = serializers.CharField(required=False, default='', allow_blank=True)
    settlement_cycle      = serializers.ChoiceField(choices=['T+1', 'T+7', 'T+15', 'T+30'], default='T+7', required=False)
    commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, required=False)

    # Step 5 — logistics
    fulfillment_type      = serializers.ChoiceField(choices=['vendor', 'platform'], default='vendor', required=False)
    dispatch_sla_hours    = serializers.IntegerField(default=24, required=False)
    return_policy         = serializers.CharField(required=False, default='', allow_blank=True)
    packaging_preferences = serializers.CharField(required=False, default='', allow_blank=True)
    serviceable_pincodes  = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    # Step 6 — operational
    opening_time          = serializers.TimeField(default='09:00', required=False)
    closing_time          = serializers.TimeField(default='22:00', required=False)
    min_order_amount      = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    delivery_radius_km    = serializers.DecimalField(max_digits=5,  decimal_places=2, default=5.0, required=False)
    auto_order_acceptance = serializers.BooleanField(default=False, required=False)
    cancellation_rules    = serializers.CharField(required=False, default='', allow_blank=True)
    vendor_tier           = serializers.ChoiceField(choices=['basic', 'silver', 'gold', 'platinum'], default='basic', required=False)
    is_open               = serializers.BooleanField(default=True, required=False)
    is_featured           = serializers.BooleanField(default=False, required=False)
    holidays              = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_pan_number(self, value):
        if value and not validate_pan(value):
            raise serializers.ValidationError('Invalid PAN format. Expected: AAAAA9999A')
        return value.upper() if value else value

    def validate_gstin(self, value):
        if value and not validate_gstin(value):
            raise serializers.ValidationError('Invalid GSTIN format. Expected 15-character GST number.')
        return value.upper() if value else value

    def validate_ifsc_code(self, value):
        if value and not validate_ifsc(value):
            raise serializers.ValidationError('Invalid IFSC code. Format: AAAA0NNNNNN')
        return value.upper() if value else value

    def create(self, validated_data):
        from django.db import transaction
        
        password = validated_data.get('password')
        auto_generated_password = None
        if not password:
            auto_generated_password = User.objects.make_random_password()
            password = auto_generated_password

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=password,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                phone=validated_data.get('phone', ''),
                role='vendor',
            )
            if auto_generated_password:
                user.force_password_change = True
                user.temp_password = auto_generated_password
                user.save(update_fields=['force_password_change', 'temp_password'])

            vendor = Vendor.objects.create(
                user=user,
                store_name=validated_data['store_name'],
                vendor_type=validated_data.get('vendor_type', 'individual'),
                vendor_tier=validated_data.get('vendor_tier', 'basic'),
                description=validated_data.get('description', ''),
                phone=validated_data.get('phone', ''),
                email=validated_data['email'],
                address=validated_data.get('address', ''),
                city=validated_data.get('city', ''),
                state=validated_data.get('state', ''),
                postal_code=validated_data.get('postal_code', ''),
                latitude=validated_data.get('latitude', 0),
                longitude=validated_data.get('longitude', 0),
                is_open=validated_data.get('is_open', True),
                opening_time=validated_data.get('opening_time', '09:00'),
                closing_time=validated_data.get('closing_time', '22:00'),
                min_order_amount=validated_data.get('min_order_amount', 0),
                delivery_radius_km=validated_data.get('delivery_radius_km', 5.0),
                fulfillment_type=validated_data.get('fulfillment_type', 'vendor'),
                dispatch_sla_hours=validated_data.get('dispatch_sla_hours', 24),
                return_policy=validated_data.get('return_policy', ''),
                packaging_preferences=validated_data.get('packaging_preferences', ''),
                auto_order_acceptance=validated_data.get('auto_order_acceptance', False),
                cancellation_rules=validated_data.get('cancellation_rules', ''),
                is_featured=validated_data.get('is_featured', False),
                status='pending',
            )

            VendorOnboarding.objects.create(
                vendor=vendor,
                legal_name=validated_data.get('legal_name', '') or validated_data['store_name'],
                vendor_type=validated_data.get('vendor_type', 'individual'),
                contact_person_name=validated_data.get('contact_person_name', ''),
                contact_person_email=validated_data.get('contact_person_email', ''),
                contact_person_phone=validated_data.get('contact_person_phone', ''),
                gst_registered=validated_data.get('gst_registered', False),
                pan_number=validated_data.get('pan_number', ''),
                gstin=validated_data.get('gstin', ''),
                cin_udyam=validated_data.get('cin_udyam', ''),
                fssai_license=validated_data.get('fssai_license', ''),
                trademark_number=validated_data.get('trademark_number', ''),
                business_addresses=validated_data.get('business_addresses', []),
                onboarding_status='submitted',
                submitted_at=timezone.now(),
            )

            bank = VendorBankDetails(
                vendor=vendor,
                account_holder_name=validated_data.get('account_holder_name', ''),
                ifsc_code=validated_data.get('ifsc_code', '').upper(),
                bank_name=validated_data.get('bank_name', ''),
                branch_name=validated_data.get('branch_name', ''),
                account_type=validated_data.get('account_type', 'current'),
                upi_id=validated_data.get('upi_id', ''),
                settlement_cycle=validated_data.get('settlement_cycle', 'T+7'),
                commission_percentage=validated_data.get('commission_percentage', 0),
            )
            acct = validated_data.get('account_number', '')
            if acct:
                bank.set_account_number(acct)
            bank.save()

            for area in validated_data.get('serviceable_pincodes', []):
                if area.get('pincode'):
                    VendorServiceableArea.objects.get_or_create(
                        vendor=vendor, pincode=area['pincode'],
                        defaults={'city': area.get('city', ''), 'state': area.get('state', '')},
                    )

            for holiday in validated_data.get('holidays', []):
                if holiday.get('date'):
                    VendorHoliday.objects.get_or_create(
                        vendor=vendor, date=holiday['date'],
                        defaults={'reason': holiday.get('reason', '')},
                    )

            VendorAuditLog.objects.create(
                vendor=vendor,
                action='created',
                description=f'Vendor "{vendor.store_name}" onboarded via admin panel.',
                performed_by=self.context['request'].user if self.context.get('request') else None,
            )

        if auto_generated_password:
            vendor.auto_generated_password = auto_generated_password

        return vendor


# ── Vendor self-registration (public) ────────────────────────────────────────

class VendorRegistrationSerializer(serializers.Serializer):
    username    = serializers.CharField()
    email       = serializers.EmailField()
    password    = serializers.CharField(write_only=True, min_length=8)
    first_name  = serializers.CharField(required=False, default='')
    last_name   = serializers.CharField(required=False, default='')
    store_name  = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, default='')
    phone       = serializers.CharField(max_length=15)
    vendor_email= serializers.EmailField()
    address     = serializers.CharField(max_length=255)
    city        = serializers.CharField(max_length=100)
    state       = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=10)
    latitude    = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude   = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role='vendor',
        )
        return Vendor.objects.create(
            user=user,
            store_name=validated_data['store_name'],
            description=validated_data.get('description', ''),
            phone=validated_data['phone'],
            email=validated_data['vendor_email'],
            address=validated_data['address'],
            city=validated_data['city'],
            state=validated_data['state'],
            postal_code=validated_data['postal_code'],
            latitude=validated_data['latitude'],
            longitude=validated_data['longitude'],
        )


class VendorReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)

    class Meta:
        model = VendorReview
        fields = ['id', 'vendor', 'customer', 'customer_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'customer', 'created_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


# ── Payouts ───────────────────────────────────────────────────────────────────

class VendorPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorPayout
        fields = '__all__'

class DeliveryPartnerPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPartnerPayout
        fields = '__all__'
