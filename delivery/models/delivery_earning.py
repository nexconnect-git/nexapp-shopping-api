import uuid
from django.db import models
from delivery.models.delivery_partner import DeliveryPartner


class DeliveryEarning(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_partner = models.ForeignKey(DeliveryPartner, on_delete=models.CASCADE, related_name='earnings')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'delivery'

    def __str__(self):
        return f"{self.delivery_partner.user.username} earned {self.amount}"
