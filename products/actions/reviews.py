from .base import BaseAction
from products.models import ProductReview, Product
from django.db import transaction

class AddReviewAction(BaseAction):
    def execute(self, product_id: str, customer, rating: int, comment: str = "") -> ProductReview:
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5.")
        
        product = Product.objects.get(pk=product_id)
        if ProductReview.objects.filter(product=product, customer=customer).exists():
            raise ValueError("You have already reviewed this product.")

        with transaction.atomic():
            review = ProductReview.objects.create(
                product=product,
                customer=customer,
                rating=rating,
                comment=comment
            )
            # Update product aggregates via signal or manually here
            # In NexConnect, signals usually handle it. 
        return review

class UpdateReviewAction(BaseAction):
    def execute(self, review_id: str, customer, rating: int = None, comment: str = None) -> ProductReview:
        review = ProductReview.objects.get(pk=review_id, customer=customer)
        if rating is not None:
            if not (1 <= rating <= 5):
                raise ValueError("Rating must be between 1 and 5.")
            review.rating = rating
        if comment is not None:
            review.comment = comment
        review.save(update_fields=["rating", "comment", "updated_at"] if rating is not None or comment is not None else ["updated_at"])
        return review
