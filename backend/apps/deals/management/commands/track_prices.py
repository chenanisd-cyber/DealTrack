"""
Suivi automatique des prix (historique VIP).

    python manage.py track_prices              # à planifier une fois par jour
    python manage.py track_prices --limit 20

Relit la page de chaque deal publié et ajoute un point d'historique si le prix
a changé. Les sites qui bloquent la lecture automatique (Coolblue, bol.com)
ne sont pas contournés : leurs deals gardent les prix relevés à la publication
et lors des modifications.
"""

import time

from django.core.management.base import BaseCommand

from apps.deals.models import Deal, PricePoint
from apps.deals.scraper import fetch_deal_info, parse_price
from apps.deals.vip import record_price


class Command(BaseCommand):
    help = "Relit les pages des deals publiés et enregistre les changements de prix."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--pause", type=float, default=2.0, help="Secondes entre deux pages."
        )

    def handle(self, *args, limit, pause, **options):
        deals = Deal.objects.live().exclude(external_url="").order_by("-published_at")[:limit]
        checked = changed = skipped = 0
        for deal in deals:
            info = fetch_deal_info(deal.external_url)
            price = parse_price(info.get("price")) if info.get("success") else None
            if price is None:
                skipped += 1
                continue
            checked += 1
            if price != deal.price:
                deal.price = price
                Deal.objects.filter(pk=deal.pk).update(price=price)
                record_price(deal, source=PricePoint.Source.TRACKER)
                changed += 1
                self.stdout.write(f"  {deal.title[:60]} → {price} €")
            time.sleep(pause)  # politesse envers les sites lus
        self.stdout.write(
            self.style.SUCCESS(
                f"{checked} prix relus, {changed} changement(s), "
                f"{skipped} page(s) non lisible(s)."
            )
        )
