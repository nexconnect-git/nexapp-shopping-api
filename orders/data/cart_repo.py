from orders.models import Cart, CartItem


class CartRepository:

    @staticmethod
    def get_or_create_cart(user):
        return Cart.objects.get_or_create(user=user)

    @staticmethod
    def get_cart_with_items(user):
        return Cart.objects.prefetch_related("items__product__vendor").get(user=user)

    @staticmethod
    def get_cart_item(pk, user):
        return CartItem.objects.get(pk=pk, cart__user=user)

    @staticmethod
    def add_item(cart, product, quantity):
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product,
            defaults={"quantity": quantity},
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return cart_item, created

    @staticmethod
    def clear_cart(user):
        try:
            cart = Cart.objects.get(user=user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass
