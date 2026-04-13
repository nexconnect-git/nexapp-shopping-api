from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from products.serializers.review_serializers import ProductReviewSerializer
from products.data.review_repository import ProductReviewRepository
from products.actions.reviews import AddReviewAction, UpdateReviewAction

class ProductReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProductReviewRepository.filter(product_id=self.kwargs.get("product_id"))

    def create(self, request, *args, **kwargs):
        action = AddReviewAction()
        try:
            review = action.execute(
                product_id=self.kwargs.get("product_id"),
                customer=request.user,
                rating=int(request.data.get("rating", 0)),
                comment=request.data.get("comment", "")
            )
            return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        action = UpdateReviewAction()
        try:
            review = action.execute(
                review_id=kwargs.get("pk"),
                customer=request.user,
                rating=int(request.data.get("rating")) if "rating" in request.data else None,
                comment=request.data.get("comment")
            )
            return Response(self.get_serializer(review).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
