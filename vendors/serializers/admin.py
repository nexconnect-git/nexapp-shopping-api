import uuid
import json
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from accounts.data.user_repository import UserRepository
from helpers.phone_helpers import normalize_phone
from helpers.validators import validate_pan, validate_ifsc, validate_gstin
from vendors.models import Vendor, VendorOnboarding, VendorBankDetails, VendorServiceableArea, VendorHoliday, VendorAuditLog, VENDOR_TYPE_CHOICES
from .public import VendorSerializer

User = get_user_model()

class AdminVendorSerializer(VendorSerializer):
    class Meta(VendorSerializer.Meta):
        read_only_fields = ["id", "average_rating", "total_ratings", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        request = self.context.get('request')
        user_fields = ['username', 'first_name', 'last_name', 'country', 'currency']
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


class JSONListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            if not data.strip():
                data = []
            else:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise serializers.ValidationError("Expected a valid JSON list.") from exc
        return super().to_internal_value(data)


class VendorFullOnboardSerializer(serializers.Serializer):
    # Step 1
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, default="", allow_blank=True)
    last_name = serializers.CharField(required=False, default="", allow_blank=True)
    
    # Step 2
    store_name = serializers.CharField(max_length=200)
    vendor_type = serializers.ChoiceField(
        choices=[choice[0] for choice in VENDOR_TYPE_CHOICES],
        default="retail_store",
    )
    description = serializers.CharField(required=False, default="", allow_blank=True)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    address = serializers.CharField(max_length=255, required=False, default="", allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, default="", allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, default="", allow_blank=True)
    postal_code = serializers.CharField(max_length=10, required=False, default="", allow_blank=True)
    country = serializers.CharField(max_length=2, required=False, default="IN", allow_blank=True)
    latitude = serializers.DecimalField(max_digits=11, decimal_places=8, required=False, default=0)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8, required=False, default=0)
    logo = serializers.ImageField(required=False, allow_null=True)
    banner = serializers.ImageField(required=False, allow_null=True)
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
    business_addresses = JSONListField(child=serializers.DictField(), required=False, default=list)
    
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
    serviceable_pincodes = JSONListField(child=serializers.DictField(), required=False, default=list)
    
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
    holidays = JSONListField(child=serializers.DictField(), required=False, default=list)

    def validate_username(self, value):
        value = value.strip()
        if UserRepository.username_exists(value):
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if UserRepository.email_exists(value):
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value):
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if UserRepository.phone_exists(phone):
            raise serializers.ValidationError("Phone number already exists.")
        return phone

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
                role="vendor",
                country=validated_data.get("country") or "IN",
            )
            if auto_pw:
                user.force_password_change = True
                user.temp_password = auto_pw
                user.save(update_fields=["force_password_change", "temp_password"])

            vendor = Vendor.objects.create(
                user=user,
                store_name=validated_data["store_name"],
                vendor_type=validated_data.get("vendor_type", "retail_store"),
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
                logo=validated_data.get("logo"),
                banner=validated_data.get("banner"),
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
