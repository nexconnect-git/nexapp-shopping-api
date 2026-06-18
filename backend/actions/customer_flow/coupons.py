from decimal import Decimal

from backend.data import CustomerFlowRepository
from orders.data.cart_repo import CartRepository
from orders.serializers.coupon_serializers import CouponSerializer


class GetCustomerBestCouponAction:
    repository = CustomerFlowRepository

    def execute(self, request) -> dict:
        cart, _ = CartRepository.get_or_create_cart(request.user)
        subtotal = cart.total_amount
        best = None
        best_discount = Decimal('0.00')
        for coupon in self.repository.active_coupons(subtotal=subtotal):
            discount = coupon.calculate_discount(subtotal)
            if coupon.discount_type == 'free_delivery':
                discount = Decimal('0.00')
            if discount > best_discount:
                best = coupon
                best_discount = discount
        if not best:
            return {'best_coupon': None, 'discount': '0.00', 'message': 'No eligible coupon for this basket.'}
        return {
            'best_coupon': CouponSerializer(best).data,
            'discount': str(best_discount.quantize(Decimal('0.01'))),
            'message': f'{best.code} gives the best saving for this basket.',
        }
