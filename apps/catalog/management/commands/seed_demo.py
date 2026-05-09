"""
Jeu de données de démonstration.

Enseignes, catégories, prix et régions correspondent au marché belge réel.
Les membres et leurs contributions sont fictifs, mais rédigés comme de vraies
contributions : c'est ce qui permet de juger les écrans sur pièces, ce qu'un
remplissage automatique ne permet pas.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role, User
from apps.catalog.models import Category, CategoryTranslation, Merchant, Region
from apps.deals.models import Comment, Deal, DealStatus, DealTranslation, Vote
from apps.moderation.models import ModerationDecision, Report
from apps.payments.models import Payment, Plan, Subscription

REGIONS = [
    (
        "BE1",
        "Région de Bruxelles-Capitale",
        "Brussels Hoofdstedelijk Gewest",
        "Region Brüssel-Hauptstadt",
    ),
    ("BE2", "Région flamande", "Vlaams Gewest", "Flämische Region"),
    ("BE3", "Région wallonne", "Waals Gewest", "Wallonische Region"),
]

CATEGORIES = [
    ("high-tech", {"fr": "High-tech", "nl": "Elektronica", "de": "Elektronik"}),
    (
        "maison",
        {
            "fr": "Maison & électroménager",
            "nl": "Wonen & huishoudtoestellen",
            "de": "Haushalt & Geräte",
        },
    ),
    (
        "supermarche",
        {
            "fr": "Supermarché & courses",
            "nl": "Supermarkt & boodschappen",
            "de": "Supermarkt & Einkauf",
        },
    ),
    (
        "telecom",
        {"fr": "Télécom & internet", "nl": "Telecom & internet", "de": "Telekom & Internet"},
    ),
    (
        "restauration",
        {
            "fr": "Restaurants & sorties",
            "nl": "Restaurants & uitgaan",
            "de": "Restaurants & Ausgehen",
        },
    ),
    ("mode", {"fr": "Mode", "nl": "Mode", "de": "Mode"}),
]

MERCHANTS = [
    # (nom, pays, indépendant belge, vérifié, TVA)
    ("Coolblue", "BE", False, True, "BE0673617277"),
    ("Colruyt", "BE", False, True, "BE0400378485"),
    ("Delhaize", "BE", False, True, "BE0402206045"),
    ("Krëfel", "BE", False, True, ""),
    ("MediaMarkt", "BE", False, True, ""),
    ("Proximus", "BE", False, True, "BE0202239951"),
    ("Brasserie de Molenbeek", "BE", True, True, ""),
    ("Fromagerie Saint-Aubert", "BE", True, True, ""),
    ("Torréfaction Ostbelgien", "BE", True, False, ""),
    ("Bol.com", "NL", False, True, ""),
    ("Action Maastricht", "NL", False, False, ""),
]

MEMBERS = [
    ("marc.vandenberghe@example.be", "MarcVDB", "fr", "BE3"),
    ("sofie.lievens@example.be", "SofieL", "nl", "BE2"),
    ("amelie.dubois@example.be", "AmelieD", "fr", "BE1"),
    ("jan.willems@example.be", "JanW", "nl", "BE2"),
    ("mathieu.bastin@example.be", "MathieuB", "fr", "BE3"),
    ("karel.dhondt@example.be", "KarelD", "nl", "BE2"),
    ("eline.desmet@example.be", "ElineD", "nl", "BE2"),
    ("nicolas.gerard@example.be", "NicolasG", "de", "BE3"),
]

# Les traductions sont rédigées à la main, pas produites par un moteur : les
# mises en garde concrètes des textes français — plancher de prix, garantie
# réglée depuis Rotterdam, exclusions du bon d'achat — doivent survivre au
# passage d'une langue à l'autre, sans quoi le visiteur néerlandophone lit une
# offre plus alléchante que le francophone. D'où is_machine_translated=False.
DEALS = [
    dict(
        title="Casque Sony WH-1000XM5 à réduction de bruit active, noir ou argent",
        merchant="Coolblue",
        category="high-tech",
        price="249.00",
        reference="349.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=1124,
        description=(
            "Prix le plus bas relevé en Belgique depuis six mois, le précédent plancher "
            "étant de 279 € en juillet. Retrait gratuit en magasin à Anvers, Gand, "
            "Bruxelles et Liège. Le coloris argent affiche un délai plus long que le noir. "
            "La remise n'est pas cumulable avec les bons de bienvenue."
        ),
        url="https://www.coolblue.be/fr/produit/sony-wh-1000xm5",
        translations={
            "nl": (
                "Sony WH-1000XM5 koptelefoon met actieve ruisonderdrukking, zwart of zilver",
                "Laagste prijs in België sinds zes maanden; de vorige bodem lag in juli op "
                "279 €. Gratis afhalen in de winkels van Antwerpen, Gent, Brussel en Luik. "
                "De zilveren uitvoering heeft een langere levertijd dan de zwarte. "
                "De korting is niet cumuleerbaar met welkomstbonnen.",
            ),
            "de": (
                "Sony WH-1000XM5 Kopfhörer mit aktiver Geräuschunterdrückung, schwarz oder silber",
                "Niedrigster Preis in Belgien seit sechs Monaten, der bisherige Tiefstand lag "
                "im Juli bei 279 €. Kostenlose Abholung in den Filialen Antwerpen, Gent, "
                "Brüssel und Lüttich. Die silberne Ausführung hat eine längere Lieferzeit als "
                "die schwarze. Der Rabatt ist nicht mit Willkommensgutscheinen kombinierbar.",
            ),
        },
    ),
    dict(
        title="Internet fibre 1 Gbit/s et mobile 20 Go à 39 €/mois pendant douze mois",
        merchant="Proximus",
        category="telecom",
        price="39.00",
        reference="64.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=892,
        description=(
            "Sans engagement au-delà de douze mois. Les frais d'activation de 59 € sont "
            "remboursés sous forme de crédit sur la deuxième facture. Vérifiez l'éligibilité "
            "fibre de votre rue avant de commander : la couverture reste partielle en zone rurale."
        ),
        url="https://www.proximus.be/fr/internet-fibre",
        translations={
            "nl": (
                "Glasvezel 1 Gbit/s en mobiel 20 GB voor 39 €/maand gedurende twaalf maanden",
                "Geen verbintenis na afloop van de twaalf maanden. De activatiekosten van 59 € "
                "worden als krediet op de tweede factuur terugbetaald. Controleer eerst of uw "
                "straat in aanmerking komt voor glasvezel: op het platteland blijft de dekking "
                "onvolledig.",
            ),
            "de": (
                "Glasfaser 1 Gbit/s und Mobilfunk 20 GB für 39 €/Monat während zwölf Monaten",
                "Keine Bindung über die zwölf Monate hinaus. Die Aktivierungskosten von 59 € "
                "werden als Gutschrift auf der zweiten Rechnung erstattet. Prüfen Sie vor der "
                "Bestellung die Glasfaser-Verfügbarkeit in Ihrer Straße: im ländlichen Raum "
                "bleibt die Abdeckung lückenhaft.",
            ),
        },
    ),
    dict(
        title="Coffret douze bières artisanales et deux verres, brasserie bruxelloise",
        merchant="Brasserie de Molenbeek",
        category="restauration",
        price="24.00",
        reference="32.00",
        shipping="0.00",
        regions=["BE1"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=415,
        description=(
            "Vente directe du producteur, sans intermédiaire. Le coffret change chaque "
            "saison ; celui-ci contient quatre brassins uniquement disponibles sur place. "
            "Retrait à la brasserie ou livraison gratuite dans les dix-neuf communes."
        ),
        url="https://example.be/brasserie-molenbeek/coffret-decouverte",
        translations={
            "nl": (
                "Geschenkpakket met twaalf ambachtelijke bieren en twee glazen, Brusselse brouwerij",
                "Rechtstreekse verkoop door de producent, zonder tussenpersoon. Het pakket "
                "wisselt elk seizoen; dit exemplaar bevat vier brouwsels die enkel ter plaatse "
                "verkrijgbaar zijn. Afhalen in de brouwerij of gratis levering in de negentien "
                "gemeenten.",
            ),
            "de": (
                "Geschenkbox mit zwölf handwerklich gebrauten Bieren und zwei Gläsern, Brüsseler Brauerei",
                "Direktverkauf durch den Erzeuger, ohne Zwischenhändler. Die Box wechselt mit "
                "der Saison; diese hier enthält vier Sude, die es nur vor Ort gibt. Abholung in "
                "der Brauerei oder kostenlose Lieferung in den neunzehn Gemeinden.",
            ),
        },
    ),
    dict(
        title="Lave-linge Bosch Serie 4 huit kilos à 389 € chez Action Maastricht",
        merchant="Action Maastricht",
        category="maison",
        price="389.00",
        reference="649.00",
        shipping="0.00",
        regions=["BE2"],
        # Le texte de base est en français : « lang » désigne la langue de
        # rédaction, pas le marché visé. Le caractère transfrontalier de
        # l'offre est déjà porté par cross_border et par le marchand.
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=372,
        cross_border=True,
        description=(
            "Vingt-deux kilomètres de la frontière limbourgeoise. Garantie européenne valable "
            "en Belgique, mais le service après-vente se règle depuis Rotterdam. Les conditions "
            "de reprise de l'ancien appareil diffèrent de la réglementation belge. "
            "Facture néerlandaise, TVA de 21 % déjà incluse."
        ),
        url="https://example.nl/action-maastricht/bosch-serie-4",
        translations={
            "nl": (
                "Bosch Serie 4 wasmachine van acht kilo voor 389 € bij Action Maastricht",
                "Tweeëntwintig kilometer van de Limburgse grens. De Europese garantie geldt in "
                "België, maar de dienst na verkoop wordt vanuit Rotterdam geregeld. De "
                "voorwaarden voor de terugname van uw oude toestel wijken af van de Belgische "
                "regelgeving. Nederlandse factuur, 21 % btw inbegrepen.",
            ),
            "de": (
                "Bosch Serie 4 Waschmaschine mit acht Kilo für 389 € bei Action Maastricht",
                "Zweiundzwanzig Kilometer von der limburgischen Grenze entfernt. Die "
                "europäische Garantie gilt in Belgien, der Kundendienst wird jedoch von "
                "Rotterdam aus abgewickelt. Die Rücknahmebedingungen für das Altgerät weichen "
                "von der belgischen Regelung ab. Niederländische Rechnung, 21 % Mehrwertsteuer "
                "bereits enthalten.",
            ),
        },
    ),
    dict(
        title="Bon d'achat de quinze euros dès soixante euros d'achat, carte Plus",
        merchant="Delhaize",
        category="supermarche",
        price="0.00",
        reference=None,
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=640,
        description=(
            "Valable une fois par carte Plus, hors tabac, presse, cartes cadeaux et produits "
            "de première nécessité subventionnés. Cumulable avec les promotions du prospectus "
            "de la semaine. Le bon s'active depuis l'application avant le passage en caisse."
        ),
        url="https://www.delhaize.be/fr/promotions",
        translations={
            "nl": (
                "Waardebon van vijftien euro vanaf zestig euro aankoop, met de Plus-kaart",
                "Eén keer geldig per Plus-kaart, uitgezonderd tabak, pers, cadeaukaarten en "
                "gesubsidieerde basisproducten. Combineerbaar met de promoties uit het "
                "weekfolder. De bon wordt in de app geactiveerd vóór het afrekenen aan de kassa.",
            ),
            "de": (
                "Einkaufsgutschein über fünfzehn Euro ab sechzig Euro Einkauf, mit der Plus-Karte",
                "Einmal pro Plus-Karte gültig, ausgenommen Tabak, Presseerzeugnisse, "
                "Geschenkkarten und subventionierte Grundnahrungsmittel. Mit den Aktionen des "
                "Wochenprospekts kombinierbar. Der Gutschein wird vor dem Bezahlen an der Kasse "
                "in der App aktiviert.",
            ),
        },
    ),
    dict(
        title="Machine à café Philips Series 2200 avec broyeur intégré et mousseur",
        merchant="Krëfel",
        category="maison",
        price="199.00",
        reference="299.00",
        shipping="0.00",
        regions=["BE1", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=287,
        description=(
            "Broyeur céramique réglable sur douze finesses. Le mousseur classique demande un "
            "peu de pratique par rapport à un LatteGo. Deux ans de garantie légale belge, "
            "extensible à cinq ans moyennant supplément en caisse."
        ),
        url="https://www.krefel.be/fr/philips-series-2200",
        translations={
            "nl": (
                "Philips Series 2200 espressomachine met ingebouwde molen en melkopschuimer",
                "Keramische molen, instelbaar op twaalf maalgraden. De klassieke opschuimer "
                "vraagt wat oefening in vergelijking met een LatteGo. Twee jaar Belgische "
                "wettelijke garantie, aan de kassa tegen bijbetaling uit te breiden tot vijf jaar.",
            ),
            "de": (
                "Philips Series 2200 Kaffeevollautomat mit integriertem Mahlwerk und Milchaufschäumer",
                "Keramikmahlwerk mit zwölf einstellbaren Mahlgraden. Der klassische "
                "Aufschäumer erfordert im Vergleich zu einem LatteGo etwas Übung. Zwei Jahre "
                "gesetzliche belgische Garantie, an der Kasse gegen Aufpreis auf fünf Jahre "
                "erweiterbar.",
            ),
        },
    ),
    dict(
        title="Café de spécialité torréfié en Ostbelgien, trois paquets de deux cent cinquante grammes",
        merchant="Torréfaction Ostbelgien",
        category="restauration",
        price="27.00",
        reference="36.00",
        shipping="4.50",
        regions=["BE3"],
        lang="de",
        status=DealStatus.PENDING,
        temp=100,
        description=(
            "Torréfaction artisanale à Eupen, grains d'origine unique du Rwanda et du Honduras. "
            "Torréfié à la commande, expédié sous quarante-huit heures. Trois paquets au choix "
            "parmi cinq références disponibles sur le site du torréfacteur."
        ),
        url="https://example.be/torrefaction-ostbelgien/decouverte",
    ),
    dict(
        title="Trottinette électrique Xiaomi 4 Pro, autonomie cinquante-cinq kilomètres",
        merchant="MediaMarkt",
        category="high-tech",
        price="349.00",
        reference="549.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.EXPIRED,
        temp=210,
        description=(
            "Rupture de stock signalée par quatre membres deux jours après la publication. "
            "L'offre reste consultable pour l'historique des prix. Rappel : depuis 2022, la "
            "trottinette est interdite aux moins de seize ans sur la voie publique en Belgique."
        ),
        url="https://www.mediamarkt.be/fr/product/xiaomi-4-pro",
    ),
    dict(
        title="Meules de fromage d'abbaye affinées vingt-quatre mois, lot de deux",
        merchant="Fromagerie Saint-Aubert",
        category="supermarche",
        price="32.00",
        reference="44.00",
        shipping="6.00",
        regions=["BE3"],
        lang="fr",
        status=DealStatus.PENDING,
        temp=100,
        description=(
            "Affinage en cave par un maître fromager de la région de Namur. Expédition sous "
            "emballage isotherme du lundi au mercredi uniquement, pour éviter un week-end en "
            "transit. Poids total d'environ un kilo deux cents."
        ),
        url="https://example.be/fromagerie-saint-aubert/abbaye-24-mois",
    ),
    dict(
        title="Chaussures de marche Salomon X Ultra 4 GTX, pointures 40 à 46",
        merchant="Bol.com",
        category="mode",
        price="89.00",
        reference="159.00",
        shipping="0.00",
        regions=["BE2"],
        lang="fr",  # texte de base français, cf. le deal Action Maastricht
        status=DealStatus.PUBLISHED,
        temp=318,
        cross_border=True,
        description=(
            "Membrane Gore-Tex, semelle Contagrip. Taille petit d'une demi-pointure d'après "
            "les retours des membres. Expédié depuis les Pays-Bas, retour gratuit sous trente "
            "jours mais le colis part vers Utrecht."
        ),
        url="https://www.bol.com/be/nl/p/salomon-x-ultra-4-gtx",
        translations={
            "nl": (
                "Salomon X Ultra 4 GTX wandelschoenen, maten 40 tot 46",
                "Gore-Tex-membraan, Contagrip-zool. Volgens de reacties van de leden valt de "
                "schoen een halve maat te klein uit. Verzending vanuit Nederland, gratis retour "
                "binnen dertig dagen, maar het pakket vertrekt richting Utrecht.",
            ),
            "de": (
                "Salomon X Ultra 4 GTX Wanderschuhe, Größen 40 bis 46",
                "Gore-Tex-Membran, Contagrip-Sohle. Nach den Rückmeldungen der Mitglieder "
                "fällt der Schuh eine halbe Nummer kleiner aus. Versand aus den Niederlanden, "
                "kostenlose Rücksendung innerhalb von dreißig Tagen, das Paket geht allerdings "
                "nach Utrecht.",
            ),
        },
    ),
]

COMMENTS = [
    (
        "Commandé ce matin, retrait à Gand dans l'heure. Le prix passe bien à 249 € au panier sans code.",
        True,
    ),
    (
        "Attention, chez le même marchand aux Pays-Bas il est dix euros moins cher, mais la garantie se règle depuis Rotterdam.",
        False,
    ),
    ("Stock épuisé sur Bruxelles depuis midi. Le noir reste disponible en ligne.", False),
    (
        "Testé le week-end dernier, la qualité est au rendez-vous. Je recommande sans réserve.",
        True,
    ),
    (
        "Le prix de référence me semble optimiste, je l'ai vu à 299 € il y a trois semaines chez un concurrent.",
        False,
    ),
    ("Livraison en deux jours ouvrables jusqu'à Liège, emballage soigné.", True),
]


class Command(BaseCommand):
    help = "Charge un jeu de données de démonstration réaliste."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true", help="Vide les tables métier avant."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20251117)  # reproductible d'une exécution à l'autre

        if options["flush"]:
            self._flush()

        regions = self._regions()
        categories = self._categories()
        merchants = self._merchants()
        staff, members = self._users(regions)
        deals = self._deals(merchants, categories, regions, members, staff)
        self._votes(deals, members + staff)
        self._comments(deals, members)
        self._payments(members)
        self._reports(deals, members)

        self.stdout.write(self.style.SUCCESS("\nJeu de démonstration chargé."))
        self._summary()

    # ------------------------------------------------------------------
    def _flush(self):
        for model in (
            Report,
            ModerationDecision,
            Subscription,
            Payment,
            Vote,
            Comment,
            DealTranslation,
            Deal,
            Merchant,
            CategoryTranslation,
            Category,
        ):
            model.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("Tables métier vidées.")

    def _regions(self):
        out = {}
        for code, fr, nl, de in REGIONS:
            out[code], _ = Region.objects.update_or_create(
                code=code, defaults={"name_fr": fr, "name_nl": nl, "name_de": de}
            )
        self.stdout.write(f"Régions : {len(out)}")
        return out

    def _categories(self):
        out = {}
        for position, (slug, labels) in enumerate(CATEGORIES):
            category, _ = Category.objects.update_or_create(
                slug=slug, defaults={"position": position, "is_active": True}
            )
            for lang, name in labels.items():
                CategoryTranslation.objects.update_or_create(
                    category=category, language=lang, defaults={"name": name}
                )
            out[slug] = category
        self.stdout.write(f"Catégories : {len(out)} × 3 langues")
        return out

    def _merchants(self):
        out = {}
        for name, country, local, verified, vat in MERCHANTS:
            out[name], _ = Merchant.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "country": country,
                    "vat_number": vat,
                    "is_local_independent": local,
                    "is_verified": verified,
                    "website": f"https://example.{country.lower()}/{slugify(name)}",
                },
            )
        self.stdout.write(f"Marchands : {len(out)}")
        return out

    def _users(self, regions):
        # Mot de passe commun aux comptes de démonstration : il satisfait la
        # politique (12 caractères, trois classes, pas de suite de touches).
        password = "Demo-Tracker-2025"

        admin, created = User.objects.get_or_create(
            email="admin@dealtrack.be",
            defaults={
                "display_name": "AdminDT",
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "accepted_terms_at": timezone.now(),
            },
        )
        if created:
            admin.set_password(password)
            admin.save()

        moderator, created = User.objects.get_or_create(
            email="moderation@dealtrack.be",
            defaults={
                "display_name": "ModeratriceBE",
                "role": Role.MODERATOR,
                "is_staff": True,
                "accepted_terms_at": timezone.now(),
            },
        )
        if created:
            moderator.set_password(password)
            moderator.save()

        members = []
        for email, name, lang, region_code in MEMBERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": name,
                    "preferred_language": lang,
                    "home_region": regions[region_code],
                    "role": Role.MEMBER,
                    "accepted_terms_at": timezone.now()
                    - timedelta(days=random.randint(60, 900)),
                    "marketing_consent": random.choice([True, False]),
                    "date_joined": timezone.now() - timedelta(days=random.randint(60, 900)),
                },
            )
            if created:
                user.set_password(password)
                user.save()
            members.append(user)

        self.stdout.write(f"Comptes : 1 admin, 1 modérateur, {len(members)} membres")
        return [admin, moderator], members

    def _deals(self, merchants, categories, regions, members, staff):
        created = []
        now = timezone.now()
        for index, spec in enumerate(DEALS):
            author = members[index % len(members)]
            published = (
                now - timedelta(hours=random.randint(2, 240))
                if spec["status"] in (DealStatus.PUBLISHED, DealStatus.EXPIRED)
                else None
            )
            deal, _ = Deal.objects.update_or_create(
                slug=slugify(spec["title"])[:150],
                defaults={
                    "title": spec["title"],
                    "description": spec["description"],
                    "external_url": spec["url"],
                    "price": Decimal(spec["price"]),
                    "reference_price": Decimal(spec["reference"])
                    if spec["reference"]
                    else None,
                    "shipping_cost": Decimal(spec["shipping"]),
                    "merchant": merchants[spec["merchant"]],
                    "category": categories[spec["category"]],
                    "submitted_by": author,
                    "status": spec["status"],
                    "language": spec["lang"],
                    "is_cross_border": spec.get("cross_border", False),
                    "temperature": spec["temp"],
                    "published_at": published,
                    "starts_at": published or now,
                    "ends_at": now - timedelta(hours=2)
                    if spec["status"] == DealStatus.EXPIRED
                    else None,
                },
            )
            deal.regions.set([regions[c] for c in spec["regions"]])

            for language, (title, description) in spec.get("translations", {}).items():
                DealTranslation.objects.update_or_create(
                    deal=deal,
                    language=language,
                    defaults={
                        "title": title,
                        "description": description,
                        "is_machine_translated": False,
                    },
                )
            created.append(deal)

            if spec["status"] == DealStatus.PUBLISHED:
                ModerationDecision.objects.get_or_create(
                    deal=deal,
                    moderator=staff[1],
                    defaults={
                        "decision": ModerationDecision.Decision.APPROVED,
                        "reason": "Lien et prix de référence contrôlés.",
                    },
                )
        self.stdout.write(
            f"Deals : {len(created)}, dont {sum(1 for s in DEALS if s.get('translations'))} "
            "traduits en néerlandais et en allemand"
        )
        return created

    def _votes(self, deals, voters):
        count = 0
        for deal in deals:
            if deal.status != DealStatus.PUBLISHED:
                continue
            for voter in random.sample(voters, k=random.randint(3, min(7, len(voters)))):
                if voter == deal.submitted_by:
                    continue
                _, created = Vote.objects.get_or_create(
                    deal=deal,
                    user=voter,
                    defaults={"value": random.choices([1, -1], weights=[85, 15])[0]},
                )
                count += int(created)
        self.stdout.write(f"Votes : {count}")

    def _comments(self, deals, members):
        count = 0
        for deal in deals:
            if deal.status != DealStatus.PUBLISHED:
                continue
            for body, verified in random.sample(COMMENTS, k=random.randint(1, 3)):
                author = random.choice([m for m in members if m != deal.submitted_by])
                if Comment.objects.filter(deal=deal, author=author, body=body).exists():
                    continue
                Comment.objects.create(
                    deal=deal,
                    author=author,
                    body=body,
                    is_verified_purchase=verified,
                )
                count += 1
        self.stdout.write(f"Commentaires : {count}")

    def _payments(self, members):
        plan, _ = Plan.objects.update_or_create(
            code="club-annuel",
            defaults={
                "name_fr": "Club annuel",
                "name_nl": "Club jaarlijks",
                "name_de": "Club jährlich",
                "price": Decimal("24.00"),
                "vat_rate": Decimal("21.00"),
                "duration_days": 365,
                "is_active": True,
            },
        )
        Plan.objects.update_or_create(
            code="club-mensuel",
            defaults={
                "name_fr": "Club mensuel",
                "name_nl": "Club maandelijks",
                "name_de": "Club monatlich",
                "price": Decimal("2.50"),
                "vat_rate": Decimal("21.00"),
                "duration_days": 30,
                "is_active": True,
            },
        )

        count = 0
        for member in members[:4]:
            if Payment.objects.filter(user=member).exists():
                continue
            settled = timezone.now() - timedelta(days=random.randint(10, 300))
            payment = Payment.objects.create(
                reference=Payment.next_reference(),
                user=member,
                plan=plan,
                amount=plan.price,
                vat_amount=(plan.price * plan.vat_rate / (100 + plan.vat_rate)).quantize(
                    Decimal("0.01")
                ),
                status=Payment.Status.SUCCEEDED,
                gateway="sandbox",
                gateway_reference=f"sbx_seed_{member.display_name.lower()}",
                card_brand="visa",
                card_last4="4242",
                settled_at=settled,
            )
            Subscription.objects.create(
                user=member,
                plan=plan,
                payment=payment,
                started_at=settled,
                ends_at=settled + timedelta(days=plan.duration_days),
            )
            count += 1
        self.stdout.write(f"Paiements et abonnements : {count}")

    def _reports(self, deals, members):
        expired = [d for d in deals if d.status == DealStatus.EXPIRED]
        if not expired:
            return
        target = expired[0]
        for member in members[:3]:
            Report.objects.get_or_create(
                deal=target,
                reporter=member,
                defaults={
                    "reason": Report.Reason.OUT_OF_STOCK,
                    "detail": "Plus aucun stock en magasin ni en ligne depuis ce matin.",
                },
            )
        self.stdout.write("Signalements : 3")

    def _summary(self):
        rows = [
            ("Régions", Region.objects.count()),
            ("Catégories", Category.objects.count()),
            ("Libellés traduits", CategoryTranslation.objects.count()),
            ("Marchands", Merchant.objects.count()),
            ("Utilisateurs", User.objects.count()),
            ("Deals", Deal.objects.count()),
            ("  dont publiés", Deal.objects.filter(status=DealStatus.PUBLISHED).count()),
            ("  dont en attente", Deal.objects.filter(status=DealStatus.PENDING).count()),
            ("Traductions de deals", DealTranslation.objects.count()),
            ("Votes", Vote.objects.count()),
            ("Commentaires", Comment.objects.count()),
            ("Formules", Plan.objects.count()),
            ("Paiements", Payment.objects.count()),
            ("Abonnements", Subscription.objects.count()),
            ("Signalements", Report.objects.count()),
        ]
        self.stdout.write("")
        for label, value in rows:
            self.stdout.write(f"  {label:.<28} {value}")
        self.stdout.write(
            "\n  Connexion : admin@dealtrack.be / moderation@dealtrack.be / "
            "marc.vandenberghe@example.be"
        )
        self.stdout.write("  Mot de passe commun : Demo-Tracker-2025\n")
