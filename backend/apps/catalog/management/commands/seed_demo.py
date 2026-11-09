"""
Jeu de données de démonstration.

Enseignes, catégories et prix correspondent au marché belge réel.
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
from apps.catalog.models import Category, CategoryTranslation, Merchant
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

from . import _volume

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

# Site officiel de chaque enseigne : sert à reconnaître le marchand quand un
# membre colle un lien dans le formulaire de publication.
MERCHANT_WEBSITES = {
    "Coolblue": "https://www.coolblue.be",
    "Colruyt": "https://www.colruyt.be",
    "Delhaize": "https://www.delhaize.be",
    "Krëfel": "https://www.krefel.be",
    "MediaMarkt": "https://www.mediamarkt.be",
    "Proximus": "https://www.proximus.be",
    "Bol.com": "https://www.bol.com",
    "Amazon.com.be": "https://www.amazon.com.be",
}

# Commerçants indépendants réels, extraits d'OpenStreetMap le 7 novembre 2026
# (données © les contributeurs OpenStreetMap, licence ODbL). Pour en ajouter :
#   python manage.py import_local_merchants --area "Gent"
# (osm_id, nom, type OSM, adresse, ville, latitude, longitude, site web)
LOCAL_MERCHANTS = [
    (
        1403028749,
        "Tropismes",
        "books",
        "",
        "Bruxelles",
        "50.848174",
        "4.354839",
        "https://www.tropismes.com/",
    ),
    (
        3885939395,
        "Passa Porta Bookshop",
        "books",
        "",
        "Bruxelles",
        "50.849439",
        "4.346492",
        "https://www.passaportabookshop.be/",
    ),
    (
        3885979057,
        "Le Wolf",
        "books",
        "",
        "Bruxelles",
        "50.845544",
        "4.352185",
        "https://www.lewolf.be/",
    ),
    (
        2385585705,
        "Piola Libri",
        "books",
        "",
        "Bruxelles",
        "50.845606",
        "4.387061",
        "https://piolalibri.be/",
    ),
    (
        2514211688,
        "Chocolatier Gerbaud",
        "chocolate",
        "",
        "Bruxelles",
        "50.844094",
        "4.358769",
        "https://chocolatsgerbaud.be",
    ),
    (
        2665166201,
        "Cave 1929",
        "wine",
        "",
        "Bruxelles",
        "50.841816",
        "4.353439",
        "https://www.cave1929.be/",
    ),
    (
        2594805954,
        "Coureur",
        "bicycle",
        "",
        "Bruxelles",
        "50.848247",
        "4.344099",
        "https://www.coureur.brussels/",
    ),
    (
        2387949125,
        "Morning Cycles",
        "bicycle",
        "",
        "Bruxelles",
        "50.847005",
        "4.388389",
        "https://morningcycles.com/",
    ),
    (
        2225073582,
        "Hinkelspel",
        "cheese",
        "Ferdinand Lousbergskaai 33, 9000 Gent",
        "Gent",
        "51.050155",
        "3.738078",
        "https://www.hethinkelspel.be/",
    ),
    (
        1314094556,
        "Bakkerij Martens",
        "bakery",
        "Oudburg 74, 9000 Gent",
        "Gent",
        "51.058876",
        "3.724802",
        "https://www.martens-gent.be/",
    ),
    (
        1532805919,
        "Bakkerij Aernoudt",
        "bakery",
        "Kortemunt 1, Gent",
        "Gent",
        "51.055611",
        "3.722320",
        "https://bakkerijaernoudt.be/",
    ),
    (
        1295215428,
        "De Gentsche Koekedoos",
        "bakery",
        "Goudstraat 31, 9000 Gent",
        "Gent",
        "51.059721",
        "3.727789",
        "",
    ),
    (
        311986274,
        "Eriks Fietsateljee",
        "bicycle",
        "Kolegemkouter 10, Gent",
        "Gent",
        "51.078223",
        "3.702254",
        "https://www.eriksfietsateljee.com/",
    ),
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
    ("marc.vandenberghe@example.be", "MarcVDB", "fr"),
    ("sofie.lievens@example.be", "SofieL", "nl"),
    ("amelie.dubois@example.be", "AmelieD", "fr"),
    ("jan.willems@example.be", "JanW", "nl"),
    ("mathieu.bastin@example.be", "MathieuB", "fr"),
    ("karel.dhondt@example.be", "KarelD", "nl"),
    ("eline.desmet@example.be", "ElineD", "nl"),
    ("nicolas.gerard@example.be", "NicolasG", "de"),
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
    # -- Deuxième relevé, même jour ----------------------------------------
    dict(
        title='TV TCL QD Mini-LED 55" C69K Pro (2026) à 599 € au lieu de 699 €',
        merchant="Coolblue",
        category="high-tech",
        price="599.00",
        reference="699.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=734,
        description=(
            "Téléviseur Mini-LED de 55 pouces, modèle 2026, noté 9,6/10 par les clients "
            "Coolblue. Distance de recul conseillée : 2,5 à 3 mètres. 100 € de remise "
            "sur le prix barré, soit -14 %."
        ),
        url="https://www.coolblue.be/fr/produit/978460/tcl-qd-mini-led-55-c69k-pro-2026.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/617174214",
        translations={
            "nl": (
                'Tv TCL QD Mini-LED 55" C69K Pro (2026) voor 599 € in plaats van 699 €',
                "Mini-led-tv van 55 inch, model 2026, door Coolblue-klanten beoordeeld met "
                "9,6/10. Aanbevolen kijkafstand: 2,5 tot 3 meter. 100 € korting op de "
                "doorstreepte prijs, of -14 %.",
            ),
            "de": (
                'TV TCL QD Mini-LED 55" C69K Pro (2026) für 599 € statt 699 €',
                "Mini-LED-Fernseher mit 55 Zoll, Modell 2026, von Coolblue-Kunden mit 9,6/10 "
                "bewertet. Empfohlener Sitzabstand: 2,5 bis 3 Meter. 100 € Rabatt auf den "
                "durchgestrichenen Preis, also -14 %.",
            ),
        },
    ),
    dict(
        title='TV Philips Ambilight 50" PQS9001 QLED (2026) à 699 € au lieu de 899 €',
        merchant="Coolblue",
        category="high-tech",
        price="699.00",
        reference="899.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=468,
        description=(
            "Téléviseur QLED de 50 pouces avec Ambilight et dalle 100 Hz, modèle 2026. "
            "200 € de remise sur le prix barré, soit -22 %."
        ),
        url="https://www.coolblue.be/fr/produit/981660/philips-ambilight-50-pqs9001-2026.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/854998982",
        translations={
            "nl": (
                'Tv Philips Ambilight 50" PQS9001 QLED (2026) voor 699 € in plaats van 899 €',
                "QLED-tv van 50 inch met Ambilight en 100 Hz-scherm, model 2026. 200 € "
                "korting op de doorstreepte prijs, of -22 %.",
            ),
            "de": (
                'TV Philips Ambilight 50" PQS9001 QLED (2026) für 699 € statt 899 €',
                "QLED-Fernseher mit 50 Zoll, Ambilight und 100-Hz-Panel, Modell 2026. 200 € "
                "Rabatt auf den durchgestrichenen Preis, also -22 %.",
            ),
        },
    ),
    dict(
        title='TV Samsung LED 50" U8070H (2026) à 399 € au lieu de 469 €',
        merchant="Coolblue",
        category="high-tech",
        price="399.00",
        reference="469.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=301,
        description=(
            "Téléviseur LED Samsung de 50 pouces, modèle 2026, pour une distance de "
            "recul de 2,5 mètres. 70 € de remise sur le prix barré, soit -15 %."
        ),
        url="https://www.coolblue.be/fr/produit/978774/samsung-led-50-u8070h-2026.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/1986163679",
        translations={
            "nl": (
                'Tv Samsung LED 50" U8070H (2026) voor 399 € in plaats van 469 €',
                "Led-tv van Samsung van 50 inch, model 2026, voor een kijkafstand van 2,5 "
                "meter. 70 € korting op de doorstreepte prijs, of -15 %.",
            ),
            "de": (
                'TV Samsung LED 50" U8070H (2026) für 399 € statt 469 €',
                "LED-Fernseher von Samsung mit 50 Zoll, Modell 2026, für 2,5 Meter "
                "Sitzabstand. 70 € Rabatt auf den durchgestrichenen Preis, also -15 %.",
            ),
        },
    ),
    dict(
        title="Aspirateur sans fil Rowenta X-Force Flex 14.60 à 350 € au lieu de 482 €",
        merchant="Coolblue",
        category="maison",
        price="350.00",
        reference="482.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=287,
        description=(
            "Aspirateur balai sans fil Rowenta X-Force Flex 14.60 (référence RH99C3), "
            "avec tube flexible pour passer sous les meubles. 132 € de remise sur le "
            "prix barré, soit -27 %."
        ),
        url="https://www.coolblue.be/fr/produit/939623/rowenta-x-force-flex-14-60-rh99c3.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/1983543",
        translations={
            "nl": (
                "Draadloze stofzuiger Rowenta X-Force Flex 14.60 voor 350 € in plaats van 482 €",
                "Draadloze steelstofzuiger Rowenta X-Force Flex 14.60 (referentie RH99C3), "
                "met flexibele buis om onder meubels te zuigen. 132 € korting op de "
                "doorstreepte prijs, of -27 %.",
            ),
            "de": (
                "Akku-Staubsauger Rowenta X-Force Flex 14.60 für 350 € statt 482 €",
                "Kabelloser Stielstaubsauger Rowenta X-Force Flex 14.60 (Referenz RH99C3) "
                "mit flexiblem Rohr für die Reinigung unter Möbeln. 132 € Rabatt auf den "
                "durchgestrichenen Preis, also -27 %.",
            ),
        },
    ),
    dict(
        title="Lave-linge Samsung Bespoke WW11DB7B34GBU3 à 679 € au lieu de 829 €",
        merchant="Coolblue",
        category="maison",
        price="679.00",
        reference="829.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=244,
        description=(
            "Machine à laver Samsung Bespoke Super Speed (référence WW11DB7B34GBU3). "
            "150 € de remise sur le prix barré, et Coolblue signale une promotion "
            "« lessive offerte » sur ce modèle : conditions sur la page du produit."
        ),
        url=(
            "https://www.coolblue.be/fr/produit/946999/"
            "samsung-ww11db7b34gbu3-bespoke-super-speed.html"
        ),
        image="https://image.coolblue.be/transparent/max/380xauto/products/2040306",
        translations={
            "nl": (
                "Wasmachine Samsung Bespoke WW11DB7B34GBU3 voor 679 € in plaats van 829 €",
                "Wasmachine Samsung Bespoke Super Speed (referentie WW11DB7B34GBU3). 150 € "
                "korting op de doorstreepte prijs, en Coolblue vermeldt een actie "
                "« gratis wasmiddel » op dit model: voorwaarden op de productpagina.",
            ),
            "de": (
                "Waschmaschine Samsung Bespoke WW11DB7B34GBU3 für 679 € statt 829 €",
                "Waschmaschine Samsung Bespoke Super Speed (Referenz WW11DB7B34GBU3). 150 € "
                "Rabatt auf den durchgestrichenen Preis, und Coolblue nennt eine Aktion "
                "„Waschmittel gratis“ für dieses Modell: Bedingungen auf der Produktseite.",
            ),
        },
    ),
    dict(
        title="Lave-linge Bosch WAN2827YFG Iron Assist à 529 € au lieu de 614 €",
        merchant="Coolblue",
        category="maison",
        price="529.00",
        reference="614.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=196,
        description=(
            "Machine à laver Bosch série 4 avec fonction Iron Assist, qui réduit les plis "
            "à la vapeur. 85 € de remise sur le prix barré, soit -14 %."
        ),
        url="https://www.coolblue.be/fr/produit/972640/bosch-wan2827yfg-iron-assist.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/1716363506",
        translations={
            "nl": (
                "Wasmachine Bosch WAN2827YFG Iron Assist voor 529 € in plaats van 614 €",
                "Wasmachine Bosch serie 4 met Iron Assist, die kreuken met stoom vermindert. "
                "85 € korting op de doorstreepte prijs, of -14 %.",
            ),
            "de": (
                "Waschmaschine Bosch WAN2827YFG Iron Assist für 529 € statt 614 €",
                "Waschmaschine Bosch Serie 4 mit Iron Assist, das Falten mit Dampf reduziert. "
                "85 € Rabatt auf den durchgestrichenen Preis, also -14 %.",
            ),
        },
    ),
    dict(
        title="PC portable HP Laptop 14-em0957nb à 649 € au lieu de 739 €",
        merchant="Coolblue",
        category="high-tech",
        price="649.00",
        reference="739.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=158,
        description=(
            "Ordinateur portable HP de 14 pouces (référence 14-em0957nb, clavier "
            "AZERTY). 90 € de remise sur le prix barré, soit -12 %."
        ),
        url="https://www.coolblue.be/fr/produit/962795/hp-laptop-14-em0957nb-azerty.html",
        image="https://image.coolblue.be/transparent/max/380xauto/products/2238621",
        translations={
            "nl": (
                "Laptop HP 14-em0957nb voor 649 € in plaats van 739 €",
                "HP-laptop van 14 inch (referentie 14-em0957nb, AZERTY-toetsenbord). 90 € "
                "korting op de doorstreepte prijs, of -12 %.",
            ),
            "de": (
                "Notebook HP Laptop 14-em0957nb für 649 € statt 739 €",
                "HP-Notebook mit 14 Zoll (Referenz 14-em0957nb, AZERTY-Tastatur). 90 € "
                "Rabatt auf den durchgestrichenen Preis, also -12 %.",
            ),
        },
    ),
    dict(
        title="Robot aspirateur laveur Dreame L50s Pro Ultra-A à 499 €",
        merchant="Amazon.com.be",
        category="maison",
        price="499.00",
        reference="579.00",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=421,
        cross_border=True,
        description=(
            "Robot aspirateur laveur avec serpillière auto-nettoyante à 100 °C. Prix de "
            "référence légal (plus bas des 30 derniers jours) : 579 €, soit 14 % de "
            "remise réelle. Vendu et expédié par Amazon.com.be."
        ),
        url="https://www.amazon.com.be/dp/B0H2F5YPTN",
        image="https://m.media-amazon.com/images/I/61FmvnlvLZL._AC_SL1500_.jpg",
        translations={
            "nl": (
                "Robotstofzuiger met dweilfunctie Dreame L50s Pro Ultra-A voor 499 €",
                "Robotstofzuiger met zelfreinigende dweil op 100 °C. Wettelijke "
                "referentieprijs (laagste van de voorbije 30 dagen): 579 €, dus 14 % echte "
                "korting. Verkocht en verzonden door Amazon.com.be.",
            ),
            "de": (
                "Saug- und Wischroboter Dreame L50s Pro Ultra-A für 499 €",
                "Saug- und Wischroboter mit selbstreinigendem Wischmopp bei 100 °C. "
                "Gesetzlicher Referenzpreis (niedrigster der letzten 30 Tage): 579 €, also "
                "14 % echter Rabatt. Verkauft und versandt von Amazon.com.be.",
            ),
        },
    ),
    dict(
        title="Robot aspirateur laveur roborock Qrevo S Pro à 329,99 €",
        merchant="Amazon.com.be",
        category="maison",
        price="329.99",
        reference="379.99",
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=217,
        cross_border=True,
        description=(
            "Robot aspirateur laveur 18 500 Pa avec brosse anti-enchevêtrement, vendu "
            "par la boutique officielle Roborock sur Amazon.com.be. Prix de référence "
            "légal (plus bas des 30 derniers jours) : 379,99 €."
        ),
        url="https://www.amazon.com.be/dp/B0GHN39ZGJ",
        image="https://m.media-amazon.com/images/I/61faWSZ6LXL._AC_SL1500_.jpg",
        translations={
            "nl": (
                "Robotstofzuiger met dweilfunctie roborock Qrevo S Pro voor 329,99 €",
                "Robotstofzuiger met dweilfunctie, 18 500 Pa en anti-klitborstel, verkocht "
                "door de officiële Roborock-winkel op Amazon.com.be. Wettelijke "
                "referentieprijs (laagste van de voorbije 30 dagen): 379,99 €.",
            ),
            "de": (
                "Saug- und Wischroboter roborock Qrevo S Pro für 329,99 €",
                "Saug- und Wischroboter mit 18 500 Pa und Anti-Verhedderungs-Bürste, "
                "verkauft vom offiziellen Roborock-Shop auf Amazon.com.be. Gesetzlicher "
                "Referenzpreis (niedrigster der letzten 30 Tage): 379,99 €.",
            ),
        },
    ),
    dict(
        title="Carottes Delhaize 1 kg : 2 achetés, le 3e offert",
        merchant="Delhaize",
        category="supermarche",
        price="1.49",
        reference=None,
        shipping="0.00",
        lang="fr",
        status=DealStatus.PUBLISHED,
        temp=133,
        description=(
            "Promotion « 2+1 gratuit » sur le sachet de carottes Delhaize de 1 kg "
            "(1,49 € le sachet) : 3 kg pour 2,98 €, soit environ 0,99 €/kg. Promotion "
            "de la semaine, dans la limite des stocks disponibles."
        ),
        url=(
            "https://www.delhaize.be/fr/shop/Fruits-et-legumes-frais/Legumes-frais/"
            "Carottes-et-legumes-racines/Carottes/Carottes/p/F2013100800315600000"
        ),
        image="https://static.delhaize.be/medias/sys_master/products/he6/hfc/13907354648606.jpg?imwidth=600",
        translations={
            "nl": (
                "Wortelen Delhaize 1 kg: 2 gekocht, de 3e gratis",
                "Actie « 2+1 gratis » op de zak wortelen van Delhaize van 1 kg (1,49 € per "
                "zak): 3 kg voor 2,98 €, of ongeveer 0,99 €/kg. Promotie van de week, "
                "zolang de voorraad strekt.",
            ),
            "de": (
                "Karotten Delhaize 1 kg: 2 kaufen, die 3. gratis",
                "Aktion „2+1 gratis“ auf den 1-kg-Beutel Karotten von Delhaize (1,49 € pro "
                "Beutel): 3 kg für 2,98 €, also etwa 0,99 €/kg. Angebot der Woche, solange "
                "der Vorrat reicht.",
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

        categories = self._categories()
        merchants = self._merchants()
        self._local_merchants()
        staff, members = self._users()
        deals = self._deals(merchants, categories, members, staff)

        # Volume (exigence du DUMP : 100 lignes minimum par table) : voir _volume.py.
        more_members = _volume.members()
        everyone = members + more_members
        self.stdout.write(f"Membres supplémentaires : {len(more_members)}")
        self.stdout.write(f"Commerçants OpenStreetMap : {_volume.osm_merchants()}")
        coolblue = _volume.coolblue_deals(
            categories=categories, members_pool=everyone, moderator=staff[1]
        )
        self.stdout.write(f"Offres relevées sur Coolblue : {len(coolblue)}")
        all_deals = deals + coolblue

        self._votes(all_deals, everyone + staff)
        self._comments(deals, members)
        self.stdout.write(
            f"Commentaires supplémentaires : {_volume.comments(coolblue, everyone)}"
        )
        self._payments(members)
        self.stdout.write(f"Paiements supplémentaires : {_volume.payments(more_members)}")
        self._reports(deals, members)
        self.stdout.write(
            f"Signalements supplémentaires : {_volume.reports(all_deals, everyone, staff[1])}"
        )
        self.stdout.write(f"Messages de contact : {_volume.contact_messages(everyone)}")
        self.stdout.write(f"Alertes : {_volume.alerts(everyone, categories)}")
        self.stdout.write(f"Alertes déclenchées : {_volume.alert_matches(all_deals)}")
        self.stdout.write(
            f"Journal d'audit : {_volume.audit_trail(staff + everyone, all_deals)} entrées"
        )

        self.stdout.write(self.style.SUCCESS("\nJeu de démonstration chargé."))
        self._summary()

    # ------------------------------------------------------------------
    def _flush(self):
        from apps.deals.models import Alert
        from apps.moderation.models import AuditLog

        for model in (
            AuditLog,
            Alert,
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
                    "website": MERCHANT_WEBSITES[name],
                },
            )
        self.stdout.write(f"Marchands : {len(out)}")
        return out

    def _local_merchants(self):
        from decimal import Decimal

        from apps.catalog.management.commands.import_local_merchants import SHOP_COLORS

        for osm_id, name, shop, address, city, lat, lon, website in LOCAL_MERCHANTS:
            Merchant.objects.update_or_create(
                osm_id=osm_id,
                defaults={
                    "name": name,
                    "slug": slugify(name),
                    "country": "BE",
                    "shop_type": shop,
                    "address": address,
                    "city": city,
                    "latitude": Decimal(lat),
                    "longitude": Decimal(lon),
                    "website": website,
                    "is_local_independent": True,
                    "is_verified": False,
                    "brand_color": SHOP_COLORS.get(shop, "#01182B"),
                },
            )
        self.stdout.write(f"Commerçants locaux (OpenStreetMap) : {len(LOCAL_MERCHANTS)}")

    def _users(self):
        # Mot de passe commun aux comptes de démonstration : il satisfait la
        # politique (12 caractères, trois classes, pas de suite de touches).
        # En ligne, la variable DEMO_PASSWORD le remplace par un secret.
        password = _volume.PASSWORD

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
        for email, name, lang in MEMBERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": name,
                    "preferred_language": lang,
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

    def _deals(self, merchants, categories, members, staff):
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
            code="vip-annuel",
            defaults={
                "name_fr": "VIP annuel",
                "name_nl": "VIP jaarlijks",
                "name_de": "VIP jährlich",
                "price": Decimal("24.00"),
                "vat_rate": Decimal("21.00"),
                "duration_days": 365,
                "is_active": True,
            },
        )
        Plan.objects.update_or_create(
            code="vip-mensuel",
            defaults={
                "name_fr": "VIP mensuel",
                "name_nl": "VIP maandelijks",
                "name_de": "VIP monatlich",
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
        secret = _volume.PASSWORD != "Demo-Tracker-2025"
        shown = "valeur de DEMO_PASSWORD (secret)" if secret else _volume.PASSWORD
        self.stdout.write(f"  Mot de passe commun : {shown}\n")
