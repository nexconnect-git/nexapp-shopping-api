import uuid
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from helpers.validators import validate_pan, validate_ifsc, validate_gstin
from vendors.models import Vendor, VendorOnboarding, VendorBankDetails, VendorServiceableArea, VendorHoliday, VendorAuditLog
from .public import VendorSerializer

User = get_user_model()

class AdminVendorSerializer(VendorSerializer):
    class Meta(VendorSerializer.Meta):
        read_only_fields = ["id", "average_rating", "total_ratings", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        request = self.context.get('request')
        user_fields = ['username', 'first_name', 'last_name']
        if request:
            user_updated = []
            for field in user_fields:
                if field in request.data:
                    setattr(instance.user, field, request.data[field])
                    user_updated.append(field)
            if 'email' in request.data:
                instance.user.email = request.data['email']
                user_updated.append('email')
            if 'phone' in request.data:
                instance.user.phone = request.data['phone']
                user_updated.append('phone')
            if user_updated:
                instance.user.save(update_fields=list(set(user_updated)))
        return super().update(instance, validated_data)

class VendorFullOnboardSerializer(serializers.Serializer):
    # Step 1
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, default="", allow_blank=True)
    last_name = serializers.CharField(required=False, default="", allow_blank=True)
    
    # Step 2
    store_name = serializers.CharField(max_length=200)
    vendor_type = serializers.ChoiceField(choices=["individual", "company", "partnership"], default="individual")
    description = serializers.CharField(required=False, default="", allow_blank=True)
    phone = serializers.CharField(max_length=15)
    email = serializers.EmailField()
    address = serializers.CharField(max_length=255, required=False, default="", allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, default="", allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, default="", allow_blank=True)
    postal_code = serializers.CharField(max_length=10, required=False, default="", allow_blank=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, default=0)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, default=0)
    gst_registered = serializers.BooleanField(default=False)
    
    # Step 3
    legal_name = serializers.CharField(required=False, default="", allow_blank=True)
    contact_person_name = serializers.CharField(required=False, default="", allow_blank=True)
    contact_person_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_person_phone = serializers.CharField(required=False, default="", allow_blank=True)
    pan_number = serializers.CharField(max_length=10, required=False, default="", allow_blank=True)
    gstin = serializers.CharField(max_length=15, required=False, default="", allow_blank=True)
    cin_udyam = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)
    fssai_license = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)
    trademark_number = serializers.CharField(max_length=50, required=False, default="", allow_blank=True)
    business_addresses = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    
    # Step 4
    account_holder_name = serializers.CharField(required=False, default="", allow_blank=True)
    account_number = serializers.CharField(required=False, default="", allow_blank=True)
    ifsc_code = serializers.CharField(max_length=11, required=False, default="", allow_blank=True)
    bank_name = serializers.CharField(required=False, default="", allow_blank=True)
    branch_name = serializers.CharField(required=False, default="", allow_blank=True)
    account_type = serializers.ChoiceField(choices=["savings", "current"], default="current", required=False)
    upi_id = serializers.CharField(required=False, default="", allow_blank=True)
    settlement_cycle = serializers.ChoiceField(choices=["T+1", "T+7", "T+15", "T+30"], default="T+7", required=False)
    commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, required=False)
    
    # Step 5
    fulfillment_type = serializers.ChoiceField(choices=["vendor", "platform"], default="vendor", required=False)
    dispatch_sla_hours = serializers.IntegerField(default=24, required=False)
    return_policy = serializers.CharField(required=False, default="", allow_blank=True)
    packaging_preferences = serializers.CharField(required=False, default="", allow_blank=True)
    serviceable_pincodes = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    
    # Step 6
    opening_time = serializers.TimeField(default="09:00", required=False)
    closing_time = serializers.TimeField(default="22:00", required=False)
    min_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    delivery_radius_km = serializers.DecimalField(max_digits=5, decimal_places=2, default=5.0, required=False)
    auto_order_acceptance = serializers.BooleanField(default=False, required=False)
    cancellation_rules = serializers.CharField(required=False, default="", allow_blank=True)
    vendor_tier = serializers.ChoiceField(choices=["basic", "silver", "gold", "platinum"], default="basic", required=False)
    is_open = serializers.BooleanField(default=True, required=False)
    is_featured = serializers.BooleanField(default=False, required=False)
    holidays = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email exists.")
        return value

    def create(self, validated_data):
        password = validated_data.get("password")
        auto_pw = None
        if not password:
            auto_pw = User.objects.make_random_password()
            password = auto_pw

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=password,
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                phone=validated_data.get("phone", ""),
                role="vendor"
            )
            if auto_pw:
                user.force_password_change = True
                user.temp_password = auto_pw
                user.save(update_fields=["force_password_change", "temp_password"])

            vendor = Vendor.objects.create(
                user=user,
                store_name=validated_data["store_name"],
                vendor_type=validated_data.get("vendor_type", "individual"),
                vendor_tier=validated_data.get("vendor_tier", "basic"),
                description=validated_data.get("description", ""),
                phone=validated_data.get("phone", ""),
                email=validated_data["email"],
                address=validated_data.get("address", ""),
                city=validated_data.get("city", ""),
                state=validated_data.get("state", ""),
                postal_code=validated_data.get("postal_code", ""),
                latitude=validated_data.get("latitude", 0),
                longitude=validated_data.get("longitude", 0),
                is_open=validated_data.get("is_open", True),
                opening_time=validated_data.get("opening_time", "09:00"),
                closing_time=validated_data.get("closing_time", "22:00"),
                min_order_amount=validated_data.get("min_order_amount", 0),
                delivery_radius_km=validated_data.get("delivery_radius_km", 5.0),
                fulfillment_type=validated_data.get("fulfillment_type", "vendor"),
                dispatch_sla_hours=validated_data.get("dispatch_sla_hours", 24),
                status="pending",
            )
            VendorOnboarding.objects.create(
                vendor=vendor,
                legal_name=validated_data.get("legal_name", "") or validated_data["store_name"],
                onboarding_status="submitted",
                submitted_at=timezone.now()
            )
            bank = VendorBankDetails(
                vendor=vendor,
                ifsc_code=validated_data.get("ifsc_code", "").upper(),
                account_type=validated_data.get("account_type", "current")
            )
            if validated_data.get("account_number"):
                bank.set_account_number(validated_data["account_number"])
            bank.save()

            VendorAuditLog.objects.create(
                vendor=vendor,
                action="created",
                description="Vendor onboarded via admin.",
                performed_by=self.context.get("request").user if self.context.get("request") else None
            )

        if auto_pw:
            vendor.auto_generated_password = auto_pw
        return vendor
