# database/ — base de données

| Fichier | Rôle |
|---|---|
| `db.sqlite3` | Base SQLite de développement. Créée par `migrate`, **jamais versionnée** |
| `media/` | Photos d'offres et logos de marchands envoyés par les utilisateurs (**non versionné**) |
| `docker-compose.yml` | PostgreSQL 16 local, pour tester dans les conditions de production |
| `DATA_DICTIONARY.md` | Dictionnaire de données : tables, colonnes, types, contraintes |
| `dump_dealtrack_mysql.sql` | **DUMP MySQL** (phpMyAdmin) : structure + données, 100 lignes minimum par table |
| `dump_dealtrack.sql` | Même DUMP au format SQLite (base de développement) |

## DUMP SQL

`dump_dealtrack.sql` contient toute la base, dans l'ordre classique d'un dump :

1. **Structure** : les 31 tables avec clés primaires, clés étrangères
   (`REFERENCES … DEFERRABLE INITIALLY DEFERRED`), contraintes `CHECK` et `UNIQUE` ;
2. **Données** : les `INSERT INTO` ;
3. **Index** : les 75 `CREATE INDEX`.

Projet en **code first** : modèles Django → migrations → données de test
(`seed_demo`) → export. Régénérer le dump :

```bash
cd backend
python manage.py seed_demo --flush
python manage.py setup_roles
python manage.py export_dump            # écrit ../database/dump_dealtrack.sql
python manage.py export_dump --counts   # nombre de lignes par table
```

Recharger le dump dans une base vierge :

```bash
sqlite3 nouvelle_base.sqlite3 < database/dump_dealtrack.sql
```

### Version MySQL (phpMyAdmin)

`dump_dealtrack_mysql.sql` contient exactement les mêmes tables et données,
avec les types natifs MySQL 8 (`decimal(10,2)`, `datetime(6)`, `utf8mb4`) :
31 tables, 38 clés étrangères nommées (`CONSTRAINT … FOREIGN KEY`), 80 index
et 26 contraintes `CHECK`. Import : phpMyAdmin → créer une base `dealtrack`
(interclassement `utf8mb4_unicode_ci`) → onglet **Importer** → choisir le
fichier. En ligne de commande :

```bash
mysql -u root -p dealtrack < database/dump_dealtrack_mysql.sql
```

Il a été produit avec les mêmes modèles et migrations, ce qui montre que le
projet est indépendant du moteur (ORM Django) :

```bash
cd backend
pip install mysqlclient==2.2.7                      # pilote MySQL (facultatif, hors requirements)
set MYSQL_OPTION_FILE=C:\chemin\vers\client.cnf   # identifiants MySQL, hors Git
python manage.py migrate --settings=config.settings.mysql
python manage.py seed_demo --settings=config.settings.mysql
python manage.py setup_roles --settings=config.settings.mysql
python manage.py export_dump --settings=config.settings.mysql --output ../database/dump_dealtrack_mysql.sql
```

Vérification : réimporté dans une base MySQL vierge, chaque table retrouve
exactement son nombre de lignes et ses 38 clés étrangères.

**Volume** : au moins 100 lignes par table métier, sauf les tables
naturellement limitées (6 catégories × 3 langues, 2 formules
d'abonnement, liaisons des droits du personnel).

| Table | Lignes | Origine des données |
|---|---|---|
| `deals_deal` | 129 | 137 vraies offres relevées le 7/11/2026 (Coolblue, Amazon.com.be, Proximus, Delhaize) |
| `deals_dealimage` | 135 | Photos produit des fiches Coolblue |
| `catalog_merchant` | 135 | 8 enseignes + 133 commerces indépendants réels (OpenStreetMap, licence ODbL) |
| `accounts_user` | 120 | Comptes fictifs aux noms belges courants, adresses `@example.be` |
| `deals_dealtranslation`, `deals_commenttranslation` | 254, 476 | Traductions NL et DE |
| `deals_comment`, `deals_vote`, `deals_alert` | 238, 616, 169 | Générés à partir de phrases réalistes FR/NL/DE |
| `payments_payment`, `payments_subscription` | 114, 105 | Paiements de démonstration (passerelle sandbox) |
| `moderation_*` | 120 à 603 | Décisions, signalements, journal d'audit |

Sécurité : les mots de passe sont hachés (Argon2) et les données de
`django_session` (jetons de connexion actifs) ne sont jamais exportées.

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
