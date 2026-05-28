"""
Back-office. Deux principes :
  - Le journal d'audit est consultable, jamais modifiable ni supprimable.
  - Les actions de modération passent par les méthodes métier du modèle, pour
    que la décision soit tracée comme si elle venait du front.
"""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .models import AuditLog, ModerationDecision, Report


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor_label", "target_type", "ip_address", "path")
    list_filter = ("action", "created_at")
    search_fields = ("actor_label", "ip_address", "path", "target_id")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ("-created_at",)

    # Piste d'audit en ajout seul : une trace modifiable ne prouve rien.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ModerationDecision)
class ModerationDecisionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "deal", "decision", "moderator", "reason")
    list_filter = ("decision", "created_at")
    search_fields = ("deal__title", "reason")
    autocomplete_fields = ("deal", "moderator")
    readonly_fields = ("created_at",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "deal", "reason", "reporter", "status")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("deal__title", "detail")
    autocomplete_fields = ("deal", "reporter")
    actions = ("mark_resolved", "mark_dismissed")

    @admin.action(description=_("Marquer comme traité"))
    def mark_resolved(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(status=Report.Status.OPEN).update(
            status=Report.Status.RESOLVED, resolved_at=timezone.now(), resolved_by=request.user
        )
        self.message_user(
            request,
            ngettext("%d signalement traité.", "%d signalements traités.", count) % count,
            messages.SUCCESS,
        )

    @admin.action(description=_("Écarter"))
    def mark_dismissed(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(status=Report.Status.OPEN).update(
            status=Report.Status.DISMISSED, resolved_at=timezone.now(), resolved_by=request.user
        )
        self.message_user(request, _("%d signalement(s) écarté(s).") % count, messages.SUCCESS)
