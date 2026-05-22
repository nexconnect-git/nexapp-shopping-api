from typing import Any, Dict, Optional

from django.db.models import QuerySet

from accounts.models import AdminAuditLog

USER_AGENT_MAX_LENGTH = 255


def _truncate(value: str, max_length: int) -> str:
    text = str(value or '')
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f'{text[:max_length - 3]}...'


def _field_max_length(field_name: str, fallback: int) -> int:
    field = AdminAuditLog._meta.get_field(field_name)
    return field.max_length or fallback


class AdminAuditLogRepository:
    @staticmethod
    def create(
        *,
        actor=None,
        action: str,
        entity_type: str,
        entity_id: str = '',
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: str = '',
    ) -> AdminAuditLog:
        return AdminAuditLog.objects.create(
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            action=_truncate(action, _field_max_length('action', 32)),
            entity_type=_truncate(entity_type, _field_max_length('entity_type', 100)),
            entity_id=_truncate(str(entity_id or ''), _field_max_length('entity_id', 100)),
            summary=_truncate(summary, _field_max_length('summary', 255)),
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=_truncate(user_agent, USER_AGENT_MAX_LENGTH),
        )

    @staticmethod
    def list(
        *,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> QuerySet:
        queryset = AdminAuditLog.objects.select_related('actor').all()
        if action:
            queryset = queryset.filter(action=action)
        if entity_type:
            queryset = queryset.filter(entity_type__iexact=entity_type)
        if actor_id:
            queryset = queryset.filter(actor_id=actor_id)
        if search:
            queryset = queryset.filter(summary__icontains=search)
        return queryset
