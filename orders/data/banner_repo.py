"""Repository for PlatformBanner ORM queries."""

from orders.models import PlatformBanner


class PlatformBannerRepository:
    @staticmethod
    def get_active():
        return PlatformBanner.objects.filter(is_active=True)

    @staticmethod
    def get_all():
        return PlatformBanner.objects.all()

    @staticmethod
    def get_by_id(pk) -> PlatformBanner | None:
        try:
            return PlatformBanner.objects.get(pk=pk)
        except PlatformBanner.DoesNotExist:
            return None
