from vendors.data.base import BaseRepository
from vendors.models import Vendor, VendorBankDetails, VendorOnboarding, VendorServiceableArea, VendorHoliday


ONBOARD_FIELDS = ('legal_name', 'contact_person_name', 'contact_person_email', 'contact_person_phone', 'gst_registered', 'pan_number', 'gstin', 'cin_udyam', 'fssai_license', 'trademark_number', 'business_addresses')
BANK_FIELDS = ('account_holder_name', 'account_number', 'ifsc_code', 'bank_name', 'branch_name', 'account_type', 'upi_id', 'settlement_cycle', 'commission_percentage')


class VendorMetadataRepository(BaseRepository):
    def __init__(self):
        super().__init__(Vendor)

    def details(self, vendor):
        onboarding = VendorOnboarding.objects.filter(vendor=vendor).first()
        bank = VendorBankDetails.objects.filter(vendor=vendor).first()
        return onboarding, bank

    def locked(self, vendor_id):
        return Vendor.objects.select_for_update().select_related('user').filter(pk=vendor_id).first()

    def collections(self, vendor):
        return {
            'serviceable_pincodes': list(VendorServiceableArea.objects.filter(vendor=vendor).values('pincode', 'city', 'state', 'is_active')),
            'holidays': [{'date': row['date'].isoformat(), 'reason': row['reason']} for row in VendorHoliday.objects.filter(vendor=vendor).values('date', 'reason')],
        }

    def save_onboarding(self, vendor, values):
        return VendorOnboarding.objects.update_or_create(vendor=vendor, defaults=values)[0]

    def save_bank(self, vendor, values):
        bank, _ = VendorBankDetails.objects.get_or_create(vendor=vendor)
        account = values.pop('account_number', None)
        changed = bool(account) or any(getattr(bank, key) != value for key, value in values.items() if key in ('ifsc_code', 'account_holder_name', 'bank_name', 'upi_id'))
        for key, value in values.items():
            setattr(bank, key, value)
        if account:
            bank.set_account_number(account)
        if changed:
            bank.is_verified = False
        bank.save()

    def replace_collection(self, vendor, name, values):
        model = VendorServiceableArea if name == 'serviceable_pincodes' else VendorHoliday
        model.objects.filter(vendor=vendor).delete()
        model.objects.bulk_create([model(vendor=vendor, **value) for value in values])
