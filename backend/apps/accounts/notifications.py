"""
Notifications par e-mail liées à l'activité d'un membre.

Trois événements : son deal est publié, son deal est refusé, un autre membre
commente son deal. (Les alertes par mot-clé ont leur propre envoi groupé :
commande `send_alerts`.)

Règles communes :
- le membre peut couper chaque type d'e-mail depuis son profil ;
- un compte fermé ou anonymisé ne reçoit plus rien ;
- le message est écrit dans la langue préférée du membre ;
- un envoi qui échoue ne doit jamais annuler l'action qui l'a déclenché
  (publier un deal, enregistrer un commentaire) : l'erreur est journalisée.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext as _
from django.utils.translation import override

logger = logging.getLogger("dealtrack.notifications")


def _site():
    return (getattr(settings, "SITE_URL", "") or "http://localhost:8000").rstrip("/")


def _send(user, subject, lines):
    """Envoie un e-mail texte au membre. Renvoie True s'il est parti."""
    if not user or not user.is_active or user.deleted_at or not user.email:
        return False
    body = "\n".join(
        [
            _("Bonjour %(name)s,") % {"name": user.display_name},
            "",
            *lines,
            "",
            _("Vous pouvez choisir les e-mails que vous recevez dans votre profil :"),
            f"{_site()}/{user.preferred_language or 'fr'}/comptes/profil/modifier/",
            "",
            "DealTrack.be",
        ]
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:  # serveur d'envoi indisponible : on n'interrompt pas l'action
        logger.exception("E-mail non envoyé à %s", user.pk)
        return False
    return True


def deal_published(deal):
    """Le deal du membre vient d'être validé par la modération."""
    author = deal.submitted_by
    if not author.notify_moderation:
        return False
    with override(author.preferred_language or "fr"):
        return _send(
            author,
            _("DealTrack : votre deal est en ligne"),
            [
                _("Bonne nouvelle : votre deal a été validé et il est maintenant visible."),
                "",
                deal.title,
                f"{_site()}{deal.get_absolute_url()}",
            ],
        )


def deal_rejected(deal, reason):
    """Le deal du membre a été refusé ; le motif du modérateur est repris."""
    author = deal.submitted_by
    if not author.notify_moderation:
        return False
    with override(author.preferred_language or "fr"):
        return _send(
            author,
            _("DealTrack : votre deal n'a pas été publié"),
            [
                _("Votre deal n'a pas pu être publié."),
                "",
                deal.title,
                _("Motif indiqué par la modération : %(reason)s") % {"reason": reason},
                "",
                _("Vous pouvez le corriger et le proposer à nouveau."),
            ],
        )


def new_comment(comment):
    """Un autre membre a commenté le deal de l'auteur."""
    deal = comment.deal
    author = deal.submitted_by
    if comment.author_id == author.pk or not author.notify_comments:
        return False
    with override(author.preferred_language or "fr"):
        return _send(
            author,
            _("DealTrack : nouveau commentaire sur votre deal"),
            [
                _("%(name)s a commenté votre deal :") % {"name": comment.author.display_name},
                "",
                deal.title,
                f"« {comment.body[:300]} »",
                "",
                f"{_site()}{deal.get_absolute_url()}#discussion",
            ],
        )
