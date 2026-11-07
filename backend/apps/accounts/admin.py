from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "display_name", "role", "is_active", "deleted_at", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "deleted_at", "preferred_language")
    search_fields = ("email", "display_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "deleted_at", "anonymised_at")
    autocomplete_fields = ("home_region",)
    actions = ("action_soft_delete", "action_anonymise")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Identité"), {"fields": ("display_name", "preferred_language", "home_region")}),
        (
            _("Rôle et accès"),
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("RGPD"),
            {
                "fields": (
                    "accepted_terms_at",
                    "marketing_consent",
                    "deleted_at",
                    "anonymised_at",
                )
            },
        ),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2", "role"),
            },
        ),
    )

    @admin.action(description=_("Désinscrire (suppression logique)"))
    def action_soft_delete(self, request, queryset):
        count = 0
        for user in queryset.filter(deleted_at__isnull=True):
            user.soft_delete(reason="Décision back-office", actor=request.user)
            count += 1
        self.message_user(request, _("%d compte(s) désinscrit(s).") % count, messages.WARNING)

    @admin.action(description=_("Anonymiser (droit à l'effacement)"))
    def action_anonymise(self, request, queryset):
        count = 0
        for user in queryset.filter(anonymised_at__isnull=True):
            user.anonymise(actor=request.user)
            count += 1
        self.message_user(
            request,
            _("%d compte(s) anonymisé(s). Les factures restent rattachées.") % count,
            messages.WARNING,
        )

    # Aucune suppression physique : les paiements sont en PROTECT et lèveraient
    # ProtectedError. Le back-office propose la voie correcte à la place.
    def has_delete_permission(self, request, obj=None):
        return False
