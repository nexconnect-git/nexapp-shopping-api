from files.models import UploadedFile
from orders.models import Order
from orders.models.order_issue import OrderIssueAttachment


class MediaAccessRepository:
    @staticmethod
    def get_uploaded_file(clean_path):
        return UploadedFile.objects.filter(file=clean_path).select_related('uploaded_by').first()

    @staticmethod
    def delivery_partner_has_order_media(user, clean_path) -> bool:
        return (
            Order.objects.filter(delivery_partner=user, delivery_photo=clean_path)
            | Order.objects.filter(delivery_partner=user, transaction_photo=clean_path)
        ).exists()

    @staticmethod
    def delivery_partner_has_issue_attachment(user, clean_path) -> bool:
        return OrderIssueAttachment.objects.filter(
            file=clean_path,
            issue__order__delivery_partner=user,
        ).exists()
