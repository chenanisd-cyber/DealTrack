"""
Réactions aux écritures du domaine « deals ».

Un commentaire peut être créé par le site ou par l'API : le signal garantit
que l'auteur du deal est prévenu dans les deux cas, sans dupliquer l'appel.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Comment


@receiver(post_save, sender=Comment)
def notify_author_of_new_comment(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.accounts import notifications

    # Après la validation de la transaction : pas d'e-mail pour un
    # commentaire qui serait finalement annulé.
    transaction.on_commit(lambda: notifications.new_comment(instance))
