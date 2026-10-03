from typing import Any, Dict, Optional

from accounts.data.audit_repository import AdminAuditLogRepository
from helpers.request_helpers import get_client_ip


def scrub_audit(value):
    if isinstance(value, dict):
        return {key: '[redacted]' if any(secret in key.lower() for secret in ('password', 'token', 'secret', 'otp', 'authorization')) else scrub_audit(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub_audit(item) for item in value]
    return value


class CreateAdminAuditLogAction:
    def execute(
        self,
        *,
        request=None,
        actor=None,
        action: str,
        entity_type: str,
        entity_id: str = '',
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        request_actor = getattr(request, 'user', None) if request is not None else None
        resolved_actor = actor or request_actor
        ip_address = get_client_ip(request) if request is not None else None
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request is not None else ''

        return AdminAuditLogRepository.create(
            actor=resolved_actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            metadata=scrub_audit(metadata or {}),
            ip_address=ip_address,
            user_agent=user_agent,
        )
