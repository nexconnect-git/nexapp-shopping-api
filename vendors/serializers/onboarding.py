from rest_framework import serializers
from helpers.validators import validate_pan, validate_gstin, validate_ifsc
from vendors.models import (
    VendorOnboarding, VendorBankDetails, VendorDocument,
    VendorServiceableArea, VendorHoliday
)

class VendorOnboardingSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VendorOnboarding
        fields = [
            "id", "vendor", "legal_name", "vendor_type",
            "contact_person_name", "contact_person_email", "contact_person_phone",
            "gst_registered", "pan_number", "gstin", "cin_udyam",
            "fssai_license", "trademark_number", "business_addresses",
            "kyc_status", "onboarding_status", "rejection_reason",
            "submitted_at", "reviewed_at", "reviewed_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "vendor", "kyc_status", "onboarding_status", "rejection_reason",
            "submitted_at", "reviewed_at", "reviewed_by_name",
            "created_at", "updated_at",
        ]

    def get_reviewed_by_name(self, obj) -> str | None:
        if obj.reviewed_by:
            return (f"{obj.reviewed_by.first_name} {obj.reviewed_by.last_name}".strip() or obj.reviewed_by.username)
        return None

    def validate_pan_number(self, value: str) -> str:
        if value and not validate_pan(value):
            raise serializers.ValidationError("Invalid PAN format. Expected: AAAAA9999A")
        return value.upper() if value else value

    def validate_gstin(self, value: str) -> str:
        if value and not validate_gstin(value):
            raise serializers.ValidationError("Invalid GSTIN format.")
        return value.upper() if value else value


class VendorBankDetailsSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    masked_account = serializers.CharField(source="masked_account_number", read_only=True)

    class Meta:
        model = VendorBankDetails
        fields = [
            "id", "vendor",
            "account_holder_name", "account_number", "masked_account",
            "ifsc_code", "bank_name", "branch_name", "account_type",
            "upi_id", "settlement_cycle", "commission_percentage",
            "is_verified", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "vendor", "masked_account", "is_verified", "created_at", "updated_at"]

    def validate_ifsc_code(self, value: str) -> str:
        if value and not validate_ifsc(value):
            raise serializers.ValidationError("Invalid IFSC code.")
        return value.upper() if value else value

    def update(self, instance, validated_data):
        account_number = validated_data.pop("account_number", None)
        if account_number:
            instance.set_account_number(account_number)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        account_number = validated_data.pop("account_number", None)
        instance = super().create(validated_data)
        if account_number:
            instance.set_account_number(account_number)
            instance.save(update_fields=["account_number_enc"])
        return instance


class VendorDocumentSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.SerializerMethodField(read_only=True)
    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = VendorDocument
        fields = [
            "id", "vendor", "document_type", "document_type_label",
            "file", "original_filename", "file_size_bytes",
            "status", "rejection_reason",
            "verified_by_name", "verified_at", "uploaded_at",
        ]
        read_only_fields = [
            "id", "original_filename", "file_size_bytes", "status",
            "rejection_reason", "verified_by_name", "verified_at", "uploaded_at",
        ]

    def get_verified_by_name(self, obj) -> str | None:
        if obj.verified_by:
            return (f"{obj.verified_by.first_name} {obj.reviewed_by.last_name}".strip() or obj.verified_by.username)
        return None

    def create(self, validated_data):
        file_obj = validated_data.get("file")
        if file_obj:
            validated_data["original_filename"] = file_obj.name
            validated_data["file_size_bytes"] = file_obj.size
        return super().create(validated_data)


class DocumentVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["verify", "reject"])
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["action"] == "reject" and not attrs.get("rejection_reason", "").strip():
            raise serializers.ValidationError({"rejection_reason": "Required."})
        return attrs


class VendorServiceableAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorServiceableArea
        fields = ["id", "vendor", "pincode", "city", "state", "is_active"]
        read_only_fields = ["id", "vendor"]


class VendorHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorHoliday
        fields = ["id", "vendor", "date", "reason"]
        read_only_fields = ["id", "vendor"]
