"""
Ajoute des favoris de démonstration à une base déjà remplie.

    python manage.py seed_favorites

Sans effet si la table contient déjà des favoris : ne touche à rien d'autre,
ce qui permet de l'appeler à chaque déploiement.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.deals.models import Deal

from . import _volume


class Command(BaseCommand):
    help = "Crée des favoris de démonstration si la table est vide."

    def handle(self, *args, **options):
        deals = list(Deal.objects.live())
        members = list(User.objects.active().filter(is_staff=False))
        created = _volume.favorites(deals, members)
        self.stdout.write(f"Favoris créés : {created}")
