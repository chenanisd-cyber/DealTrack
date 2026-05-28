"""Branchement de la piste d'audit sur les signaux d'authentification."""

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import AuditLog


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AuditLog.record(action=AuditLog.Action.USER_LOGIN, actor=user, target=user, request=request)


@receiver(user_login_failed)
def log_login_failure(sender, credentials, request=None, **kwargs):
    # On consigne l'identifiant tenté sans jamais le mot de passe.
    AuditLog.record(
        action=AuditLog.Action.USER_LOGIN_FAILED,
        request=request,
        metadata={"attempted_username": (credentials or {}).get("username", "")[:120]},
    )
