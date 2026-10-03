import logging
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from accounts.admin_access import allows
from accounts.actions.audit_actions import CreateAdminAuditLogAction
from accounts.data.password_reset_repository import PasswordResetRepository
from accounts.data.user_repository import UserRepository
from accounts.services.email_service import EmailService

logger = logging.getLogger(__name__)

class RequestAccountPasswordResetAction:
    @transaction.atomic
    def execute(self, *, target_id=None, email='', role='', request=None, reason=''):
        user = PasswordResetRepository.locked_user(target_id) if target_id else UserRepository.get_by_email(email, role=role or None)
        if request is not None:
            if not allows(request.user, 'users.reset_password'):
                raise PermissionDenied('Password reset permission is required.')
            if user is None:
                raise NotFound('Account not found.')
            if user.role == 'admin' and not request.user.is_superuser:
                raise PermissionDenied('Only a superuser may reset an administrator account.')
            if not reason.strip():
                raise ValidationError({'reason': 'Explain why this reset is required.'})
            if not user.email or not user.is_active:
                raise ValidationError('An active account with a registered email address is required.')
        if not user or not user.is_active or not user.email:
            return
        user = PasswordResetRepository.locked_user(user.pk)
        if PasswordResetRepository.has_recent_request(user):
            if request is not None:
                raise ValidationError('Wait one minute before requesting another reset.')
            return
        record, raw = PasswordResetRepository.issue(user)
        EmailService.send_password_reset_email(user, raw)
        if request is not None:
            CreateAdminAuditLogAction().execute(request=request, action='password_reset', entity_type='user', entity_id=str(user.pk), summary=f'Requested password reset for {user.username}.', metadata={'account_type': user.role, 'reason': reason.strip(), 'expires_at': record.expires_at.isoformat()})

class ConfirmAccountPasswordResetAction:
    @transaction.atomic
    def execute(self, token, new_password):
        record = PasswordResetRepository.locked_token(token)
        if not record:
            raise ValidationError('Invalid, expired or already used reset link.')
        user = record.user
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            raise ValidationError({'new_password': exc.messages}) from exc
        user.set_password(new_password)
        user.force_password_change = False
        user.temp_password = ''
        user.save(update_fields=['password', 'force_password_change', 'temp_password', 'updated_at'])
        record.used = True
        record.save(update_fields=['used'])
        PasswordResetRepository.invalidate_sessions(user)
        CreateAdminAuditLogAction().execute(actor=user, action='password_reset', entity_type='user', entity_id=str(user.pk), summary='Completed account password reset.')
        transaction.on_commit(lambda: self._notify(user))

    @staticmethod
    def _notify(user):
        try:
            EmailService.send_password_changed_email(user)
        except Exception:
            logger.warning('Password-change notification delivery failed for account %s.', user.pk)
