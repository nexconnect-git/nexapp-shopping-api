from rest_framework.exceptions import ValidationError
from vendors.actions.base import BaseAction
from vendors.data.analytics_repository import VendorAnalyticsRepository


class VendorAnalyticsAction(BaseAction):
    def execute(self, vendor, days="30"):
        if str(days) not in {"7", "30", "90", "all"}:
            raise ValidationError({"days": "Choose 7, 30, 90, or all."})
        return VendorAnalyticsRepository().summary(vendor, str(days))
