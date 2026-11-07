from django.contrib import admin

from .models import Payment, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name_fr", "price", "vat_rate", "duration_days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name_fr")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount", "vat_amount", "status", "created_at")
    list_filter = ("status", "gateway", "created_at")
    search_fields = ("reference", "gateway_reference", "user__email", "user__display_name")
    autocomplete_fields = ("user", "plan")
    date_hierarchy = "created_at"
    # Pièce comptable : consultable, jamais retouchée.
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "started_at", "ends_at")
    list_filter = ("status", "plan")
    search_fields = ("user__email", "user__display_name")
    autocomplete_fields = ("user", "plan", "payment")

    def has_delete_permission(self, request, obj=None):
        return False
