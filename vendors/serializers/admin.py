import uuid
import json
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from accounts.data.user_repository import UserRepository
from helpers.phone_helpers import normalize_phone
from helpers.validators import validate_document_upload, validate_pan, validate_ifsc, validate_gstin
from vendors.models import (
    Vendor,
    VendorAuditLog,
    VendorBankDetails,
    VendorDocument,
    VendorHoliday,
    VendorOnboarding,
    VendorServiceableArea,
    VENDOR_TYPE_CHOICES,
)
from vendors.serializers.onboarding import VendorDocumentSerializer
from vendors.serializers.public import VendorSerializer

User = get_user_model()

VENDOR_ONBOARD_DOCUMENT_FIELDS = {
    "license_document": "license",
    "pan_card_document": "pan_card",
    "gstin_certificate_document": "gstin_certificate",
    "identity_proof_document": "identity_proof",
    "address_proof_document": "address_proof",
    "cancelled_cheque_document": "cancelled_cheque",
    "fssai_license_document": "fssai_license",
    "business_registration_document": "business_registration",
    "trademark_document": "trademark",
}

class AdminVendorSerializer(VendorSerializer):
    documents = serializers.SerializerMethodField(read_only=True)
    license_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    pan_card_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    gstin_certificate_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    identity_proof_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    address_proof_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    cancelled_cheque_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    fssai_license_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    business_registration_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    trademark_document = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta(VendorSerializer.Meta):
        fields = VendorSerializer.Meta.fields + ["documents"] + list(VENDOR_ONBOARD_DOCUMENT_FIELDS.keys())
        read_only_fields = [
            "id", "status", "status_reason", "average_rating", "total_ratings",
            "created_at", "updated_at",
        ]

    def get_documents(self, obj):
        documents = obj.documents.all().order_by("-uploaded_at")
        return VendorDocumentSerializer(documents, many=True, context=self.context).data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field_name in VENDOR_ONBOARD_DOCUMENT_FIELDS:
            file_obj = attrs.get(field_name)
            if not file_obj:
                continue
            label = field_name.replace("_", " ").replace("document", "file").strip()
            try:
                validate_document_upload(file_obj, label=label)
            except ValueError as exc:
                raise serializers.ValidationError({field_name: str(exc)}) from exc
        return attrs

    def update(self, instance, validated_data):
        document_uploads = {
            document_type: validated_data.pop(field_name, None)
            for field_name, document_type in VENDOR_ONBOARD_DOCUMENT_FIELDS.items()
        }
        request = self.context.get('request')
        user_fields = ['username', 'first_name', 'last_name', 'country', 'currency']
        if request:
            user_updated = []
            if 'username' in request.data:
                username = str(request.data['username']).strip()
                if UserRepository.username_exists(username, exclude_user_id=instance.user_id):
                    raise serializers.ValidationError({'username': 'Username already exists.'})
            if 'email' in request.data:
                email = str(request.data['email']).strip().lower()
                if UserRepository.email_exists(email, exclude_user_id=instance.user_id, role='vendor'):
                    raise serializers.ValidationError({'email': 'Email already exists for a vendor account.'})
            if 'phone' in request.data:
                try:
                    phone = normalize_phone(str(request.data['phone']))
                except ValueError as exc:
                    raise serializers.ValidationError({'phone': str(exc)}) from exc
                if UserRepository.phone_exists(phone, exclude_user_id=instance.user_id, role='vendor'):
                    raise serializers.ValidationError({'phone': 'Phone number already exists for a vendor account.'})
            for field in user_fields:
                if field in request.data:
                    setattr(instance.user, field, request.data[field])
                    user_updated.append(field)
            if 'email' in request.data:
                instance.user.email = request.data['email']
                user_updated.append('email')
            if 'phone' in request.data:
                instance.user.phone = normalize_phone(str(request.data['phone']))
                user_updated.append('phone')
            if user_updated:
                instance.user.save(update_fields=list(set(user_updated)))
        vendor = super().update(instance, validated_data)
        uploaded_documents = []
        for document_type, file_obj in document_uploads.items():
            if not file_obj:
                continue
            uploaded_documents.append(
                VendorDocument.objects.create(
                    vendor=vendor,
                    document_type=document_type,
                    file=file_obj,
                    original_filename=file_obj.name,
                    file_size_bytes=file_obj.size,
                )
            )
        if uploaded_documents:
            VendorAuditLog.objects.create(
                vendor=vendor,
                action="document_uploaded",
                description="Vendor documents uploaded by admin during profile edit.",
                performed_by=request.user if request else None,
            )
        return vendor


class JSONListField(serializers.ListField):
    def to_internal_value(self, data):
        if (
            isinstance(data, list)
            and len(data) == 1
            and isinstance(data[0], str)
        ):
            data = data[0]
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
    license_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    pan_card_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    gstin_certificate_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    identity_proof_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    address_proof_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    cancelled_cheque_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    fssai_license_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    business_registration_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    trademark_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    
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
        if UserRepository.email_exists(value, role="vendor"):
            raise serializers.ValidationError("Email already exists for a vendor account.")
        return value

    def validate_phone(self, value):
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if UserRepository.phone_exists(phone, role="vendor"):
            raise serializers.ValidationError("Phone number already exists for a vendor account.")
        return phone

    def validate(self, attrs):
        for field_name in VENDOR_ONBOARD_DOCUMENT_FIELDS:
            file_obj = attrs.get(field_name)
            if not file_obj:
                continue
            label = field_name.replace("_", " ").replace("document", "file").strip()
            try:
                validate_document_upload(file_obj, label=label)
            except ValueError as exc:
                raise serializers.ValidationError({field_name: str(exc)}) from exc
        return attrs

    def create(self, validated_data):
        document_uploads = {
            document_type: validated_data.pop(field_name, None)
            for field_name, document_type in VENDOR_ONBOARD_DOCUMENT_FIELDS.items()
        }
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
                vendor_type=validated_data.get("vendor_type", "retail_store"),
                contact_person_name=validated_data.get("contact_person_name", ""),
                contact_person_email=validated_data.get("contact_person_email", ""),
                contact_person_phone=validated_data.get("contact_person_phone", ""),
                gst_registered=validated_data.get("gst_registered", False),
                pan_number=validated_data.get("pan_number", "").upper(),
                gstin=validated_data.get("gstin", "").upper(),
                cin_udyam=validated_data.get("cin_udyam", "").upper(),
                fssai_license=validated_data.get("fssai_license", ""),
                trademark_number=validated_data.get("trademark_number", "").upper(),
                business_addresses=validated_data.get("business_addresses", []),
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
            for document_type, file_obj in document_uploads.items():
                if not file_obj:
                    continue
                VendorDocument.objects.create(
                    vendor=vendor,
                    document_type=document_type,
                    file=file_obj,
                    original_filename=file_obj.name,
                    file_size_bytes=file_obj.size,
                )
            if any(document_uploads.values()):
                VendorAuditLog.objects.create(
                    vendor=vendor,
                    action="document_uploaded",
                    description="Vendor onboarding documents uploaded by admin.",
                    performed_by=self.context.get("request").user if self.context.get("request") else None
                )

        if auto_pw:
            vendor.auto_generated_password = auto_pw
        return vendor
