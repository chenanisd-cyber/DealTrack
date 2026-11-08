# backend/ — serveur Django

Toute la logique côté serveur : modèles de données, règles métier, sécurité,
API REST et tests. Les commandes se lancent **depuis ce dossier**.

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py setup_roles
python manage.py runserver        # http://localhost:8000/fr/
```

## Contenu

| Dossier | Rôle |
|---|---|
| `config/settings/` | Réglages : `base.py` (commun), `dev.py`, `test.py`, `prod.py` |
| `config/urls.py` | URL racines : API, sélecteur de langue, pages traduites |
| `apps/accounts/` | Utilisateurs, rôles, inscription, export RGPD, désinscription (soft delete) |
| `apps/catalog/` | Catégories multilingues, marchands ; commandes `seed_demo`, `data_dictionary` |
| `apps/deals/` | Offres, votes, commentaires, pré-remplissage par lien (`scraper.py`) |
| `apps/payments/` | Formules, paiements, abonnements, passerelle de paiement |
| `apps/moderation/` | Journal d'audit, décisions, signalements |
| `apps/api/` | API REST : sérialiseurs, vues, permissions, limitation de débit |
| `tests/` | 173 tests unitaires et d'intégration |
| `scripts/` | Démonstration de l'API, traductions, collection Postman |
| `logs/` | Journaux `dealtrack.log` et `security.log` (non versionnés) |

Chaque application suit le même découpage Django :
`models.py` (tables) → `forms.py` / `serializers.py` (validation) →
`views.py` (traitement des requêtes) → `urls.py` (routes) → `admin.py`
(back-office). Les migrations restent dans `apps/<module>/migrations/`.

## Liens avec les autres dossiers

Les chemins sont définis une seule fois, dans `config/settings/base.py` :

| Réglage | Pointe vers |
|---|---|
| `TEMPLATES["DIRS"]` | `../frontend/templates/` |
| `STATICFILES_DIRS` | `../frontend/static/` |
| `LOCALE_PATHS` | `../frontend/locale/` |
| `DATABASES["default"]["NAME"]` | `../database/db.sqlite3` |
| `MEDIA_ROOT` | `../database/media/` (photos et logos envoyés) |
