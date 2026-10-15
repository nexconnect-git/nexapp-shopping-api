from accounts.models.mobile_otp import MobileOTP
from vendors.data.base import BaseRepository


class MobileOTPRepository(BaseRepository):
    def __init__(self):
        super().__init__(MobileOTP)

    @staticmethod
    def recent_requests(phone, email, cutoff):
        return (
            list(MobileOTP.objects.filter(phone=phone, created_at__gte=cutoff).order_by('-created_at').values_list('created_at', flat=True)),
            list(MobileOTP.objects.filter(email=email, created_at__gte=cutoff).order_by('-created_at').values_list('created_at', flat=True)),
        )

    @staticmethod
    def latest_unused(phone, purpose, email=None):
        query = MobileOTP.objects.filter(phone=phone, purpose=purpose, is_used=False)
        if email is not None:
            query = query.filter(email=email)
        return query.order_by('-created_at').first()
