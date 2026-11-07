"""
Permissions objet — la parade au Broken Access Control.

Le contrôle porte sur l'objet, pas sur l'URL : autoriser « /api/deals/<id>/ »
aux authentifiés ne dit rien de QUEL deal l'appelant a le droit de modifier.
"""

from rest_framework import permissions

from apps.deals.models import DealStatus
from apps.moderation.models import AuditLog

SAFE = permissions.SAFE_METHODS


class IsModerator(permissions.BasePermission):
    message = "Réservé à l'équipe de modération."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_moderator)


class ReadOnlyOrAuthenticated(permissions.BasePermission):
    """Lecture ouverte à tous, écriture réservée aux comptes actifs."""

    def has_permission(self, request, view):
        if request.method in SAFE:
            return True
        user = request.user
        return bool(user and user.is_authenticated and not user.is_deleted)


class IsAuthorOrModerator(permissions.BasePermission):
    """
    Écriture réservée à l'auteur tant que l'offre n'est pas publiée, ou à la
    modération à tout moment. Chaque refus est consigné : une rafale de 403 sur
    des identifiants différents signale une tentative d'énumération.
    """

    message = "Vous ne pouvez modifier que vos propres offres non publiées."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE:
            return True

        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_moderator:
            return True

        author = getattr(obj, "submitted_by", None) or getattr(obj, "author", None)
        allowed = author == user and getattr(obj, "status", None) in (
            DealStatus.DRAFT,
            DealStatus.PENDING,
            None,
        )
        if not allowed:
            AuditLog.record(
                action=AuditLog.Action.PERMISSION_DENIED,
                actor=user,
                target=obj,
                request=request,
                metadata={"view": view.__class__.__name__, "method": request.method},
            )
        return allowed


class IsSelf(permissions.BasePermission):
    """Un membre n'accède qu'à son propre profil, ses paiements, ses alertes."""

    def has_object_permission(self, request, view, obj):
        owner = obj if hasattr(obj, "email") else getattr(obj, "user", None)
        return owner == request.user
