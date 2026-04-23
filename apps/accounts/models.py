"""
Comptes utilisateurs.

Choix de clé primaire : UUIDv4 plutôt qu'un entier auto-incrémenté.
  - Invariante : elle ne dépend d'aucune donnée métier modifiable. L'e-mail et
    le pseudonyme changent, l'identifiant non.
  - Non devinable : un identifiant séquentiel exposé dans une URL d'API invite
    à l'énumération (Broken Access Control par référence directe d'objet).
  - Elle ne divulgue pas le volume d'inscriptions à un concurrent.
Coût assumé : 16 octets au lieu de 8 et un index un peu plus lourd.
"""

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Trois rôles, hiérarchiques, adossés aux groupes Django."""

    MEMBER = "member", _("Membre")
    MODERATOR = "moderator", _("Modérateur")
    ADMIN = "admin", _("Administrateur")


class UserQuerySet(models.QuerySet):
    def active(self):
        """Comptes non désinscrits. Base de tous les écrans publics."""
        return self.filter(deleted_at__isnull=True, is_active=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError(_("Une adresse e-mail est obligatoire."))
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", Role.MEMBER)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("display_name", email.split("@")[0])
        if extra.get("is_staff") is not True:
            raise ValueError(_("Un superutilisateur doit avoir is_staff=True."))
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(
        _("adresse e-mail"),
        unique=True,
        max_length=254,
        help_text=_("Sert d'identifiant de connexion. Stockée en minuscules."),
    )
    display_name = models.CharField(
        _("pseudonyme"),
        max_length=40,
        unique=True,
        validators=[
            MinLengthValidator(3),
            RegexValidator(
                r"^[\w.\-]+$",
                _("Lettres, chiffres, point, tiret et souligné uniquement."),
            ),
        ],
        help_text=_("Nom affiché publiquement à côté des deals et commentaires."),
    )
    role = models.CharField(
        _("rôle"), max_length=20, choices=Role.choices, default=Role.MEMBER, db_index=True
    )
    preferred_language = models.CharField(
        _("langue préférée"),
        max_length=5,
        choices=settings.LANGUAGES,
        default="fr",
    )
    home_region = models.ForeignKey(
        "catalog.Region",
        verbose_name=_("région"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="residents",
        help_text=_("Sert à trier les deals de proximité. Facultatif."),
    )

    is_active = models.BooleanField(_("actif"), default=True)
    is_staff = models.BooleanField(_("accès au back-office"), default=False)
    date_joined = models.DateTimeField(_("inscrit le"), default=timezone.now)

    # --- Désinscription en douceur -------------------------------------
    deleted_at = models.DateTimeField(
        _("désinscrit le"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Renseigné à la désinscription. La ligne n'est jamais supprimée."),
    )
    anonymised_at = models.DateTimeField(
        _("anonymisé le"),
        null=True,
        blank=True,
        help_text=_("Renseigné une fois les données personnelles écrasées."),
    )

    # --- Consentements RGPD --------------------------------------------
    accepted_terms_at = models.DateTimeField(_("CGU acceptées le"), null=True, blank=True)
    marketing_consent = models.BooleanField(
        _("consentement marketing"),
        default=False,
        help_text=_("Consentement explicite, distinct des CGU (art. 7 RGPD)."),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        ordering = ["-date_joined"]
        constraints = [
            # Un compte anonymisé est nécessairement désinscrit. L'inverse est
            # permis : on peut désinscrire d'abord et purger ensuite.
            models.CheckConstraint(
                condition=models.Q(anonymised_at__isnull=True)
                | models.Q(deleted_at__isnull=False),
                name="user_anonymised_implies_deleted",
            ),
        ]
        indexes = [models.Index(fields=["role", "is_active"], name="user_role_active_idx")]

    def __str__(self):
        return self.display_name

    # -- Rôles ----------------------------------------------------------
    @property
    def is_moderator(self):
        return self.role in {Role.MODERATOR, Role.ADMIN}

    @property
    def is_administrator(self):
        return self.role == Role.ADMIN

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    # -- Désinscription -------------------------------------------------
    def soft_delete(self, *, reason="", actor=None):
        """
        Désinscrit sans détruire la ligne.

        Les paiements pointent vers ce compte avec on_delete=PROTECT : une
        suppression réelle lèverait ProtectedError, et devrait la lever, parce
        que le droit comptable belge impose de conserver les pièces sept ans.
        On coupe donc l'accès et on conserve la coquille référencée.
        """
        if self.is_deleted:
            return self
        now = timezone.now()
        self.deleted_at = now
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active"])

        from apps.moderation.models import AuditLog

        AuditLog.record(
            actor=actor or self,
            action=AuditLog.Action.USER_SOFT_DELETED,
            target=self,
            metadata={"reason": reason},
        )
        return self

    def anonymise(self, *, actor=None):
        """
        Droit à l'effacement (art. 17 RGPD), version compatible avec les
        obligations de conservation.

        Les données personnelles sont écrasées de façon irréversible ; la ligne
        et sa clé primaire subsistent pour que les factures restent rattachables
        à une entité, sans que celle-ci soit encore identifiable.
        """
        if not self.is_deleted:
            self.soft_delete(reason="anonymisation", actor=actor)

        token = str(self.pk)[:8]
        self.email = f"anonyme-{token}@{settings.ANONYMISED_EMAIL_DOMAIN}"
        self.display_name = f"membre-supprimé-{token}"
        self.home_region = None
        self.marketing_consent = False
        self.anonymised_at = timezone.now()
        self.set_unusable_password()
        self.save(
            update_fields=[
                "email",
                "display_name",
                "home_region",
                "marketing_consent",
                "anonymised_at",
                "password",
            ]
        )

        from apps.moderation.models import AuditLog

        AuditLog.record(
            actor=actor,
            action=AuditLog.Action.USER_ANONYMISED,
            target=self,
            metadata={"retained_for_accounting": True},
        )
        return self

    def export_personal_data(self):
        """Droit à la portabilité (art. 20 RGPD) : dictionnaire sérialisable."""
        return {
            "identifiant": str(self.pk),
            "email": self.email,
            "pseudonyme": self.display_name,
            "langue": self.preferred_language,
            "region": self.home_region.code if self.home_region else None,
            "inscrit_le": self.date_joined.isoformat(),
            "consentement_marketing": self.marketing_consent,
            "deals_publies": [
                {"titre": d.title, "publie_le": d.created_at.isoformat()}
                for d in self.submitted_deals.all()
            ],
            "commentaires": [
                {"texte": c.body, "publie_le": c.created_at.isoformat()}
                for c in self.comments.filter(deleted_at__isnull=True)
            ],
            "paiements": [
                {
                    "reference": p.reference,
                    "montant": str(p.amount),
                    "devise": p.currency,
                    "date": p.created_at.isoformat(),
                }
                for p in self.payments.all()
            ],
        }
