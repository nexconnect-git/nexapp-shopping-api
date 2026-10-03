from django.db.models import Avg, Count, Q

from support.models import SupportTicket
from vendors.data.base import BaseRepository
from vendors.models import VendorReview


class VendorFeedbackRepository(BaseRepository):
    def __init__(self):
        super().__init__(VendorReview)

    def reviews(self, vendor, params):
        query = self.filter(vendor=vendor).select_related('customer')
        if params.get('filter') == 'low':
            query = query.filter(rating__lte=3)
        if params.get('rating') in ('1', '2', '3', '4', '5'):
            query = query.filter(rating=int(params['rating']))
        return query.order_by('-created_at', 'id')

    def summary(self, vendor):
        query = self.filter(vendor=vendor)
        result = query.aggregate(average=Avg('rating'), total=Count('id'))
        result['average'] = result['average'] or 0
        result['distribution'] = {str(row['rating']): row['count'] for row in query.values('rating').annotate(count=Count('id'))}
        return result

    def tickets(self, vendor, params):
        query = SupportTicket.objects.filter(vendor=vendor)
        for field in ('status', 'category', 'priority'):
            if params.get(field):
                query = query.filter(**{field: params[field]})
        if params.get('search'):
            term = params['search']
            query = query.filter(Q(subject__icontains=term) | Q(message__icontains=term))
        return query.order_by('-created_at', 'id')
