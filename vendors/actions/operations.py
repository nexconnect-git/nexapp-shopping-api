from vendors.actions.base import BaseAction
from vendors.data.operations_repository import VendorOperationsRepository


class VendorOperationsSummaryAction(BaseAction):
    def execute(self, vendor):
        return VendorOperationsRepository().summary(vendor)


class VendorLiveOrdersAction(BaseAction):
    def execute(self, vendor):
        return VendorOperationsRepository().live_orders(vendor)
