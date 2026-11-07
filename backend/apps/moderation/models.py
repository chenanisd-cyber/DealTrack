"""
Piste d'audit et décisions de modération.

AuditLog est en ajout seul. La clé primaire est un BigAutoField, contrairement
aux entités métier : ici l'ordre d'insertion porte du sens (une piste d'audit se
lit chronologiquement), l'écriture est massive, et l'identifiant n'est jamais
exposé dans une URL publique. Un UUID aléatoire ferait perdre la localité
d'insertion de l'index sans rien apporter.
"""

import logging
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

audit_logger = logging.getLogger("dealtrack.audit")


class AuditLog(models.Model):
    class Action(models.TextChoices):
        USER_REGISTERED = "user.registered", _("Inscription")
        USER_LOGIN = "user.login", _("Connexion")
        USER_LOGIN_FAILED = "user.login_failed", _("Échec de connexion")
        USER_SOFT_DELETED = "user.soft_deleted", _("Désinscription")
        USER_ANONYMISED = "user.anonymised", _("Anonymisation")
        USER_DATA_EXPORTED = "user.data_exported", _("Export des données")
        DEAL_SUBMITTED = "deal.submitted", _("Deal soumis")
        DEAL_PUBLISHED = "deal.published", _("Deal publié")
        DEAL_REJECTED = "deal.rejected", _("Deal refusé")
        DEAL_UPDATED = "deal.updated", _("Deal modifié")
        DEAL_DELETED = "deal.deleted", _("Deal retiré")
        COMMENT_DELETED = "comment.deleted", _("Commentaire supprimé")
        PAYMENT_INITIATED = "payment.initiated", _("Paiement initié")
        PAYMENT_SUCCEEDED = "payment.succeeded", _("Paiement abouti")
        PAYMENT_FAILED = "payment.failed", _("Paiement échoué")
        PERMISSION_DENIED = "security.permission_denied", _("Accès refusé")
        CSRF_FAILURE = "security.csrf_failure", _("Échec CSRF")

    id = models.BigAutoField(primary_key=True)

    # SET_NULL : effacer un compte ne doit pas effacer la trace de ses actes,
    # mais la trace ne doit pas non plus empêcher l'anonymisation.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        verbose_name=_("auteur de l'action"),
    )
    actor_label = models.CharField(
        _("auteur (copie)"),
        max_length=80,
        blank=True,
        help_text=_("Pseudonyme figé au moment de l'action, pour survivre à l'anonymisation."),
    )
    action = models.CharField(_("action"), max_length=40, choices=Action.choices, db_index=True)

    target_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    target_id = models.CharField(max_length=40, blank=True)
    target = GenericForeignKey("target_type", "target_id")

    ip_address = models.GenericIPAddressField(_("adresse IP"), null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    path = models.CharField(max_length=300, blank=True)
    method = models.CharField(max_length=10, blank=True)
    metadata = models.JSONField(_("détails"), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("entrée d'audit")
        verbose_name_plural = _("journal d'audit")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"], name="audit_action_date_idx"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_date_idx"),
        ]
        # Ajout seul : personne ne modifie ni ne supprime une entrée d'audit.
        default_permissions = ("add", "view")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} par {self.actor_label or '—'}"

    @classmethod
    def record(cls, *, action, actor=None, target=None, request=None, metadata=None):
        """Point d'entrée unique. Écrit en base et dans security.log."""
        entry = cls(
            action=action,
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            actor_label=str(actor) if actor else "",
            metadata=metadata or {},
        )
        if target is not None:
            entry.target_type = ContentType.objects.get_for_model(target)
            entry.target_id = str(target.pk)
        if request is not None:
            # Un HttpRequest fabriqué (force_login, tâche de fond, commande de
            # gestion) n'a ni méthode ni chemin. La piste d'audit doit encaisser
            # ces objets partiels sans lever : une trace incomplète vaut mieux
            # qu'une transaction annulée.
            entry.ip_address = _client_ip(request)
            entry.user_agent = (getattr(request, "META", {}).get("HTTP_USER_AGENT") or "")[:300]
            entry.path = (getattr(request, "path", "") or "")[:300]
            entry.method = (getattr(request, "method", "") or "")[:10]
        entry.save()

        audit_logger.info(
            "%s actor=%s target=%s:%s ip=%s %s",
            action,
            entry.actor_label or "anonyme",
            entry.target_type_id or "-",
            entry.target_id or "-",
            entry.ip_address or "-",
            entry.metadata or {},
        )
        return entry


def _client_ip(request):
    """
    Derrière un reverse proxy, REMOTE_ADDR vaut l'adresse du proxy.
    X-Forwarded-For n'est digne de confiance que si le proxy l'écrase :
    à configurer côté nginx (proxy_set_header X-Forwarded-For $remote_addr).
    """
    meta = getattr(request, "META", {}) or {}
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return meta.get("REMOTE_ADDR") or None


class ModerationDecision(models.Model):
    """Trace nominative de chaque validation ou refus d'offre."""

    class Decision(models.TextChoices):
        APPROVED = "approved", _("Publiée")
        REJECTED = "rejected", _("Refusée")
        EXPIRED = "expired", _("Marquée expirée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deal = models.ForeignKey(
        "deals.Deal", on_delete=models.CASCADE, related_name="moderation_decisions"
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="moderation_decisions"
    )
    decision = models.CharField(max_length=20, choices=Decision.choices)
    reason = models.CharField(_("motif"), max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("décision de modération")
        verbose_name_plural = _("décisions de modération")
        ordering = ["-created_at"]
        constraints = [
            # Un refus sans motif n'est pas contestable par l'auteur.
            models.CheckConstraint(
                condition=~models.Q(decision="rejected") | ~models.Q(reason=""),
                name="rejection_requires_reason",
            ),
        ]

    def __str__(self):
        return f"{self.deal} → {self.decision}"


class Report(models.Model):
    """Signalement d'un contenu par un membre."""

    class Reason(models.TextChoices):
        OUT_OF_STOCK = "out_of_stock", _("Rupture de stock")
        WRONG_PRICE = "wrong_price", _("Prix incorrect")
        MISLEADING = "misleading", _("Réduction trompeuse")
        AFFILIATE = "affiliate", _("Lien d'affiliation personnel")
        SPAM = "spam", _("Spam ou compte promotionnel")

    class Status(models.TextChoices):
        OPEN = "open", _("Ouvert")
        RESOLVED = "resolved", _("Traité")
        DISMISSED = "dismissed", _("Écarté")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deal = models.ForeignKey("deals.Deal", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_filed"
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    detail = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_resolved",
    )

    class Meta:
        verbose_name = _("signalement")
        verbose_name_plural = _("signalements")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["deal", "reporter"], name="uniq_report_per_user_deal"
            ),
            models.CheckConstraint(
                condition=models.Q(status="open") | models.Q(resolved_at__isnull=False),
                name="report_closed_requires_date",
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} · {self.deal}"
