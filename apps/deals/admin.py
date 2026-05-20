from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import Alert, Comment, Deal, DealStatus, DealTranslation, Vote


class DealTranslationInline(admin.StackedInline):
    # StackedInline plutôt que TabularInline : la description fait jusqu'à
    # 4 000 caractères, illisible dans une cellule de tableau.
    model = DealTranslation
    extra = 0


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "merchant",
        "price",
        "status",
        "temperature",
        "submitted_by",
        "created_at",
    )
    list_filter = ("status", "is_cross_border", "language", "category", "merchant__country")
    search_fields = ("title", "description", "merchant__name", "submitted_by__display_name")
    autocomplete_fields = ("merchant", "category", "submitted_by")
    filter_horizontal = ("regions",)
    readonly_fields = ("temperature", "created_at", "updated_at", "published_at", "deleted_at")
    date_hierarchy = "created_at"
    actions = ("action_publish", "action_reject", "action_soft_delete")
    inlines = [DealTranslationInline]

    def get_queryset(self, request):
        # Les offres retirées restent visibles au back-office : c'est le
        # principe même du retrait logique.
        return (
            super()
            .get_queryset(request)
            .select_related("merchant", "category", "submitted_by")
            .prefetch_related("translations")
        )

    @admin.action(description=_("Publier les offres sélectionnées"))
    def action_publish(self, request, queryset):
        published = 0
        for deal in queryset.exclude(status=DealStatus.PUBLISHED):
            deal.publish(moderator=request.user, reason="Validation groupée au back-office")
            published += 1
        self.message_user(request, _("%d offre(s) publiée(s).") % published, messages.SUCCESS)

    @admin.action(description=_("Refuser (motif générique)"))
    def action_reject(self, request, queryset):
        count = 0
        for deal in queryset.exclude(status=DealStatus.REJECTED):
            deal.reject(moderator=request.user, reason="Non conforme aux règles de publication")
            count += 1
        self.message_user(request, _("%d offre(s) refusée(s).") % count, messages.WARNING)

    @admin.action(description=_("Retirer du flux (suppression logique)"))
    def action_soft_delete(self, request, queryset):
        count = 0
        for deal in queryset.filter(deleted_at__isnull=True):
            deal.soft_delete(actor=request.user)
            count += 1
        self.message_user(request, _("%d offre(s) retirée(s).") % count, messages.WARNING)

    # La suppression physique est retirée du back-office : elle détruirait les
    # votes et les commentaires liés.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "deal", "created_at", "deleted_at")
    list_filter = ("created_at", "is_verified_purchase")
    search_fields = ("body", "author__display_name", "deal__title")
    autocomplete_fields = ("deal", "author")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("deal", "user", "value", "created_at")
    list_filter = ("value", "created_at")
    autocomplete_fields = ("deal", "user")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("user", "keyword", "region", "category", "max_price", "is_active")
    list_filter = ("is_active", "region")
    search_fields = ("keyword", "user__display_name")
    autocomplete_fields = ("user", "category", "region")
