import hashlib
import json


def cart_hash(cart) -> str:
    items = sorted((str(item.product_id), item.quantity) for item in cart.items.all())
    return hashlib.md5(json.dumps(items).encode()).hexdigest()
