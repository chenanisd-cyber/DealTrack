#!/usr/bin/env python3
"""
Construit la collection Postman.

Générée plutôt qu'écrite à la main : les identifiants de marchand et de
catégorie viennent de la base réelle, donc la collection est directement
exécutable après un `seed_demo`.
"""

import json
import os
import sys
from pathlib import Path

import django

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.catalog.models import Category, Merchant  # noqa: E402
from apps.deals.models import Deal, DealStatus  # noqa: E402


def request(
    name, method, path, *, auth=True, body=None, description="", expect=200, tests=None
):
    item = {
        "name": name,
        "request": {
            "method": method,
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "url": {
                "raw": "{{base_url}}/api/v1" + path,
                "host": ["{{base_url}}"],
                "path": ["api", "v1"] + [p for p in path.strip("/").split("/") if p],
            },
            "description": description,
        },
    }
    if auth:
        item["request"]["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{access_token}}"}],
        }
    if body is not None:
        item["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, ensure_ascii=False, indent=2),
        }
    script = [f'pm.test("HTTP {expect}", () => pm.response.to.have.status({expect}));']
    if tests:
        script += tests
    item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": script}}]
    return item


def main():
    merchant = Merchant.objects.get(slug="coolblue")
    dutch = Merchant.objects.get(slug="action-maastricht")
    category = Category.objects.get(slug="high-tech")
    published = Deal.objects.filter(status=DealStatus.PUBLISHED).first()

    collection = {
        "info": {
            "name": "DealTrack.be — API v1",
            "description": (
                "Collection de démonstration. Exécuter dans l'ordre : la requête "
                "d'authentification enregistre le jeton dans {{access_token}}, "
                "les suivantes s'en servent.\n\n"
                "Prérequis : python3 manage.py migrate && python3 manage.py seed_demo"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": "http://127.0.0.1:8000"},
            {"key": "email", "value": "marc.vandenberghe@example.be"},
            {"key": "password", "value": "Demo-Tracker-2025"},
            {"key": "moderator_email", "value": "moderation@dealtrack.be"},
            {"key": "access_token", "value": ""},
            {"key": "moderator_token", "value": ""},
            {"key": "deal_id", "value": ""},
            {"key": "merchant_id", "value": str(merchant.pk)},
            {"key": "category_id", "value": str(category.pk)},
            {"key": "dutch_merchant_id", "value": str(dutch.pk)},
            {"key": "published_deal_id", "value": str(published.pk) if published else ""},
        ],
        "item": [
            # ---------------------------------------------------------
            {
                "name": "1 · Lecture publique",
                "item": [
                    request(
                        "GET /deals/ — flux complet",
                        "GET",
                        "/deals/?ordering=-temperature",
                        auth=False,
                        description=(
                            "Aucune authentification. Le compte renvoyé exclut les offres "
                            "en attente de modération : le filtrage d'accès s'applique "
                            "aussi à l'anonyme."
                        ),
                        tests=[
                            "const d = pm.response.json();",
                            'pm.test("format paginé", () => pm.expect(d).to.have.keys('
                            '"count","next","previous","results"));',
                            'pm.test("aucune offre en attente", () => '
                            'pm.expect(d.results.every(r => r.status !== "pending")).to.be.true);',
                        ],
                    ),
                    request(
                        "GET /deals/ — filtre commerçants locaux",
                        "GET",
                        "/deals/?local_only=true",
                        auth=False,
                        description="Indépendants belges uniquement.",
                    ),
                    request(
                        "GET /deals/ — fourchette de prix",
                        "GET",
                        "/deals/?min_price=100&max_price=300",
                        auth=False,
                    ),
                    request(
                        "GET /deals/ — recherche plein texte",
                        "GET",
                        "/deals/?search=fibre",
                        auth=False,
                    ),
                    request(
                        "GET /deals/ — filtre invalide → 400",
                        "GET",
                        "/deals/?min_price=pas-un-nombre",
                        auth=False,
                        expect=400,
                        description="Une valeur non numérique renvoie 400, jamais 500.",
                    ),
                    request(
                        "GET /deals/{id}/ — détail",
                        "GET",
                        "/deals/{{published_deal_id}}/",
                        auth=False,
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "2 · Refus sans authentification",
                "item": [
                    request(
                        "POST /deals/ anonyme → 401",
                        "POST",
                        "/deals/",
                        auth=False,
                        expect=401,
                        body={"title": "tentative anonyme"},
                        description="Écriture fermée par défaut.",
                        tests=[
                            'pm.test("enveloppe d\'erreur", () => '
                            "pm.expect(pm.response.json().error).to.have.keys("
                            '"code","trace_id","detail"));'
                        ],
                    ),
                    request("GET /me/ anonyme → 401", "GET", "/me/", auth=False, expect=401),
                    request(
                        "GET /moderation/queue/ anonyme → 401",
                        "GET",
                        "/moderation/queue/",
                        auth=False,
                        expect=401,
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "3 · Authentification",
                "item": [
                    request(
                        "POST /auth/token/ — membre",
                        "POST",
                        "/auth/token/",
                        auth=False,
                        body={"email": "{{email}}", "password": "{{password}}"},
                        description="Enregistre le jeton dans {{access_token}}.",
                        tests=[
                            "const d = pm.response.json();",
                            'pm.collectionVariables.set("access_token", d.access);',
                            'pm.test("jeton reçu", () => pm.expect(d.access).to.be.a("string"));',
                        ],
                    ),
                    request(
                        "POST /auth/token/ — modérateur",
                        "POST",
                        "/auth/token/",
                        auth=False,
                        body={"email": "{{moderator_email}}", "password": "{{password}}"},
                        tests=[
                            'pm.collectionVariables.set("moderator_token", '
                            "pm.response.json().access);"
                        ],
                    ),
                    request("GET /me/ — profil", "GET", "/me/"),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "4 · Création et validation",
                "item": [
                    request(
                        "POST /deals/ — le serveur impose le statut",
                        "POST",
                        "/deals/",
                        expect=201,
                        body={
                            "title": "Aspirateur balai Dyson V12 Detect Slim Absolute",
                            "description": (
                                "Prix le plus bas relevé en Belgique depuis "
                                "quatre mois. Stock limité à Anvers et Gand."
                            ),
                            "external_url": "https://www.coolblue.be/fr/produit/dyson-v12",
                            "price": "399.00",
                            "reference_price": "649.00",
                            "merchant": "{{merchant_id}}",
                            "category": "{{category_id}}",
                            "language": "nl",
                            "status": "published",
                            "temperature": 99999,
                        },
                        description=(
                            "La charge utile tente de forcer status=published et "
                            "temperature=99999. Ces champs ne sont pas exposés par le "
                            "sérialiseur : l'offre entre en pending à 100°."
                        ),
                        tests=['pm.collectionVariables.set("deal_id", pm.response.json().id);'],
                    ),
                    request(
                        "GET /deals/{id}/ — vérifier le statut réel",
                        "GET",
                        "/deals/{{deal_id}}/",
                        tests=[
                            "const d = pm.response.json();",
                            'pm.test("statut imposé", () => pm.expect(d.status).to.eql("pending"));',
                            'pm.test("température imposée", () => '
                            "pm.expect(d.temperature).to.eql(100));",
                        ],
                    ),
                    request(
                        "POST /deals/ — prix de référence incohérent → 400",
                        "POST",
                        "/deals/",
                        expect=400,
                        body={
                            "title": "Écran Dell UltraSharp 27 pouces U2724D",
                            "description": "Prix barré inférieur au prix affiché.",
                            "external_url": "https://example.be/dell-u2724d",
                            "price": "400.00",
                            "reference_price": "300.00",
                            "merchant": "{{merchant_id}}",
                            "category": "{{category_id}}",
                        },
                        description="Article VI.18 CDE : la réduction annoncée serait trompeuse.",
                    ),
                    request(
                        "POST /deals/ — lien non-HTTPS → 400",
                        "POST",
                        "/deals/",
                        expect=400,
                        body={
                            "title": "Enceinte portable JBL Charge 5 étanche",
                            "description": "Lien en clair vers la fiche produit du marchand.",
                            "external_url": "http://example.be/jbl-charge-5",
                            "price": "99.00",
                            "merchant": "{{merchant_id}}",
                            "category": "{{category_id}}",
                        },
                    ),
                    request(
                        "POST /deals/ — marchand étranger sans drapeau → 400",
                        "POST",
                        "/deals/",
                        expect=400,
                        body={
                            "title": "Sèche-linge Bosch pompe à chaleur huit kilos",
                            "description": "Vendu par un marchand néerlandais près de la frontière.",
                            "external_url": "https://example.nl/bosch-seche-linge",
                            "price": "449.00",
                            "merchant": "{{dutch_merchant_id}}",
                            "category": "{{category_id}}",
                        },
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "5 · Modification et contrôle d'accès",
                "item": [
                    request(
                        "PATCH /deals/{id}/ — par l'auteur",
                        "PATCH",
                        "/deals/{{deal_id}}/",
                        body={"price": "379.00"},
                        tests=[
                            'pm.test("prix modifié", () => '
                            'pm.expect(pm.response.json().price).to.eql("379.00"));'
                        ],
                    ),
                    request(
                        "POST /deals/{id}/publish/ — par un membre → 403",
                        "POST",
                        "/deals/{{deal_id}}/publish/",
                        expect=403,
                        description="Élévation de privilège : publier est réservé à la modération.",
                    ),
                    request(
                        "GET /moderation/queue/ — par un membre → 403",
                        "GET",
                        "/moderation/queue/",
                        expect=403,
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "6 · Modération",
                "item": [
                    {
                        **request(
                            "GET /moderation/queue/ — par un modérateur",
                            "GET",
                            "/moderation/queue/",
                        ),
                        "request": {
                            **request("x", "GET", "/moderation/queue/")["request"],
                            "auth": {
                                "type": "bearer",
                                "bearer": [{"key": "token", "value": "{{moderator_token}}"}],
                            },
                        },
                    },
                    {
                        **request(
                            "POST /deals/{id}/publish/ — par un modérateur",
                            "POST",
                            "/deals/{{deal_id}}/publish/",
                            body={"reason": "Lien et prix de référence contrôlés."},
                            tests=[
                                'pm.test("publiée", () => '
                                'pm.expect(pm.response.json().status).to.eql("published"));'
                            ],
                        ),
                        "request": {
                            **request(
                                "x",
                                "POST",
                                "/deals/{{deal_id}}/publish/",
                                body={"reason": "Lien et prix de référence contrôlés."},
                            )["request"],
                            "auth": {
                                "type": "bearer",
                                "bearer": [{"key": "token", "value": "{{moderator_token}}"}],
                            },
                        },
                    },
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "7 · Vote",
                "item": [
                    request(
                        "POST /deals/{id}/vote/ — réchauffer",
                        "POST",
                        "/deals/{{deal_id}}/vote/",
                        body={"value": 1},
                        tests=[
                            'pm.test("température à 101", () => '
                            "pm.expect(pm.response.json().temperature).to.eql(101));"
                        ],
                    ),
                    request(
                        "POST /deals/{id}/vote/ — revote identique annule",
                        "POST",
                        "/deals/{{deal_id}}/vote/",
                        body={"value": 1},
                        description="Revoter dans le même sens retire le vote, ne le double pas.",
                        tests=[
                            'pm.test("retour à 100", () => '
                            "pm.expect(pm.response.json().temperature).to.eql(100));"
                        ],
                    ),
                    request(
                        "POST /deals/{id}/vote/ — valeur hors domaine → 400",
                        "POST",
                        "/deals/{{deal_id}}/vote/",
                        body={"value": 7},
                        expect=400,
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "8 · RGPD",
                "item": [
                    request(
                        "GET /me/export/ — portabilité (art. 20)",
                        "GET",
                        "/me/export/",
                        tests=[
                            'pm.test("sections attendues", () => '
                            "pm.expect(pm.response.json()).to.include.keys("
                            '"identifiant","email","deals_publies","paiements"));'
                        ],
                    ),
                    request(
                        "DELETE /me/ — effacement (art. 17)",
                        "DELETE",
                        "/me/",
                        description=(
                            "Ne lance jamais de DELETE SQL. Renvoie 'anonymised' si aucun "
                            "paiement, 'soft_deleted_pending_retention' sinon — le droit à "
                            "l'effacement cède devant la conservation comptable de sept ans.\n\n"
                            "À exécuter en dernier : le compte devient inutilisable."
                        ),
                        tests=[
                            'pm.test("statut de désinscription", () => '
                            'pm.expect(["anonymised","soft_deleted_pending_retention"])'
                            ".to.include(pm.response.json().status));"
                        ],
                    ),
                ],
            },
            # ---------------------------------------------------------
            {
                "name": "9 · Retrait logique",
                "item": [
                    {
                        **request(
                            "DELETE /deals/{id}/ — retrait",
                            "DELETE",
                            "/deals/{{deal_id}}/",
                            expect=204,
                            description="La ligne reste en base avec deleted_at renseigné.",
                        ),
                        "request": {
                            **request("x", "DELETE", "/deals/{{deal_id}}/")["request"],
                            "auth": {
                                "type": "bearer",
                                "bearer": [{"key": "token", "value": "{{moderator_token}}"}],
                            },
                        },
                    },
                    request(
                        "GET /deals/{id}/ — disparue du flux → 404",
                        "GET",
                        "/deals/{{deal_id}}/",
                        auth=False,
                        expect=404,
                    ),
                ],
            },
        ],
    }

    out = BASE / "docs" / "DealTrack.postman_collection.json"
    out.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(g["item"]) for g in collection["item"])
    print(f"Collection écrite : {out.relative_to(BASE)}")
    print(f"  {len(collection['item'])} dossiers, {total} requêtes")
    for group in collection["item"]:
        print(f"    {group['name']:.<44} {len(group['item'])} requêtes")


if __name__ == "__main__":
    main()
