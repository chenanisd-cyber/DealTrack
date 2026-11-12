from django.contrib import admin

from .models import Category, CategoryTranslation, Merchant, MerchantAccount


@admin.register(MerchantAccount)
class MerchantAccountAdmin(admin.ModelAdmin):
    """Demandes d'accès à l'espace commerçant : la modération accepte ou refuse."""

    list_display = ("merchant", "user", "status", "message", "created_at", "decided_by")
    list_filter = ("status",)
    search_fields = ("merchant__name", "user__email", "user__display_name")
    readonly_fields = ("user", "merchant", "message", "created_at", "decided_at", "decided_by")
    fields = (*readonly_fields, "status")
    actions = ["approve", "reject"]

    def has_add_permission(self, request):
        return False  # une demande vient toujours du membre, depuis le site

    def save_model(self, request, obj, form, change):
        # Statut modifié depuis la fiche : même traçabilité que les actions groupées.
        if "status" in form.changed_data and obj.status != MerchantAccount.Status.PENDING:
            obj.decide(
                moderator=request.user, approve=obj.status == MerchantAccount.Status.APPROVED
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Accepter les demandes sélectionnées")
    def approve(self, request, queryset):
        for account in queryset:
            account.decide(moderator=request.user, approve=True)
        self.message_user(request, f"{queryset.count()} demande(s) acceptée(s).")

    @admin.action(description="Refuser les demandes sélectionnées")
    def reject(self, request, queryset):
        for account in queryset:
            account.decide(moderator=request.user, approve=False)
        self.message_user(request, f"{queryset.count()} demande(s) refusée(s).")


class CategoryTranslationInline(admin.TabularInline):
    model = CategoryTranslation
    extra = 0
    min_num = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("slug", "label_fr", "parent", "position", "is_active")
    list_filter = ("is_active",)
    search_fields = ("slug", "translations__name")
    inlines = [CategoryTranslationInline]

    @admin.display(description="Libellé (fr)")
    def label_fr(self, obj):
        return obj.label("fr")


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "city",
        "shop_type",
        "is_local_independent",
        "is_verified",
        "vat_number",
    )
    list_filter = ("country", "is_local_independent", "is_verified", "city", "shop_type")
    search_fields = ("name", "vat_number", "slug", "city", "address")
    prepopulated_fields = {"slug": ("name",)}
