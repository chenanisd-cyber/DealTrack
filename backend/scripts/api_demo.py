#!/usr/bin/env python3
"""
Démonstration en direct de l'API DealTrack.

Effectue de vrais appels HTTP sur un serveur en cours d'exécution :
  GET     public non authentifié
  POST    /auth/token/            obtention d'un JWT
  POST    /deals/                 création (avec tentative d'élévation)
  PATCH   /deals/{id}/            modification par l'auteur
  DELETE  /deals/{id}/            retrait logique
  GET     /me/export/             portabilité RGPD
  plus les refus attendus : anonyme, mauvais rôle, propriétaire différent.

Le scénario est destructif : il crée une offre, la publie, la retire et ferme
le compte de démonstration. Relancer après un `python3 manage.py seed_demo`.

Usage :
    python3 manage.py seed_demo
    python3 manage.py runserver &
    python3 scripts/api_demo.py [http://127.0.0.1:8000]
"""

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
PASSWORD = "Demo-Tracker-2025"


def call(method, path, *, token=None, body=None):
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept-Language", "fr")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw[:200]


def title(text):
    print(f"\n\033[1m{'─' * 74}\n{text}\n{'─' * 74}\033[0m")


def show(label, status, expected):
    mark = "\033[32m✓\033[0m" if status == expected else "\033[31m✗\033[0m"
    print(f"  {mark} {label:<52} HTTP {status} (attendu {expected})")


def main():
    # ------------------------------------------------------------------
    title("1. GET public — aucune authentification")
    status, payload = call("GET", "/deals/?ordering=-temperature")
    show("GET /api/v1/deals/", status, 200)
    print(f"      {payload['count']} deals visibles ; les offres en attente sont filtrées")
    for row in payload["results"][:4]:
        print(
            f"      {row['temperature']:>5}°  {row['price']:>7} €  "
            f"{row['merchant']['name']:<23} {row['title'][:40]}"
        )

    reference = payload["results"][0]
    merchant_id, category_id = reference["merchant"]["id"], reference["category"]["id"]

    title("2. GET filtré et paginé")
    for query, label in [
        ("?local_only=true", "commerçants indépendants belges"),
        ("?is_cross_border=true", "offres transfrontalières"),
        ("?min_price=100&max_price=300", "entre 100 et 300 €"),
        ("?search=fibre", "recherche plein texte « fibre »"),
    ]:
        status, payload = call("GET", f"/deals/{query}")
        print(f"  {label:<42} → {payload['count']} résultat(s)")

    status, payload = call("GET", "/deals/?min_price=pas-un-nombre")
    show("filtre invalide renvoie 400, pas 500", status, 400)

    # ------------------------------------------------------------------
    title("3. Écriture refusée sans authentification")
    status, payload = call("POST", "/deals/", body={"title": "tentative"})
    show("POST /api/v1/deals/ anonyme", status, 401)
    print(f"      code : {payload['error']['code']} · trace : {payload['error']['trace_id']}")

    # ------------------------------------------------------------------
    title("4. Authentification JWT")
    status, tokens = call(
        "POST", "/auth/token/", body={"email": "sofie.lievens@example.be", "password": PASSWORD}
    )
    show("POST /api/v1/auth/token/", status, 200)
    member = tokens["access"]
    print(f"      access  : {member[:48]}…")
    print(f"      refresh : {tokens['refresh'][:48]}…")

    status, _ = call("GET", "/me/", token="jeton.forge.invalide")
    show("jeton falsifié rejeté", status, 401)

    # ------------------------------------------------------------------
    title("5. POST authentifié — le serveur impose statut et auteur")
    status, created = call(
        "POST",
        "/deals/",
        token=member,
        body={
            "title": "Aspirateur balai Dyson V12 Detect Slim Absolute",
            "description": (
                "Prix le plus bas relevé en Belgique depuis quatre mois. "
                "Stock limité aux magasins d'Anvers et de Gand."
            ),
            "external_url": "https://www.coolblue.be/fr/produit/dyson-v12",
            "price": "399.00",
            "reference_price": "649.00",
            "merchant": merchant_id,
            "category": category_id,
            "language": "nl",
            # Champs que le client tente de forcer :
            "status": "published",
            "temperature": 99999,
        },
    )
    show("POST /api/v1/deals/", status, 201)
    new_id = created["id"]

    status, detail = call("GET", f"/deals/{new_id}/", token=member)
    print(
        f"      statut enregistré ..... {detail['status']}  "
        f"(la charge utile demandait « published »)"
    )
    print(
        f"      température ........... {detail['temperature']}  "
        f"(la charge utile demandait 99999)"
    )
    print(f"      auteur ................ {detail['author']}")
    print("      → les champs de décision sont fixés par le serveur.")

    title("6. Validation côté serveur")
    status, payload = call(
        "POST",
        "/deals/",
        token=member,
        body={
            "title": "Écran Dell UltraSharp 27 pouces U2724D",
            "description": "Réduction annoncée avec un prix barré inférieur au prix affiché.",
            "external_url": "https://example.be/dell-u2724d",
            "price": "400.00",
            "reference_price": "300.00",
            "merchant": merchant_id,
            "category": category_id,
        },
    )
    show("prix de référence < prix → refusé", status, 400)
    print(f"      {payload['error']['detail']['reference_price'][0][:88]}")

    status, payload = call(
        "POST",
        "/deals/",
        token=member,
        body={
            "title": "Enceinte portable JBL Charge 5 étanche",
            "description": "Lien en clair, non chiffré, vers la fiche produit du marchand.",
            "external_url": "http://example.be/jbl",
            "price": "99.00",
            "merchant": merchant_id,
            "category": category_id,
        },
    )
    show("lien non-HTTPS → refusé", status, 400)

    # ------------------------------------------------------------------
    title("7. PATCH — l'auteur modifie sa propre offre en attente")
    status, patched = call("PATCH", f"/deals/{new_id}/", token=member, body={"price": "379.00"})
    show("PATCH par l'auteur", status, 200)
    print(f"      prix : 399.00 € → {patched['price']} €")

    title("8. Contrôle d'accès — Broken Access Control")
    status, other = call(
        "POST", "/auth/token/", body={"email": "jan.willems@example.be", "password": PASSWORD}
    )
    intruder = other["access"]
    status, _ = call(
        "PATCH",
        f"/deals/{new_id}/",
        token=intruder,
        body={"title": "Titre détourné par un tiers malveillant"},
    )
    # 404 et non 403 : l'offre est encore en attente, donc absente du queryset
    # `for_user()` de l'intrus. Le filtrage d'accès agit avant l'évaluation des
    # permissions, et répondre 403 confirmerait l'existence de la ressource.
    show("PATCH par un autre membre (filtré en amont)", status, 404)

    status, _ = call("POST", f"/deals/{new_id}/publish/", token=member)
    show("publication par un membre simple", status, 403)

    status, _ = call("GET", "/moderation/queue/", token=member)
    show("file de modération vue par un membre", status, 403)

    status, moderator_tokens = call(
        "POST", "/auth/token/", body={"email": "moderation@dealtrack.be", "password": PASSWORD}
    )
    moderator = moderator_tokens["access"]
    status, queue = call("GET", "/moderation/queue/", token=moderator)
    show("file de modération vue par un modérateur", status, 200)
    print(f"      {queue['count']} offre(s) en attente de validation")

    status, published = call(
        "POST",
        f"/deals/{new_id}/publish/",
        token=moderator,
        body={"reason": "Lien et prix de référence contrôlés."},
    )
    show("publication par un modérateur", status, 200)
    print(f"      statut : {published['status']} · publié le {published['published_at'][:16]}")

    # ------------------------------------------------------------------
    title("9. Vote — une voix par membre et par offre")
    status, vote = call("POST", f"/deals/{new_id}/vote/", token=intruder, body={"value": 1})
    show("premier vote", status, 200)
    print(f"      température : 100° → {vote['temperature']}°")
    status, vote = call("POST", f"/deals/{new_id}/vote/", token=intruder, body={"value": 1})
    print(f"      revote identique → {vote['temperature']}° (le vote est annulé, pas doublé)")
    status, _ = call("POST", f"/deals/{new_id}/vote/", token=intruder, body={"value": 7})
    show("valeur de vote hors domaine", status, 400)

    # ------------------------------------------------------------------
    title("10. RGPD — portabilité et effacement")
    status, export = call("GET", "/me/export/", token=member)
    show("GET /api/v1/me/export/", status, 200)
    print(f"      sections exportées : {', '.join(export.keys())}")
    print(
        f"      {len(export['deals_publies'])} deal(s), "
        f"{len(export['commentaires'])} commentaire(s), "
        f"{len(export['paiements'])} paiement(s)"
    )

    # Le compte porte une facture : le droit à l'effacement cède devant
    # l'obligation de conservation comptable. Aucun DELETE SQL n'est émis.
    status, closure = call("DELETE", "/me/", token=member)
    show("DELETE /api/v1/me/ (droit à l'effacement)", status, 200)
    print(f"      statut : {closure['status']}")
    print(f"      {closure['detail'][:82]}")

    status, _ = call("GET", "/me/", token=member)
    show("le jeton du compte fermé ne fonctionne plus", status, 401)

    # ------------------------------------------------------------------
    title("11. DELETE — retrait logique, jamais de DELETE SQL")
    status, _ = call("DELETE", f"/deals/{new_id}/", token=moderator)
    show("DELETE /api/v1/deals/{id}/", status, 204)
    status, _ = call("GET", f"/deals/{new_id}/")
    show("l'offre a disparu du flux public", status, 404)
    print("      → la ligne existe toujours en base, avec deleted_at renseigné.")

    print("\n\033[1mDémonstration terminée.\033[0m\n")


if __name__ == "__main__":
    main()
