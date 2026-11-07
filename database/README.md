# database/ — base de données

| Fichier | Rôle |
|---|---|
| `db.sqlite3` | Base SQLite de développement. Créée par `migrate`, **jamais versionnée** |
| `docker-compose.yml` | PostgreSQL 16 local, pour tester dans les conditions de production |
| `DATA_DICTIONARY.md` | Dictionnaire de données : tables, colonnes, types, contraintes |

## Où est défini le schéma ?

Avec Django, le schéma n'est pas écrit en SQL à la main : chaque table est une
classe Python (un *modèle*), et Django génère le SQL sous forme de
*migrations*. Les deux restent dans le backend, à côté du code qui les utilise :

| Module | Modèles | Migrations |
|---|---|---|
| Comptes | `backend/apps/accounts/models.py` | `backend/apps/accounts/migrations/` |
| Catalogue | `backend/apps/catalog/models.py` | `backend/apps/catalog/migrations/` |
| Offres | `backend/apps/deals/models.py` | `backend/apps/deals/migrations/` |
| Paiements | `backend/apps/payments/models.py` | `backend/apps/payments/migrations/` |
| Modération | `backend/apps/moderation/models.py` | `backend/apps/moderation/migrations/` |

Pour voir le SQL exact d'une migration :

```bash
cd backend
python manage.py sqlmigrate deals 0003
```

## Commandes utiles

```bash
cd backend
python manage.py migrate                 # crée / met à jour database/db.sqlite3
python manage.py seed_demo               # données de démonstration réalistes
python manage.py data_dictionary > ../database/DATA_DICTIONARY.md
```

Repartir d'une base vierge :

```bash
rm database/db.sqlite3       # depuis la racine
make migrate seed
```

PostgreSQL local (Docker) :

```bash
docker compose -f database/docker-compose.yml up -d
```

Puis renseigner les variables `POSTGRES_*` dans `.env` et lancer les commandes
avec `DJANGO_SETTINGS_MODULE=config.settings.prod`.
