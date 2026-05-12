from datetime import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils import timezone

from helpers.validators import validate_document_upload
from helpers.vendor_hours import get_vendor_availability


class VendorHoursTests(SimpleTestCase):
    class Vendor:
        is_open = True
        is_accepting_orders = True

        def __init__(self, opening_time, closing_time):
            self.opening_time = opening_time
            self.closing_time = closing_time

    def test_accepts_string_times(self):
        vendor = self.Vendor("09:00:00", "23:00:00")
        current_dt = timezone.datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)

        is_open, message = get_vendor_availability(vendor, current_dt=current_dt)

        self.assertTrue(is_open)
        self.assertEqual(message, "Open now until 23:00")

    def test_accepts_time_objects(self):
        vendor = self.Vendor(time(9, 0), time(23, 0))
        current_dt = timezone.datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)

        is_open, _message = get_vendor_availability(vendor, current_dt=current_dt)

        self.assertTrue(is_open)


class UploadValidatorTests(SimpleTestCase):
    def test_rejects_disallowed_document_extension(self):
        upload = SimpleUploadedFile(
            "payload.exe",
            b"not a document",
            content_type="application/octet-stream",
        )

        with self.assertRaises(ValueError):
            validate_document_upload(upload)
