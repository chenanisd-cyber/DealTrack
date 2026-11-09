from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms import ContactForm
from .models import AuditLog


def csrf_failure(request, reason=""):
    """
    Vue CSRF personnalisée : consigne l'échec puis renvoie une page lisible
    plutôt que la page technique de Django, qui en dit trop.
    """
    AuditLog.record(
        action=AuditLog.Action.CSRF_FAILURE,
        actor=getattr(request, "user", None),
        request=request,
        metadata={"reason": reason},
    )
    return render(request, "errors/csrf.html", {"reason": reason}, status=403)


# -- Aide et contact ---------------------------------------------------------------
CONTACT_LIMIT = 5  # messages par heure et par adresse IP
CONTACT_WINDOW = 60 * 60

FAQ = [
    (
        _("Comment publier un bon plan ?"),
        _(
            "Connectez-vous, cliquez sur « Publier » et collez le lien de l’offre. "
            "Le formulaire se remplit tout seul : vérifiez, puis envoyez à la modération."
        ),
    ),
    (
        _("Pourquoi mon deal n’apparaît-il pas tout de suite ?"),
        _(
            "Chaque deal est vérifié par un modérateur avant d’être publié, pour éviter "
            "les fausses promotions. Il apparaît dès qu’il est validé."
        ),
    ),
    (
        _("Que m’apporte l’abonnement VIP ?"),
        _(
            "L’historique du prix de chaque deal, la comparaison avec d’autres magasins "
            "et vos alertes en priorité. 2,50 € par mois ou 24 € par an."
        ),
    ),
    (
        _("Comment exporter ou supprimer mes données ?"),
        _(
            "Dans « Mon compte », vous pouvez télécharger vos données ou fermer votre "
            "compte. Vos factures sont conservées sept ans, comme la loi l’impose."
        ),
    ),
    (
        _("Un deal est faux ou expiré : que faire ?"),
        _(
            "Écrivez-nous avec le sujet « Un deal ou un commentaire » et le lien du deal. "
            "Un modérateur le vérifie."
        ),
    ),
]


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else "") or request.META.get(
        "REMOTE_ADDR", ""
    )


@require_http_methods(["GET", "POST"])
def contact(request):
    """
    Page « Aide et contact » : questions fréquentes et formulaire. Le message
    est enregistré en base (traité depuis le back-office) et l'équipe est
    prévenue par e-mail. Protection : CSRF, validation, champ piège anti-robot
    et cinq messages par heure au plus par adresse IP.
    """
    user = request.user if request.user.is_authenticated else None
    initial = {"name": user.display_name, "email": user.email} if user else {}
    form = ContactForm(request.POST or None, initial=initial)
    status = 200

    if request.method == "POST":
        key = f"contact-rate:{_client_ip(request)}"
        sent = cache.get_or_set(key, 0, CONTACT_WINDOW)
        if sent >= CONTACT_LIMIT:
            messages.error(request, _("Trop de messages envoyés. Réessayez dans une heure."))
            status = 429
        elif form.is_valid():
            cache.incr(key)
            message = form.save(commit=False)
            message.user = user
            message.language = (get_language() or "fr")[:2]
            message.save()
            send_mail(
                f"[DealTrack] {message.get_subject_display()} — {message.name}",
                f"{message.message}\n\n{message.name} <{message.email}>",
                settings.DEFAULT_FROM_EMAIL,
                [settings.SUPPORT_EMAIL],
                fail_silently=True,
            )
            messages.success(
                request,
                _("Merci ! Votre message est bien envoyé. Nous vous répondons par e-mail."),
            )
            return redirect("support:contact")

    return render(request, "support/contact.html", {"form": form, "faq": FAQ}, status=status)
