from typing import Any, Dict, Optional

from accounts.data.audit_repository import AdminAuditLogRepository
from helpers.request_helpers import get_client_ip


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
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
