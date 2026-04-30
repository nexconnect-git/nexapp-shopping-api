from typing import Any, Dict, Optional

from django.db.models import QuerySet

from accounts.models import AdminAuditLog


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
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ''),
            summary=summary,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
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
