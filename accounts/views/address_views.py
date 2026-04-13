"""Address views — CRUD for the authenticated user's delivery addresses."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.models.address import Address
from accounts.serializers.address_serializers import AddressSerializer


class AddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing the current user's delivery addresses."""

    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return addresses belonging to the authenticated user."""
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Attach the current user to the new address on save."""
        serializer.save(user=self.request.user)
