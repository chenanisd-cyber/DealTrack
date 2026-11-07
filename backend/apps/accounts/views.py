from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.moderation.models import AuditLog

from .forms import EmailAuthenticationForm, RegistrationForm


class DealTrackLoginView(LoginView):
    """Connexion. django-axes s'intercale via le backend d'authentification."""

    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class DealTrackLogoutView(LogoutView):
    next_page = reverse_lazy("deals:list")


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("deals:list")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        AuditLog.record(
            action=AuditLog.Action.USER_REGISTERED,
            actor=user,
            target=user,
            request=request,
            metadata={"marketing_consent": user.marketing_consent},
        )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            request, _("Bienvenue sur DealTrack, %(name)s.") % {"name": user.display_name}
        )
        return redirect("deals:list")

    return render(request, "registration/register.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def profile(request):
    return render(
        request,
        "registration/profile.html",
        {
            "deals": request.user.submitted_deals.order_by("-created_at")[:20],
            "payments": request.user.payments.order_by("-created_at")[:20],
            "subscriptions": request.user.subscriptions.all(),
        },
    )


@login_required
@require_http_methods(["GET"])
def export_data(request):
    """Portabilité (art. 20 RGPD) : téléchargement JSON immédiat."""
    AuditLog.record(
        action=AuditLog.Action.USER_DATA_EXPORTED,
        actor=request.user,
        target=request.user,
        request=request,
    )
    response = JsonResponse(
        request.user.export_personal_data(), json_dumps_params={"indent": 2}
    )
    response["Content-Disposition"] = 'attachment; filename="mes-donnees-dealtrack.json"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def close_account(request):
    """
    Désinscription. Confirmation explicite exigée : un GET ne doit jamais
    produire d'effet de bord, sans quoi une simple image <img src="..."> suffit
    à fermer le compte d'un visiteur connecté.
    """
    has_payments = request.user.payments.exists()

    if request.method == "POST":
        if request.POST.get("confirm") != request.user.display_name:
            messages.error(request, _("La confirmation ne correspond pas à votre pseudonyme."))
            return redirect("accounts:close")

        user = request.user
        user.soft_delete(reason=request.POST.get("reason", "")[:300], actor=user)
        if not has_payments:
            user.anonymise(actor=user)
            note = _("Votre compte est fermé et vos données personnelles ont été effacées.")
        else:
            note = _(
                "Votre compte est fermé. Vos factures sont conservées le temps du "
                "délai légal, puis vos données seront anonymisées."
            )
        messages.success(request, note)
        return redirect("deals:list")

    return render(request, "registration/close_account.html", {"has_payments": has_payments})
