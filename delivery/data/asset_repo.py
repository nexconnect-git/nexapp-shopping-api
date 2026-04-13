from django.db.models import QuerySet
from delivery.models import Asset


class AssetRepository:
    """Repository for Asset database operations."""

    @staticmethod
    def get_by_id(pk: str, select_related: list = None) -> Asset:
        qs = Asset.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        return qs.get(pk=pk)

    @staticmethod
    def get_all(asset_type: str = None, status: str = None, assigned_to: str = None) -> QuerySet[Asset]:
        qs = Asset.objects.select_related("assigned_to__user").order_by("-created_at")
        if asset_type:
            qs = qs.filter(asset_type=asset_type)
        if status:
            qs = qs.filter(status=status)
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        return qs
