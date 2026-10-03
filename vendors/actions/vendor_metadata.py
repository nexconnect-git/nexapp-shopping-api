from rest_framework import serializers
from django.utils.dateparse import parse_date

from vendors.data.vendor_metadata_repository import VendorMetadataRepository, ONBOARD_FIELDS, BANK_FIELDS
from vendors.serializers.onboarding import VendorOnboardingSerializer, VendorBankDetailsSerializer


class UpdateVendorMetadataAction:
    def execute(self, vendor, data):
        repository = VendorMetadataRepository()
        groups = []
        for fields, schema, operation in ((ONBOARD_FIELDS, VendorOnboardingSerializer, repository.save_onboarding), (BANK_FIELDS, VendorBankDetailsSerializer, repository.save_bank)):
            values = {key: data[key] for key in fields if key in data}
            if not values:
                continue
            validator = schema(data=values, partial=True)
            validator.is_valid(raise_exception=True)
            addresses = validator.validated_data.get('business_addresses')
            if addresses is not None and (not isinstance(addresses, list) or len(addresses) > 50 or any(not isinstance(row, dict) for row in addresses)):
                raise serializers.ValidationError({'business_addresses': 'Provide a list of at most 50 address objects.'})
            groups.append((operation, dict(validator.validated_data)))
        collections = {}
        for name in ('serviceable_pincodes', 'holidays'):
            if name not in data:
                continue
            rows = data[name]
            if not isinstance(rows, list) or len(rows) > 500:
                raise serializers.ValidationError({name: 'Provide a list of at most 500 records.'})
            seen, clean = set(), []
            for row in rows:
                if not isinstance(row, dict):
                    raise serializers.ValidationError({name: 'Each record must be an object.'})
                if name == 'serviceable_pincodes':
                    code = str(row.get('pincode', '')).strip()
                    if not code.isdigit() or not 4 <= len(code) <= 10 or len(str(row.get('city', ''))) > 100 or len(str(row.get('state', ''))) > 100 or not isinstance(row.get('is_active', True), bool):
                        raise serializers.ValidationError({name: 'Use a valid pincode, city, state and boolean is_active.'})
                    value = {'pincode': code, 'city': str(row.get('city', '')), 'state': str(row.get('state', '')), 'is_active': row.get('is_active', True)}
                    key = code
                else:
                    try:
                        day = parse_date(row.get('date', ''))
                    except (ValueError, TypeError):
                        day = None
                    reason = row.get('reason', '')
                    if not day or not isinstance(reason, str) or len(reason) > 200:
                        raise serializers.ValidationError({name: 'Use a valid date (YYYY-MM-DD) and reason of at most 200 characters.'})
                    value, key = {'date': day, 'reason': reason}, day
                if key in seen:
                    raise serializers.ValidationError({name: 'Duplicate records are not allowed.'})
                seen.add(key)
                clean.append(value)
            collections[name] = clean
        for operation, values in groups:
            operation(vendor, values)
        for name, rows in collections.items():
            repository.replace_collection(vendor, name, rows)
