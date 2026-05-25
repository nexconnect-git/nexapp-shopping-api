import hashlib
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response


CATALOG_CACHE_PREFIX = 'api:catalog'
DEFAULT_PUBLIC_TTL_SECONDS = int(getattr(settings, 'API_PUBLIC_CACHE_TTL_SECONDS', 120))
DEFAULT_REFERENCE_TTL_SECONDS = int(getattr(settings, 'API_REFERENCE_CACHE_TTL_SECONDS', 300))


def cached_api_response(
    request,
    namespace,
    ttl_seconds,
    producer,
    include_user=False,
    cache_statuses=(200,),
):
    key = _cache_key(request, namespace, include_user=include_user)
    try:
        cached = cache.get(key)
    except Exception:
        cached = None
    if cached is not None:
        response = Response(cached['data'], status=cached['status'])
        _apply_cache_headers(response, ttl_seconds, hit=True, private=include_user)
        return response

    response = producer()
    if response.status_code in cache_statuses:
        try:
            cache.set(
                key,
                {
                    'data': response.data,
                    'status': response.status_code,
                },
                ttl_seconds,
            )
            _apply_cache_headers(response, ttl_seconds, hit=False, private=include_user)
        except Exception:
            pass
    return response


def invalidate_catalog_cache():
    pattern = f'{CATALOG_CACHE_PREFIX}:*'
    try:
        cache.delete_pattern(pattern)
    except AttributeError:
        cache.clear()
    except Exception:
        pass


def _cache_key(request, namespace, include_user=False):
    user_segment = 'public'
    if include_user:
        user = getattr(request, 'user', None)
        user_segment = str(getattr(user, 'id', 'anon')) if getattr(user, 'is_authenticated', False) else 'anon'
    query = _canonical_query(request)
    raw = f'{namespace}:{user_segment}:{query}'
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f'{CATALOG_CACHE_PREFIX}:{namespace}:{digest}'


def _canonical_query(request):
    query_params = getattr(request, 'query_params', request.GET)
    pairs = []
    for key, values in query_params.lists():
        for value in values:
            pairs.append((key, value))
    return urlencode(sorted(pairs), doseq=True)


def _apply_cache_headers(response, ttl_seconds, hit=False, private=False):
    response['X-Backend-Cache'] = 'HIT' if hit else 'MISS'
    scope = 'private' if private else 'public'
    response['Cache-Control'] = f'{scope}, max-age={ttl_seconds}'
