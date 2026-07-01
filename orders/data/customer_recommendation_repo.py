from orders.models import CustomerRecommendationSnapshot


class CustomerRecommendationRepository:
    """Persistence for precomputed customer recommendations."""

    @staticmethod
    def get_for_user(user):
        if not user or not getattr(user, 'is_authenticated', False):
            return None
        return CustomerRecommendationSnapshot.objects.filter(user=user).first()

    @staticmethod
    def upsert_for_user(user, *, recommended_product_ids, flash_deal_product_ids, recommended_store_ids, metadata=None):
        snapshot, _created = CustomerRecommendationSnapshot.objects.update_or_create(
            user=user,
            defaults={
                'recommended_product_ids': recommended_product_ids,
                'flash_deal_product_ids': flash_deal_product_ids,
                'recommended_store_ids': recommended_store_ids,
                'metadata': metadata or {},
            },
        )
        return snapshot
