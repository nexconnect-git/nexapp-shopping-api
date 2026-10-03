from django.db import transaction

from accounts.actions.audit_actions import CreateAdminAuditLogAction
from orders.data.operations_repo import FeatureFlagRepository
from notifications.data.notification_repository import NotificationRepository


class UpdatePageConfigurationAction:
    @transaction.atomic
    def execute(self, data, request, defaults):
        flag = FeatureFlagRepository.page_configuration(defaults, lock=True)
        metadata = {**defaults, **(flag.metadata if isinstance(flag.metadata,dict) else {})}
        old = metadata.copy()
        for key in ('applications','global_settings'):
            if key in data:
                metadata[key] = data[key] if key == 'applications' else {**defaults['global_settings'], **metadata.get(key, {}), **data[key]}
        if 'is_enabled' in data:
            flag.is_enabled=data['is_enabled']
        metadata['version']=int(metadata.get('version') or 1)+1
        flag.metadata, flag.updated_by=metadata, request.user
        FeatureFlagRepository.save_configuration(flag)
        old_pages = {page['id']: page for app in old.get('applications', []) for page in app.get('pages', [])}
        changed = [page for app in metadata.get('applications', []) for page in app.get('pages', []) if page.get('status') != old_pages.get(page['id'], {}).get('status')]
        preferences = metadata.get('global_settings', {})
        disabled = [page for page in changed if page.get('status') == 'disabled']
        if (disabled and preferences.get('pageDisabledAlerts')) or (len(changed) > 1 and preferences.get('bulkActionAlerts')):
            NotificationRepository.create(user=request.user, title='Page availability updated', message=f'{len(changed)} page configurations changed; {len(disabled)} disabled.', notification_type='system', data={'route': '/settings/page-feature-management'})
        CreateAdminAuditLogAction().execute(request=request,action='settings',entity_type='page_feature_config',entity_id='page_feature_management',summary='Updated registered page availability configuration.',metadata={'old':old,'new':metadata})
        return flag
