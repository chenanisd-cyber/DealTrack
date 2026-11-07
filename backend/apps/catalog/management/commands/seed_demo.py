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
from apps.deals.models import (
    Comment,
    CommentTranslation,
    Deal,
    DealStatus,
    DealTranslation,
    Vote,
)
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
    # (nom, pays, indépendant belge, vérifié, TVA, couleur de la vignette)
    # La couleur sert de fond quand une offre n'a pas de photo ; elle
    # s'inspire de l'enseigne sans reproduire son logo (marque déposée).
    ("Coolblue", "BE", False, True, "BE0673617277", "#0090E3"),
    ("Colruyt", "BE", False, True, "BE0400378485", "#E8541E"),
    ("Delhaize", "BE", False, True, "BE0402206045", "#C8102E"),
    ("Krëfel", "BE", False, True, "", "#E30613"),
    ("MediaMarkt", "BE", False, True, "", "#DF0000"),
    ("Proximus", "BE", False, True, "BE0202239951", "#5C2D91"),
    ("Bol.com", "NL", False, True, "", "#0000A4"),
    # Amazon.com.be est exploité par Amazon EU S.à r.l., établie au Luxembourg.
    ("Amazon.com.be", "LU", False, True, "", "#232F3E"),
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
    # ------------------------------------------------------------------
    # Offres réelles relevées le 7 novembre 2026 sur les sites marchands.
    # Les prix évoluent : relancer un relevé avant une démonstration.
    # « reference » = prix barré affiché par le marchand ; pour Amazon, le
    # « prix le plus bas des 30 derniers jours » exigé par l'art. VI.18 CDE.
    # ------------------------------------------------------------------
    dict(
        title='TV Philips Ambilight 43" PUS8001 (2026) à 349 € au lieu de 449 €',
        merchant="Coolblue",
        category="high-tech",
        price="349.00",
        reference="449.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=1124,
        description=(
            "Téléviseur LED 43 pouces avec Ambilight, modèle 2026, choisi par Coolblue "
            "comme TV idéale pour une petite pièce (distance de recul 2 à 2,5 m). "
            "Remise de 22 % sur le prix barré. Livraison le lendemain pour toute "
            "commande passée avant 23 h 59, ou retrait en magasin Coolblue."
        ),
        url="https://www.coolblue.be/fr/produit/981650/philips-ambilight-43-pus8001-2026.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/695138008",
        translations={
            "nl": (
                'Tv Philips Ambilight 43" PUS8001 (2026) voor 349 € in plaats van 449 €',
                "Led-tv van 43 inch met Ambilight, model 2026, door Coolblue gekozen als "
                "ideale tv voor een kleine kamer (kijkafstand 2 tot 2,5 m). 22 % korting "
                "op de doorstreepte prijs. Morgen geleverd bij bestelling voor 23.59 uur, "
                "of afhalen in een Coolblue-winkel.",
            ),
            "de": (
                'TV Philips Ambilight 43" PUS8001 (2026) für 349 € statt 449 €',
                "43-Zoll-LED-Fernseher mit Ambilight, Modell 2026, von Coolblue als "
                "idealer Fernseher für kleine Räume empfohlen (Sitzabstand 2 bis 2,5 m). "
                "22 % Rabatt auf den durchgestrichenen Preis. Lieferung am nächsten Tag "
                "bei Bestellung vor 23:59 Uhr oder Abholung in einer Coolblue-Filiale.",
            ),
        },
    ),
    dict(
        title="Aspirateur balai Dyson V12s Detect Slim Submarine à 419 € au lieu de 599 €",
        merchant="Coolblue",
        category="maison",
        price="419.00",
        reference="599.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=956,
        description=(
            "Aspirateur balai sans fil Dyson V12s Detect Slim avec tête de lavage "
            "Submarine : il aspire et lave les sols durs en un seul passage. 180 € de "
            "remise sur le prix barré, soit -30 %. Vendu et expédié par Coolblue."
        ),
        url="https://www.coolblue.be/fr/produit/983319/dyson-v12s-detect-slim-submarine.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/1202033838",
        translations={
            "nl": (
                "Steelstofzuiger Dyson V12s Detect Slim Submarine voor 419 € in plaats van 599 €",
                "Draadloze steelstofzuiger Dyson V12s Detect Slim met Submarine-dweilkop: "
                "zuigt en dweilt harde vloeren in één beweging. 180 € korting op de "
                "doorstreepte prijs, of -30 %. Verkocht en verzonden door Coolblue.",
            ),
            "de": (
                "Akku-Staubsauger Dyson V12s Detect Slim Submarine für 419 € statt 599 €",
                "Kabelloser Stielstaubsauger Dyson V12s Detect Slim mit Submarine-Nasswischkopf: "
                "saugt und wischt Hartböden in einem Durchgang. 180 € Rabatt auf den "
                "durchgestrichenen Preis, also -30 %. Verkauft und versandt von Coolblue.",
            ),
        },
    ),
    dict(
        title="Robot aspirateur laveur Dreame L40s Pro Ultra à 399 €",
        merchant="Amazon.com.be",
        category="maison",
        price="399.00",
        reference="502.60",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=892,
        cross_border=True,
        description=(
            "Robot aspirateur et laveur avec station, aspiration de 19 000 Pa. Amazon "
            "affiche un prix barré de 899 €, mais le prix de référence légal est le plus "
            "bas des 30 derniers jours : 502,60 €. La vraie remise est donc de 21 %, pas "
            "de 56 %. Vendu et expédié par Amazon.com.be (Amazon EU, Luxembourg)."
        ),
        url="https://www.amazon.com.be/dp/B0DY8V59LY",
        image="https://m.media-amazon.com/images/I/71V6BOrwKnL._AC_SL1500_.jpg",
        translations={
            "nl": (
                "Robotstofzuiger met dweilfunctie Dreame L40s Pro Ultra voor 399 €",
                "Robotstofzuiger en dweilrobot met station, zuigkracht van 19 000 Pa. Amazon "
                "toont een doorstreepte prijs van 899 €, maar de wettelijke referentieprijs is "
                "de laagste prijs van de voorbije 30 dagen: 502,60 €. De echte korting is dus "
                "21 %, geen 56 %. Verkocht en verzonden door Amazon.com.be (Amazon EU, Luxemburg).",
            ),
            "de": (
                "Saug- und Wischroboter Dreame L40s Pro Ultra für 399 €",
                "Saug- und Wischroboter mit Station, Saugleistung 19 000 Pa. Amazon zeigt einen "
                "durchgestrichenen Preis von 899 €, der gesetzliche Referenzpreis ist jedoch der "
                "niedrigste Preis der letzten 30 Tage: 502,60 €. Der echte Rabatt beträgt also "
                "21 %, nicht 56 %. Verkauft und versandt von Amazon.com.be (Amazon EU, Luxemburg).",
            ),
        },
    ),
    dict(
        title="Samsung Galaxy A57 128 Go à 9 € avec un abonnement mobile Proximus",
        merchant="Proximus",
        category="telecom",
        price="9.00",
        reference="549.99",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=640,
        description=(
            "Le smartphone coûte 9 € au lieu de 549,99 €, à condition de prendre un "
            "abonnement mobile avec une option DataPhone pendant 24 mois (par exemple "
            "un abonnement à partir de 15 € avec l'option DataPhone 1,5 GB à 15 €/mois). "
            "Offre valable jusqu'au 3 janvier 2027 pour les nouveaux clients et les "
            "clients GSM existants. Faites le calcul sur deux ans avant de signer."
        ),
        url="https://www.proximus.be/fr/smartphones/samsung/galaxy-a57-5g/128gb/awesome-navy",
        image="",  # pas de photo exploitable : la vignette Proximus s'affiche
        translations={
            "nl": (
                "Samsung Galaxy A57 128 GB voor 9 € met een mobiel abonnement van Proximus",
                "De smartphone kost 9 € in plaats van 549,99 €, op voorwaarde dat je 24 "
                "maanden een mobiel abonnement met een DataPhone-optie neemt (bijvoorbeeld "
                "een abonnement vanaf 15 € met de optie DataPhone 1,5 GB aan 15 €/maand). "
                "Aanbod geldig tot 3 januari 2027 voor nieuwe klanten en bestaande "
                "gsm-klanten. Reken het over twee jaar uit voor je tekent.",
            ),
            "de": (
                "Samsung Galaxy A57 128 GB für 9 € mit einem Proximus-Mobilfunkvertrag",
                "Das Smartphone kostet 9 € statt 549,99 €, sofern man 24 Monate lang einen "
                "Mobilfunkvertrag mit DataPhone-Option abschließt (zum Beispiel einen Tarif "
                "ab 15 € mit der Option DataPhone 1,5 GB für 15 €/Monat). Angebot gültig bis "
                "3. Januar 2027 für Neukunden und bestehende Mobilfunkkunden. Vor der "
                "Unterschrift die Kosten über zwei Jahre berechnen.",
            ),
        },
    ),
    dict(
        title="Chromebook Lenovo IdeaPad Slim 3 14 pouces à 279 € au lieu de 369 €",
        merchant="Coolblue",
        category="high-tech",
        price="279.00",
        reference="369.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=512,
        description=(
            "Chromebook Lenovo IdeaPad Slim 3 de 14 pouces (référence 14M868, clavier "
            "AZERTY). Sous ChromeOS, adapté aux études et à la bureautique en ligne. "
            "90 € de remise sur le prix barré, soit -24 %."
        ),
        url=(
            "https://www.coolblue.be/fr/produit/943117/"
            "lenovo-ideapad-slim-3-chromebook-14m868-82xj0030mb-azerty.html"
        ),
        image="https://image.coolblue.be/transparent/max/380xauto/products/2155323",
        translations={
            "nl": (
                "Chromebook Lenovo IdeaPad Slim 3 14 inch voor 279 € in plaats van 369 €",
                "Chromebook Lenovo IdeaPad Slim 3 van 14 inch (referentie 14M868, "
                "AZERTY-toetsenbord). Met ChromeOS, geschikt voor studie en online kantoorwerk. "
                "90 € korting op de doorstreepte prijs, of -24 %.",
            ),
            "de": (
                "Chromebook Lenovo IdeaPad Slim 3 14 Zoll für 279 € statt 369 €",
                "Chromebook Lenovo IdeaPad Slim 3 mit 14 Zoll (Referenz 14M868, "
                "AZERTY-Tastatur). Mit ChromeOS, geeignet für Studium und Online-Büroarbeit. "
                "90 € Rabatt auf den durchgestrichenen Preis, also -24 %.",
            ),
        },
    ),
    dict(
        title="Lave-linge AEG LF62CB86 ProSense à 499 € au lieu de 599 €",
        merchant="Coolblue",
        category="maison",
        price="499.00",
        reference="599.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=388,
        description=(
            "Machine à laver AEG série 6000 ProSense, qui adapte la durée et la quantité "
            "d'eau au poids du linge. 100 € de remise sur le prix barré, soit -17 %."
        ),
        url="https://www.coolblue.be/fr/produit/967584/aeg-lf62cb86-prosense.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/2215763",
        translations={
            "nl": (
                "Wasmachine AEG LF62CB86 ProSense voor 499 € in plaats van 599 €",
                "Wasmachine AEG 6000-serie ProSense, die de duur en de hoeveelheid water "
                "aanpast aan het gewicht van de was. 100 € korting op de doorstreepte prijs, "
                "of -17 %.",
            ),
            "de": (
                "Waschmaschine AEG LF62CB86 ProSense für 499 € statt 599 €",
                "Waschmaschine AEG Serie 6000 ProSense, die Dauer und Wassermenge an das "
                "Gewicht der Wäsche anpasst. 100 € Rabatt auf den durchgestrichenen Preis, "
                "also -17 %.",
            ),
        },
    ),
    dict(
        title="Myrtilles bleues Delhaize 300 g à 2,99 € au lieu de 5,49 €",
        merchant="Delhaize",
        category="supermarche",
        price="2.99",
        reference="5.49",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=264,
        description=(
            "Barquette de 300 g de myrtilles en promotion dans les magasins Delhaize et "
            "sur la boutique en ligne : 9,97 €/kg au lieu de 18,30 €/kg. Promotion de la "
            "semaine, dans la limite des stocks disponibles."
        ),
        url=(
            "https://www.delhaize.be/fr/shop/Fruits-et-legumes-frais/Fruits-frais/"
            "Fruits-rouges-et-baies/Myrtilles/Myrtilles-Bleues/p/F2024022000131720000"
        ),
        image=(
            "https://static.delhaize.be/medias/sys_master/products/h5a/hbd/"
            "12675488645150.jpg?imwidth=600"
        ),
        translations={
            "nl": (
                "Blauwe bosbessen Delhaize 300 g voor 2,99 € in plaats van 5,49 €",
                "Schaaltje van 300 g bosbessen in promotie in de Delhaize-winkels en in de "
                "webshop: 9,97 €/kg in plaats van 18,30 €/kg. Promotie van de week, zolang "
                "de voorraad strekt.",
            ),
            "de": (
                "Blaubeeren Delhaize 300 g für 2,99 € statt 5,49 €",
                "Schale mit 300 g Heidelbeeren im Angebot in den Delhaize-Filialen und im "
                "Onlineshop: 9,97 €/kg statt 18,30 €/kg. Angebot der Woche, solange der "
                "Vorrat reicht.",
            ),
        },
    ),
    dict(
        title="Jean Levi's 501 Original Fit homme à partir de 50 €",
        merchant="Amazon.com.be",
        category="mode",
        price="50.00",
        reference=None,
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=171,
        cross_border=True,
        description=(
            "Le jean 501 coupe droite d'origine, vendu par Amazon.com.be. Le prix de "
            "50 € vaut pour certaines tailles et couleurs ; Amazon indique un prix "
            "conseillé de 110 €, qui n'est pas un prix de référence au sens de la loi "
            "belge : aucune réduction n'est donc annoncée ici."
        ),
        url="https://www.amazon.com.be/dp/B001GT1WDI",
        image="https://m.media-amazon.com/images/I/81hyY84WRCL._AC_SL1500_.jpg",
        translations={
            "nl": (
                "Jeans Levi's 501 Original Fit heren vanaf 50 €",
                "De originele 501 met rechte pijp, verkocht door Amazon.com.be. De prijs van "
                "50 € geldt voor bepaalde maten en kleuren; Amazon vermeldt een adviesprijs "
                "van 110 €, wat geen referentieprijs is in de zin van de Belgische wet: er "
                "wordt hier dus geen korting aangekondigd.",
            ),
            "de": (
                "Jeans Levi's 501 Original Fit Herren ab 50 €",
                "Die originale 501 mit geradem Schnitt, verkauft von Amazon.com.be. Der Preis "
                "von 50 € gilt für bestimmte Größen und Farben; Amazon nennt eine "
                "unverbindliche Preisempfehlung von 110 €, die kein Referenzpreis im Sinne "
                "des belgischen Rechts ist: Hier wird daher kein Rabatt angekündigt.",
            ),
        },
    ),
    # -- En attente de modération : pour la démonstration du back-office ----
    dict(
        title='PC portable HP OmniBook 3 OLED 16" à 679 € au lieu de 899 €',
        merchant="Coolblue",
        category="high-tech",
        price="679.00",
        reference="899.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PENDING,
        temp=100,
        description=(
            "Ordinateur portable HP OmniBook 3 Next Gen AI PC avec écran OLED de 16 "
            "pouces (référence BZ0031NBX, clavier AZERTY). 220 € de remise sur le prix "
            "barré. En attente de vérification du prix de référence par la modération."
        ),
        url=(
            "https://www.coolblue.be/fr/produit/980471/"
            "hp-omnibook-3-next-gen-ai-pc-oled-16-bz0031nbx-azerty.html"
        ),
        image="https://image.coolblue.be/transparent/max/380xauto/products/1127009865",
    ),
    dict(
        title='TV Samsung LED 85" U8070H (2026) à 999 € au lieu de 1 199 €',
        merchant="Coolblue",
        category="high-tech",
        price="999.00",
        reference="1199.00",
        shipping="0.00",
        regions=["BE1", "BE2", "BE3"],
        lang="fr",
        status=DealStatus.PENDING,
        temp=100,
        description=(
            "Téléviseur LED Samsung de 85 pouces, modèle 2026, pour une distance de "
            "recul de 3,5 à 4 mètres. 200 € de remise sur le prix barré, soit -17 %."
        ),
        url="https://www.coolblue.be/fr/produit/978778/samsung-led-85-u8070h-2026.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/767139863",
    ),
]

COMMENTS = [
    # (texte original en français, achat confirmé, traductions)
    (
        "Commandé hier soir, livré ce midi comme annoncé. Le prix affiché est bien celui du panier, sans code.",
        True,
        {
            "nl": "Gisteravond besteld, vanmiddag geleverd zoals aangekondigd. De getoonde prijs is ook de prijs in het winkelmandje, zonder code.",
            "de": "Gestern Abend bestellt, heute Mittag wie angekündigt geliefert. Der angezeigte Preis ist auch der Preis im Warenkorb, ohne Code.",
        },
    ),
    (
        "Bon plan, mais regardez le prix des 30 derniers jours : la réduction réelle est souvent plus faible que le pourcentage affiché.",
        False,
        {
            "nl": "Goede deal, maar kijk naar de prijs van de voorbije 30 dagen: de echte korting is vaak kleiner dan het getoonde percentage.",
            "de": "Gutes Angebot, aber achtet auf den Preis der letzten 30 Tage: Der echte Rabatt ist oft kleiner als der angezeigte Prozentsatz.",
        },
    ),
    (
        "Stock limité : il n'en restait plus que quelques-uns quand j'ai commandé.",
        False,
        {
            "nl": "Beperkte voorraad: er waren er nog maar een paar toen ik bestelde.",
            "de": "Begrenzter Vorrat: Als ich bestellt habe, waren nur noch wenige übrig.",
        },
    ),
    (
        "Testé le week-end dernier, la qualité est au rendez-vous. Je recommande sans réserve.",
        True,
        {
            "nl": "Vorig weekend getest, de kwaliteit is uitstekend. Ik raad het zonder voorbehoud aan.",
            "de": "Letztes Wochenende getestet, die Qualität stimmt. Ich kann es uneingeschränkt empfehlen.",
        },
    ),
    (
        "J'ai comparé avec deux autres enseignes belges : c'est bien le meilleur prix aujourd'hui.",
        False,
        {
            "nl": "Vergeleken met twee andere Belgische winkels: dit is vandaag echt de beste prijs.",
            "de": "Mit zwei anderen belgischen Händlern verglichen: Das ist heute wirklich der beste Preis.",
        },
    ),
    (
        "Livraison en deux jours ouvrables jusqu'à Liège, emballage soigné.",
        True,
        {
            "nl": "Levering in twee werkdagen tot in Luik, zorgvuldig verpakt.",
            "de": "Lieferung in zwei Werktagen bis nach Lüttich, sorgfältig verpackt.",
        },
    ),
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
        for name, country, local, verified, vat, color in MERCHANTS:
            out[name], _ = Merchant.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "country": country,
                    "vat_number": vat,
                    "is_local_independent": local,
                    "is_verified": verified,
                    "brand_color": color,
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
                    "image_url": spec.get("image", ""),
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
            for body, verified, translations in random.sample(COMMENTS, k=random.randint(1, 3)):
                author = random.choice([m for m in members if m != deal.submitted_by])
                comment, created = Comment.objects.get_or_create(
                    deal=deal,
                    author=author,
                    body=body,
                    defaults={"is_verified_purchase": verified, "language": "fr"},
                )
                count += created
                for language, text in translations.items():
                    CommentTranslation.objects.update_or_create(
                        comment=comment, language=language, defaults={"body": text}
                    )
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
        # Signalements de démonstration sur le jean Levi's : le prix de 50 €
        # ne vaut que pour certaines tailles, un cas typique de modération.
        target = next((d for d in deals if d.external_url.endswith("B001GT1WDI")), None)
        if target is None:
            return
        for member in members[:3]:
            if member == target.submitted_by:
                continue
            Report.objects.get_or_create(
                deal=target,
                reporter=member,
                defaults={
                    "reason": Report.Reason.WRONG_PRICE,
                    "detail": "Le prix de 50 € n'apparaît que pour quelques tailles.",
                },
            )
        self.stdout.write("Signalements : prix à vérifier sur le jean Levi's")

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
