from django.http import JsonResponse
from django.views.decorators.http import require_GET

from backend.actions.health_actions import HealthReadinessAction


@require_GET
def health_live(_request):
    return JsonResponse({'status': 'ok'})


@require_GET
def health_ready(_request):
    payload, response_status = HealthReadinessAction().execute()
    return JsonResponse(payload, status=response_status)
