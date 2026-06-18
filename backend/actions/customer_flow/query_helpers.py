from uuid import UUID

from django.db.models import Q


def uuid_or_none(value):
    try:
        return UUID(str(value))
    except Exception:
        return None


def truthy_query_param(value):
    return str(value or '').lower() in {'1', 'true', 'yes'}


def category_product_query(category):
    if not category or category == 'all':
        return None
    query = (
        Q(category__slug__iexact=category)
        | Q(category__name__iexact=category)
        | Q(category__parent__slug__iexact=category)
    )
    category_id = uuid_or_none(category)
    if category_id:
        query |= Q(category_id=category_id)
    return query


def category_store_query(category):
    if not category or category == 'all':
        return None
    query = Q(products__category__slug__iexact=category)
    category_id = uuid_or_none(category)
    if category_id:
        query |= Q(products__category_id=category_id)
    return query


def category_list_query(category):
    if not category or category == 'all':
        return None
    query = Q(slug__iexact=category) | Q(name__iexact=category)
    category_id = uuid_or_none(category)
    if category_id:
        query |= Q(id=category_id)
    return query
