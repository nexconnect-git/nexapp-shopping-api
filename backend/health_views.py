from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_live(_request):
    return JsonResponse({'status': 'ok'})


@require_GET
def health_ready(_request):
    checks = {
        'database': _check_database(),
        'cache': _check_cache(),
    }
    if getattr(settings, 'HEALTH_CHECK_QUEUE', True):
        checks['queue'] = _check_queue()

    ready = all(item['ok'] for item in checks.values())
    return JsonResponse(
        {
            'status': 'ready' if ready else 'not_ready',
            'checks': checks,
        },
        status=200 if ready else 503,
    )


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return {'ok': True}
    except Exception as exc:
        return {'ok': False, 'error': exc.__class__.__name__}


def _check_cache():
    try:
        key = 'health:ready'
        cache.set(key, 'ok', 5)
        if cache.get(key) not in (None, 'ok'):
            return {'ok': False, 'error': 'unexpected_cache_value'}
        return {'ok': True}
    except Exception as exc:
        return {'ok': False, 'error': exc.__class__.__name__}


def _check_queue():
    try:
        import django_rq

        queue = django_rq.get_queue('default')
        connection_obj = getattr(queue, 'connection', None)
        if connection_obj and hasattr(connection_obj, 'ping'):
            connection_obj.ping()
        return {'ok': True}
    except Exception as exc:
        return {'ok': False, 'error': exc.__class__.__name__}
