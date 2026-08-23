# API REST — DealTrack.be

Base : `/api/v1/` — délibérément **hors** du préfixe de langue. Un client REST
négocie via l'en-tête `Accept-Language`, pas via l'URL. `/fr/api/v1/deals/`
renvoie 404, et c'est voulu.

Format d'échange : JSON. Encodage : UTF-8.

---

## Démarrage rapide

```bash
python3 manage.py runserver          # terminal 1
python3 scripts/api_demo.py          # terminal 2
```

Le script effectue de vrais appels HTTP sur les onze scénarios ci-dessous et
affiche le code attendu face au code obtenu. Comptes de démonstration :

| Adresse | Rôle | Mot de passe |
|---|---|---|
| `marc.vandenberghe@example.be` | membre | `Demo-Tracker-2025` |
| `moderation@dealtrack.be` | modérateur | `Demo-Tracker-2025` |
| `admin@dealtrack.be` | administrateur | `Demo-Tracker-2025` |

---

## Authentification

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "marc.vandenberghe@example.be", "password": "Demo-Tracker-2025"}'
```

```json
{
  "access":  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
}
```

Le jeton d'accès se place ensuite dans l'en-tête :

```
Authorization: Bearer <access>
```

Durées de vie : accès **15 minutes**, rafraîchissement **7 jours** avec
rotation. Le rafraîchissement passe par `POST /api/v1/auth/token/refresh/`.

---

## Points d'entrée

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| `GET` | `/deals/` | public | flux filtrable et paginé |
| `GET` | `/deals/{id}/` | public | détail d'une offre |
| `POST` | `/deals/` | membre | soumettre une offre |
| `PATCH` | `/deals/{id}/` | auteur (non publié) ou modérateur | modifier |
| `DELETE` | `/deals/{id}/` | auteur ou modérateur | retrait **logique** |
| `POST` | `/deals/{id}/vote/` | membre | réchauffer ou refroidir |
| `POST` | `/deals/{id}/publish/` | modérateur | valider |
| `POST` | `/deals/{id}/reject/` | modérateur | refuser, motif obligatoire |
| `GET` | `/comments/?deal={id}` | public | commentaires d'une offre |
| `POST` | `/comments/` | membre | commenter |
| `GET` | `/me/` | membre | son propre profil |
| `DELETE` | `/me/` | membre | désinscription (art. 17 RGPD) |
| `GET` | `/me/export/` | membre | portabilité (art. 20 RGPD) |
| `GET` | `/moderation/queue/` | modérateur | file d'attente |
| `POST` | `/auth/token/` | public | obtenir un JWT |
| `POST` | `/auth/token/refresh/` | public | rafraîchir |
| `POST` | `/auth/token/verify/` | public | vérifier |

---

## GET `/deals/` — lecture publique

```bash
curl "http://127.0.0.1:8000/api/v1/deals/?ordering=-temperature"
```

```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "3f2b8c11-…",
      "url": "http://127.0.0.1:8000/api/v1/deals/3f2b8c11-…/",
      "title": "Casque Sony WH-1000XM5 à réduction de bruit active…",
      "price": "249.00",
      "reference_price": "349.00",
      "discount_percentage": 29,
      "currency": "EUR",
      "shipping_cost": "0.00",
      "merchant": {
        "name": "Coolblue",
        "country": "BE",
        "is_local_independent": false,
        "is_verified": true
      },
      "category": {"slug": "high-tech", "label": "High-tech"},
      "author": "MarcVDB",
      "status": "published",
      "temperature": 1124,
      "is_cross_border": false,
      "is_expired": false
    }
  ]
}
```

`count` vaut 8 alors que la base en contient 10 : **les offres en attente de
modération sont filtrées**, y compris pour un appelant anonyme.

### Filtres

| Paramètre | Exemple | Effet |
|---|---|---|
| `search` | `?search=fibre` | titre, description, nom du marchand |
| `category` | `?category=high-tech` | par slug de catégorie |
| `region` | `?region=BE1` | code NUTS-1 |
| `merchant` | `?merchant=coolblue` | par slug de marchand |
| `local_only` | `?local_only=true` | indépendants belges |
| `is_cross_border` | `?is_cross_border=true` | offres transfrontalières |
| `min_price` / `max_price` | `?min_price=100&max_price=300` | fourchette |
| `min_temperature` | `?min_temperature=500` | seuil de popularité |
| `language` | `?language=nl` | langue de rédaction |
| `ordering` | `?ordering=price` | `temperature`, `published_at`, `price`, `created_at` |
| `page` | `?page=2` | 20 éléments par page |

Une valeur invalide renvoie **400**, pas 500 :

```bash
curl "…/deals/?min_price=pas-un-nombre"      # → 400
```

### Négociation de langue

```bash
curl -H "Accept-Language: nl" "…/deals/"     # libellés de catégorie en NL
```

---

## POST `/deals/` — création

```bash
curl -X POST http://127.0.0.1:8000/api/v1/deals/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Aspirateur balai Dyson V12 Detect Slim Absolute",
    "description": "Prix le plus bas relevé en Belgique depuis quatre mois.",
    "external_url": "https://www.coolblue.be/fr/produit/dyson-v12",
    "price": "399.00",
    "reference_price": "649.00",
    "merchant": "<uuid>",
    "category": "<uuid>",
    "language": "nl"
  }'
```

**201 Created.** L'offre entre en `pending` quoi qu'il arrive : `status`,
`submitted_by` et `temperature` ne sont pas exposés par le sérialiseur. Une
charge utile portant `"status": "published"` et `"temperature": 99999` produit
malgré tout `pending` à 100°.

### Validations serveur

| Règle | Réponse |
|---|---|
| Titre de moins de 15 caractères | 400 |
| Titre entièrement en majuscules | 400 |
| Lien non-HTTPS | 400 |
| `reference_price` ≤ `price` | 400 |
| `ends_at` ≤ `starts_at` | 400 |
| Marchand hors Belgique sans `is_cross_border` | 400 |
| Prix négatif ou supérieur à 100 000 € | 400 |

```json
{
  "error": {
    "code": "bad_request",
    "trace_id": "a3f9c2e11b04",
    "detail": {
      "reference_price": [
        "Le prix de référence doit dépasser le prix affiché, sinon la réduction annoncée est trompeuse."
      ]
    }
  }
}
```

---

## PATCH `/deals/{id}/` — modification

Autorisée à l'auteur tant que l'offre n'est pas publiée, ou à un modérateur
à tout moment.

```bash
curl -X PATCH "…/deals/$ID/" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"price": "379.00"}'
```

Un membre tiers reçoit **404** et non 403 : l'offre en attente est absente de
son périmètre de lecture, et répondre 403 confirmerait son existence.

---

## DELETE `/deals/{id}/` — retrait logique

```bash
curl -X DELETE "…/deals/$ID/" -H "Authorization: Bearer $TOKEN"    # → 204
curl "…/deals/$ID/"                                                # → 404
```

Aucun `DELETE` SQL n'est exécuté. La colonne `deleted_at` est renseignée ; votes
et commentaires restent rattachés, et le back-office continue de voir la ligne.

---

## POST `/deals/{id}/vote/`

```bash
curl -X POST "…/deals/$ID/vote/" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"value": 1}'
```

```json
{"id": "3f2b8c11-…", "temperature": 101}
```

`value` vaut `1` ou `-1`. Revoter dans le même sens **annule** le vote plutôt
que de le doubler. Une contrainte d'unicité en base garantit une voix par membre
et par offre, y compris sous requêtes concurrentes. Une valeur hors domaine
renvoie 400 ; voter sur une offre non publiée renvoie 409.

---

## Modération

```bash
curl "…/moderation/queue/"  -H "Authorization: Bearer $MOD"        # 200
curl "…/moderation/queue/"  -H "Authorization: Bearer $MEMBRE"     # 403

curl -X POST "…/deals/$ID/publish/" -H "Authorization: Bearer $MOD" \
  -H "Content-Type: application/json" -d '{"reason": "Lien et prix contrôlés."}'
```

Chaque décision crée une ligne `ModerationDecision` nominative et une entrée
dans la piste d'audit. Un refus **sans motif** est rejeté par une contrainte de
table, pas seulement par le code.

---

## RGPD

```bash
curl "…/me/export/" -H "Authorization: Bearer $TOKEN"
```

```json
{
  "identifiant": "cea7f0d5-…",
  "email": "marc.vandenberghe@example.be",
  "pseudonyme": "MarcVDB",
  "langue": "fr",
  "region": "BE3",
  "inscrit_le": "2024-03-11T09:42:00+01:00",
  "consentement_marketing": true,
  "deals_publies": [...],
  "commentaires": [...],
  "paiements": [{"reference": "DT-2026-000001", "montant": "24.00", …}]
}
```

```bash
curl -X DELETE "…/me/" -H "Authorization: Bearer $TOKEN"
```

Deux réponses possibles :

```json
{"status": "anonymised",
 "detail": "Compte désactivé et données personnelles anonymisées."}
```

```json
{"status": "soft_deleted_pending_retention",
 "detail": "Compte désactivé. Les données personnelles seront purgées à l'expiration du délai légal de conservation comptable."}
```

Le second cas s'applique dès qu'un paiement existe : le droit à l'effacement
cède devant l'obligation de conservation comptable belge. Voir
[`LEGAL_GDPR.md`](LEGAL_GDPR.md).

---

## Codes de réponse

| Code | Signification |
|---|---|
| 200 | succès |
| 201 | ressource créée |
| 204 | supprimée logiquement, pas de corps |
| 400 | validation échouée, détail par champ |
| 401 | authentification absente ou jeton invalide |
| 403 | authentifié mais rôle insuffisant |
| 404 | inexistant, ou hors du périmètre de l'appelant |
| 405 | méthode non permise |
| 409 | conflit (double vote, offre déjà publiée) |
| 429 | débit dépassé, en-tête `Retry-After` fourni |
| 500 | anomalie serveur, `trace_id` à citer au support |

Toute erreur suit la même enveloppe :

```json
{"error": {"code": "…", "trace_id": "…", "detail": {…}}}
```

Le `trace_id` rapproche la réponse et la ligne de `logs/dealtrack.log`. Aucune
trace d'exécution n'est jamais renvoyée au client.

---

## Limitation de débit

| Portée | Limite |
|---|---|
| anonyme | 60 / heure |
| authentifié | 1000 / heure |
| écriture de deal | 20 / heure |
| vote | 60 / heure |
| obtention de jeton | 10 / heure par IP |

---

## Postman

Importer `docs/DealTrack.postman_collection.json`. La collection contient les
onze scénarios dans l'ordre. La requête d'authentification enregistre
automatiquement le jeton dans la variable `access_token` via son script de test,
et les requêtes suivantes s'en servent — aucun copier-coller n'est nécessaire.

Variables d'environnement : `base_url` (par défaut `http://127.0.0.1:8000`),
`email`, `password`.
