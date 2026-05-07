from django.contrib import admin

from .models import Category, CategoryTranslation, Merchant, Region


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
    list_display = ("name", "country", "is_local_independent", "is_verified", "vat_number")
    list_filter = ("country", "is_local_independent", "is_verified")
    search_fields = ("name", "vat_number", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name_fr", "name_nl", "name_de")
    search_fields = ("code", "name_fr", "name_nl", "name_de")

    def has_delete_permission(self, request, obj=None):
        return False  # référentiel officiel, non supprimable
