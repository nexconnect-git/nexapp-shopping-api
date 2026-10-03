from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.admin_access import ADMIN_PERMISSION_CATALOG, allows, granted_permissions
from accounts.actions import CreateAdminAuditLogAction
from accounts.serializers.audit_serializers import AdminAuditLogSerializer
from backend.data.admin_console_repository import AdminConsoleRepository
from backend.data.scheduled_task_repository import ScheduledTaskRepository
from delivery.actions import AdminReassignDeliveryAction
from helpers.geo_helpers import haversine
from orders.models import OrderIssue


class DispatchConsoleAction:
    def execute(self, orders, order_id=None):
        now = timezone.now()
        rows = []
        for order in orders:
            ready = min((event.timestamp for event in order.tracking.all() if event.status == 'ready'), default=None)
            pickup_due = ready + timedelta(minutes=getattr(settings, 'ADMIN_PICKUP_SLA_MINUTES', 20)) if ready else None
            accepted = max((event.timestamp for event in order.tracking.all() if event.status == 'accepted'), default=None)
            delivery_due = accepted + timedelta(minutes=order.estimated_delivery_time) if accepted and order.estimated_delivery_time else None
            deadline = pickup_due if order.status == 'ready' else delivery_due if order.status in ('picked_up', 'on_the_way') else None
            rows.append({
                'id': str(order.pk), 'order_number': order.order_number, 'status': order.status,
                'vendor_name': order.vendor.store_name, 'customer_name': order.customer.get_full_name() or order.customer.username,
                'partner_name': order.delivery_partner.get_full_name() or order.delivery_partner.username if order.delivery_partner else None,
                'partner_id': str(order.delivery_partner.delivery_profile.pk) if order.delivery_partner and hasattr(order.delivery_partner, 'delivery_profile') else None,
                'placed_at': order.placed_at, 'ready_at': ready, 'deadline': deadline,
                'delayed': bool(deadline and deadline < now), 'priority': order.dispatch_priority,
                'escalated_at': order.dispatch_escalated_at, 'notes': order.dispatch_notes,
                'can_assign': order.status == 'ready', 'can_unassign': order.status == 'ready' and order.delivery_partner_id is not None,
            })
        origin = next((order for order in orders if str(order.pk) == str(order_id)), None)
        partners = []
        for partner in AdminConsoleRepository.partners()[:200]:
            distance = None
            if origin and all(value is not None for value in (origin.vendor.latitude, origin.vendor.longitude, partner.current_latitude, partner.current_longitude)):
                distance = round(haversine(float(origin.vendor.latitude), float(origin.vendor.longitude), float(partner.current_latitude), float(partner.current_longitude)), 2)
            partners.append({'id': str(partner.pk), 'name': partner.user.get_full_name() or partner.user.username, 'status': partner.status, 'workload': partner.workload, 'capacity': 1, 'distance_km': distance, 'available': partner.status == 'available' and partner.workload == 0})
        if origin:
            partners.sort(key=lambda partner: (not partner['available'], partner['distance_km'] is None, partner['distance_km'] or 0))
        return {'results': rows, 'partners': partners, 'generated_at': now, 'pickup_sla_minutes': getattr(settings, 'ADMIN_PICKUP_SLA_MINUTES', 20)}


class UpdateDispatchAction:
    @transaction.atomic
    def execute(self, pk, data, request):
        order = AdminConsoleRepository.locked_order(pk)
        command = data['command']
        if command in ('assign', 'unassign'):
            if order.status != 'ready':
                raise ValidationError('Only orders ready for pickup can be assigned or unassigned. In-transit custody must remain intact.')
            if command == 'assign':
                target = next((partner for partner in AdminConsoleRepository.partners() if str(partner.pk) == str(data.get('partner_id'))), None)
                if not target or target.status != 'available' or target.workload:
                    raise ValidationError('This partner is unavailable or already has an active delivery.')
            try:
                return AdminReassignDeliveryAction.execute(str(pk), request.user, delivery_partner_id=str(data['partner_id']) if command == 'assign' else '', reason=data['reason'], request=request)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        old = {'priority': order.dispatch_priority, 'notes': order.dispatch_notes, 'escalated_at': order.dispatch_escalated_at.isoformat() if order.dispatch_escalated_at else None}
        if command == 'escalate':
            order.dispatch_escalated_at = timezone.now()
            order.dispatch_priority = 'urgent'
        elif command == 'clear_escalation':
            order.dispatch_escalated_at = None
        if 'priority' in data:
            order.dispatch_priority = data['priority']
        if 'notes' in data:
            order.dispatch_notes = data['notes']
        AdminConsoleRepository.save(order, ['dispatch_escalated_at', 'dispatch_priority', 'dispatch_notes'])
        CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='order', entity_id=str(order.pk), summary=f'Dispatch {command} for {order.order_number}.', metadata={'old': old, 'new': {'priority': order.dispatch_priority, 'notes': order.dispatch_notes}, 'reason': data['reason']})
        return order


class UpdateSupportCaseAction:
    @transaction.atomic
    def execute(self, pk, data, request):
        issue = AdminConsoleRepository.locked_issue(pk)
        if data.get('assignee') and not AdminConsoleRepository.admin_exists(data['assignee']):
            raise ValidationError({'assignee': 'Choose an active administrator.'})
        if data.get('refund_amount') is not None and data['refund_amount'] > issue.order.total:
            raise ValidationError({'refund_amount': 'Refund amount cannot exceed the order total.'})
        old = {field: str(getattr(issue, field)) for field in data}
        for field, value in data.items():
            setattr(issue, f'{field}_id' if field == 'assignee' else field, value)
        if data.get('status') in ('resolved', 'closed', 'rejected'):
            issue.resolved_by = request.user
            issue.resolved_at = timezone.now()
        elif 'status' in data:
            issue.resolved_by = None
            issue.resolved_at = None
        fields = [f'{field}_id' if field == 'assignee' else field for field in data]
        AdminConsoleRepository.save(issue, fields + ['resolved_by', 'resolved_at'])
        CreateAdminAuditLogAction().execute(request=request, action='update', entity_type='order_issue', entity_id=str(issue.pk), summary=f'Updated support case for {issue.order.order_number}.', metadata={'old': old, 'new': {field: str(value) for field, value in data.items()}, 'order_id': str(issue.order_id)})
        return issue


class ProfileOperationalContextAction:
    def execute(self, entity_type, pk, request):
        domain = {'vendor': 'vendors', 'customer': 'customers', 'delivery-partner': 'dispatch', 'admin-user': None}.get(entity_type)
        if entity_type not in ('vendor', 'customer', 'delivery-partner', 'admin-user'):
            raise ValidationError('Unsupported profile type.')
        if domain and not allows(request.user, f'{domain}.view'):
            raise PermissionDenied()
        if entity_type == 'admin-user' and str(pk) != str(request.user.pk) and not request.user.is_superuser:
            raise PermissionDenied()
        entity, user, orders = AdminConsoleRepository.profile(entity_type, pk)
        result = {'user': {'id': str(user.pk), 'name': user.get_full_name() or user.username, 'role': user.role, 'email': user.email, 'phone': user.phone}, 'generated_at': timezone.now()}
        if allows(request.user, 'orders.view') and entity_type != 'admin-user':
            result['metrics'] = {'total_orders': orders.count(), 'completed_orders': orders.filter(status='delivered').count(), 'cancelled_orders': orders.filter(status='cancelled').count(), 'active_orders': orders.exclude(status__in=['delivered', 'cancelled']).count(), 'delivered_value': orders.filter(status='delivered').aggregate(amount=Sum('total'))['amount'] or 0}
            result['orders'] = list(orders.order_by('-placed_at').values('id', 'order_number', 'status', 'total', 'placed_at')[:10])
        result['activities'] = AdminAuditLogSerializer(AdminConsoleRepository.audit([entity.pk, user.pk])[:30], many=True).data if allows(request.user, 'audit.view') else []
        if entity_type == 'vendor' and allows(request.user, 'audit.view'):
            result['activities'] += [{
                'id': f'vendor-{event.pk}', 'summary': event.description, 'action': event.action,
                'actor_name': event.performed_by.get_full_name() or event.performed_by.username if event.performed_by else 'System',
                'created_at': event.created_at.isoformat(),
            } for event in AdminConsoleRepository.vendor_audit(entity.pk)[:30]]
            result['activities'] = sorted(result['activities'], key=lambda event: str(event['created_at']), reverse=True)[:30]
        related = AdminConsoleRepository.related_profile(entity_type, entity, user, orders)
        result['related'] = []
        for key, permission, route in [('issues', 'support.view', '/issues'), ('payments', 'finance.view', '/payments'), ('products', 'catalog.view', '/products'), ('payouts', 'finance.view', '/payouts'), ('assets', 'dispatch.view', '/assets')]:
            if key in related and allows(request.user, permission) and entity_type != 'admin-user':
                filter_key = 'vendor' if entity_type == 'vendor' else 'customer' if entity_type == 'customer' else 'delivery_partner'
                filter_id = entity.pk
                if key == 'assets':
                    filter_key = 'assigned_to'
                if key == 'payouts':
                    if entity_type == 'delivery-partner':
                        filter_key, filter_id = 'partner', user.pk
                        route += '?tab=delivery&'
                    else:
                        route += '?tab=vendors&'
                else:
                    route += '?'
                result['related'].append({'label': key.capitalize(), 'count': related[key].count(), 'route': f'{route}{filter_key}={filter_id}'})
        if entity_type == 'vendor':
            result['documents'] = [{'id': str(doc.pk), 'document_type': doc.get_document_type_display(), 'status': doc.status, 'expires_on': doc.expires_on, 'expired': bool(doc.expires_on and doc.expires_on < timezone.localdate()), 'file': request.build_absolute_uri(doc.file.url) if doc.file else ''} for doc in related['documents']]
        return result


class AdminReadinessAction:
    def execute(self):
        try:
            queue = ScheduledTaskRepository().get_queue()
            connected = queue.connection.ping() is True
            jobs = {'state': 'connected' if connected else 'unavailable', 'queued': queue.count if connected else None}
        except Exception:
            jobs = {'state': 'unavailable', 'queued': None}
        try:
            database = 'connected' if AdminConsoleRepository.database_connected() else 'unavailable'
        except Exception:
            database = 'unavailable'
        return {'generated_at': timezone.now(), 'database': database, 'jobs': jobs, 'channel_backend': settings.CHANNEL_LAYERS.get('default', {}).get('BACKEND', 'Not configured'), 'permissions': {'defined': len(ADMIN_PERMISSION_CATALOG)}, 'scope': 'Runtime connectivity checks. Worker execution, external gateway and bank connectivity need separate environment verification.'}


class AdminUserMutationAction:
    @transaction.atomic
    def execute(self, pk, data, request, delete=False):
        user, active_superusers = AdminConsoleRepository.locked_administrators(pk)
        if delete and str(user.pk) == str(request.user.pk):
            raise ValidationError('You cannot delete your own administrator account.')
        if user.role == 'admin' and user.is_superuser and user.is_active and (delete or data.get('is_active') is False) and active_superusers <= 1:
            raise ValidationError('The final active superuser cannot be disabled or deleted.')
        old = {key: str(getattr(user, key)) for key in data if hasattr(user, key)}
        CreateAdminAuditLogAction().execute(request=request, action='delete' if delete else 'update', entity_type='user', entity_id=str(user.pk), summary=f'{"Deleted" if delete else "Updated"} administrator {user.username}.', metadata={'old': old, 'new': data})
        if delete:
            AdminConsoleRepository.delete(user)
            return None
        for key, value in data.items():
            setattr(user, key, value)
        return AdminConsoleRepository.save(user, list(data))


class UpdateAdminSettingsAction:
    @transaction.atomic
    def execute(self, data, request):
        setting = AdminConsoleRepository.platform_setting(lock=True)
        old = {key: str(getattr(setting, key)) for key in data}
        for key, value in data.items():
            setattr(setting, key, value)
        setting.save(update_fields=list(data))
        CreateAdminAuditLogAction().execute(request=request, action='settings', entity_type='platform_setting', entity_id=str(setting.pk), summary='Updated platform settings.', metadata={'old': old, 'new': {key: str(value) for key, value in data.items()}})
        return setting
