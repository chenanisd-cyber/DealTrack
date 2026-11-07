# DealTrack.be – Django 5

## Équipe de développement

- Mohamed-Amine Chenani

## Description du projet

DealTrack.be est une plateforme communautaire de bons plans pour la Belgique.
Les membres publient des offres commerciales, votent pour faire remonter les
meilleures et commentent leur expérience.

L'application comprend :

- un catalogue d'offres, de marchands, de catégories et de régions,
- un système de vote et de commentaires,
- un back-office de modération avec journal d'audit,
- une API RESTful sécurisée par JWT,
- un abonnement payant avec passerelle de paiement,
- un front-office trilingue français / néerlandais / allemand.

Le projet tient compte du RGPD et du droit belge du commerce électronique :
annonce de réduction, conservation des pièces comptables, droit à l'oubli.

## Objectifs pédagogiques

- Structurer un projet Django complet en applications métier.
- Concevoir une base de données normalisée avec contraintes d'intégrité.
- Sécuriser une application contre les vulnérabilités du Top 10 OWASP.
- Exposer et sécuriser une API REST.
- Mettre en place des tests unitaires et d'intégration.
- Travailler avec Git et l'intégration continue.

## Structure du projet

Le dépôt est découpé en trois parties, chacune avec son propre README :

```
DealTrack/
├── backend/                    # Serveur : logique métier, sécurité, API (Python / Django)
│   ├── manage.py               # Point d'entrée des commandes Django
│   ├── requirements.txt        # Dépendances Python
│   ├── config/                 # Réglages (base, dev, test, prod), URL racines
│   ├── apps/
│   │   ├── accounts/           # Utilisateurs, rôles, RGPD
│   │   ├── catalog/            # Régions, catégories, marchands
│   │   ├── deals/              # Offres, votes, commentaires, alertes
│   │   ├── payments/           # Formules, paiements, abonnements
│   │   ├── moderation/         # Journal d'audit, décisions, signalements
│   │   └── api/                # API REST (sérialiseurs, vues, permissions)
│   ├── tests/                  # Tests unitaires et d'intégration
│   ├── scripts/                # Démonstration API, traductions, Postman
│   └── logs/                   # Journaux applicatifs et de sécurité
│
├── frontend/                   # Interface : ce que le navigateur reçoit
│   ├── templates/              # Gabarits HTML (Django templates)
│   ├── static/css/             # Feuille de style
│   └── locale/                 # Traductions néerlandaises et allemandes
│
├── database/                   # Données
│   ├── DATA_DICTIONARY.md      # Dictionnaire de données (généré depuis le schéma)
│   ├── docker-compose.yml      # PostgreSQL 16 local
│   ├── db.sqlite3              # Base SQLite de développement (non versionnée)
│   └── media/                  # Photos et logos envoyés (non versionnés)
│
├── docs/                       # Documentation technique (API, sécurité, RGPD…)
├── Makefile                    # Raccourcis : make run, make test…
└── pyproject.toml              # Configuration de ruff
```

Les modèles (tables) et les migrations restent dans `backend/apps/<module>/` :
Django les lie à leur application. `database/` regroupe ce qui concerne la
base elle-même : le fichier SQLite, PostgreSQL et la documentation du schéma.

## Installation et configuration

### Prérequis

- Python 3.11 minimum (3.12 recommandé)
- Git

Aucune base de données à installer : SQLite est utilisée en développement.

### Installation complète

```bash
git clone https://github.com/chenanisd-cyber/DealTrack.git
cd DealTrack

python -m venv .venv
.venv\Scripts\activate       # Windows
# ou
source .venv/bin/activate    # Linux / Mac

cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py setup_roles
python manage.py runserver
```

L'application est ensuite accessible sur : http://localhost:8000/fr/

Sous Windows, si PowerShell refuse le script d'activation :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Toutes les commandes `python manage.py …` se lancent depuis le dossier
`backend/`.

### Chargement des données de test

```bash
python manage.py seed_demo
```

Cette commande peuple la base avec 3 régions, 6 catégories traduites en 3
langues, 8 marchands réels, 10 comptes utilisateurs, 10 offres, des votes,
des commentaires traduits, 2 formules d'abonnement et 4 paiements.

Les 10 offres sont **de vrais deals** relevés le 7 novembre 2026 sur Coolblue,
Amazon.com.be, Proximus et Delhaize : titre, prix, prix barré, lien et photo
du marchand. Les prix évoluent : avant une démonstration, vérifiez-les sur les
sites et mettez à jour `DEALS` dans
`backend/apps/catalog/management/commands/seed_demo.py`, puis relancez
`python manage.py seed_demo --flush`. Les comptes et commentaires restent des
données de démonstration.

### Attribution des permissions

```bash
python manage.py setup_roles
```

Crée le groupe des modérateurs et lui attribue ses permissions. Sans cette
commande, un modérateur se connecte au back-office mais n'y voit rien :
`is_staff` ouvre l'accès, Django exige en plus une permission par modèle.

### Réinitialisation

```bash
rm ../database/db.sqlite3
python manage.py migrate
python manage.py seed_demo
python manage.py setup_roles
```

## Comptes de test

| Adresse | Rôle | Mot de passe |
|---|---|---|
| marc.vandenberghe@example.be | Membre | Demo-Tracker-2025 |
| moderation@dealtrack.be | Modérateur | Demo-Tracker-2025 |
| admin@dealtrack.be | Administrateur | Demo-Tracker-2025 |

Sept autres comptes membres existent, répartis sur les trois régions.

## Adresses de l'application

| URL | Contenu |
|---|---|
| /fr/ /nl/ /de/ | Front-office dans les trois langues |
| /fr/back-office/ | Administration |
| /api/v1/deals/ | API REST, lecture publique |

## Technologies utilisées

- Python 3.12
- Django 5.1.5
- Django REST Framework 3.15
- SimpleJWT (authentification par jeton)
- django-axes (protection contre la force brute)
- Argon2 (hachage des mots de passe)
- SQLite (développement) / PostgreSQL 16 (production)
- Gunicorn (serveur de production)
- Ruff (analyse statique)
- GitHub Actions et GitLab CI (intégration continue)

## Fonctionnalités par module

| Module | Fonctionnalités |
|---|---|
| accounts | Inscription, connexion, rôles, export RGPD, suppression logique, anonymisation |
| catalog | Régions NUTS-1, catégories multilingues, marchands avec validation TVA belge |
| deals | Publication, modération, vote, commentaires, alertes par mot-clé |
| payments | Formules d'abonnement, paiement par jeton, facturation numérotée |
| moderation | Journal d'audit en ajout seul, décisions tracées, signalements |
| api | CRUD sur les offres, vote, file de modération, points d'entrée RGPD |

## Tests

```bash
python manage.py test tests --settings=config.settings.test
```

142 tests, répartis en cinq fichiers dans `backend/tests/` :

| Fichier | Tests | Contenu |
|---|---|---|
| test_unit.py | 41 | Mots de passe, TVA belge, contraintes de base, vote, suppression logique, paiement |
| test_integration.py | 72 | CSRF, XSS, force brute, contrôle d'accès, API REST, RGPD, multilingue, formulaires |
| test_scraper.py | 11 | Protection SSRF du pré-remplissage par lien, limite d'appels, affichage des erreurs |
| test_images.py | 13 | Validation des photos envoyées, priorité photo / image externe / vignette du marchand |
| test_comments.py | 5 | Commentaires traduits selon la langue de la page, repli sur l'original |

## API REST

Base : `/api/v1/`

| Méthode | Chemin | Accès |
|---|---|---|
| GET | /deals/ | Public |
| GET | /deals/{id}/ | Public |
| POST | /deals/ | Membre |
| PATCH | /deals/{id}/ | Auteur ou modérateur |
| DELETE | /deals/{id}/ | Auteur ou modérateur |
| POST | /deals/{id}/vote/ | Membre |
| POST | /deals/{id}/publish/ | Modérateur |
| GET | /me/ | Membre |
| GET | /me/export/ | Membre |
| DELETE | /me/ | Membre |
| GET | /moderation/queue/ | Modérateur |
| POST | /auth/token/ | Public |

Une collection Postman de 29 requêtes est fournie dans
`docs/DealTrack.postman_collection.json`.

Démonstration en ligne de commande, avec le serveur démarré dans un autre
terminal :

```bash
python scripts/api_demo.py      # depuis backend/
```

## Commandes de gestion

| Commande | Rôle |
|---|---|
| seed_demo | Charge le jeu de données de test |
| setup_roles | Attribue les permissions aux rôles |
| demo_soft_delete --anonymise | Démontre la suppression logique et son impact en base |
| audit_report --days 30 | Produit le rapport d'audit d'activité |
| data_dictionary | Régénère le dictionnaire de données |

## Sécurité

| Protection | Mise en œuvre |
|---|---|
| CSRF | Middleware Django, jeton sur tous les formulaires, POST obligatoire |
| XSS | Échappement automatique des gabarits, validation des URL en HTTPS |
| Force brute | django-axes, 5 échecs, verrouillage de 15 minutes |
| Contrôle d'accès | Permissions de classe, permissions d'objet, queryset filtré |
| Mots de passe | Argon2, 12 caractères minimum, 5 validateurs |
| Injection SQL | ORM Django, requêtes paramétrées |
| Journalisation | Deux fichiers avec rotation, table AuditLog en ajout seul |

## Base de données

16 tables, avec clés étrangères, contraintes CHECK et contraintes d'unicité.

Trois stratégies de clé primaire sont employées :

- UUIDv4 pour les entités métier exposées par l'API,
- code NUTS-1 pour les régions (BE1, BE2, BE3),
- BigAutoField pour les tables en ajout seul.

Le détail figure dans `database/DATA_DICTIONARY.md` (régénéré par `make dict`).

## Documentation

| Fichier | Contenu |
|---|---|
| docs/RAPPORT_DEVELOPPEMENT.md | Plan de programmation, modules, choix techniques, difficultés |
| database/DATA_DICTIONARY.md | Dictionnaire de données généré depuis le schéma |
| docs/SECURITY.md | Protections mises en œuvre |
| docs/API.md | Documentation de l'API |
| docs/LEGAL_GDPR.md | RGPD et droit belge |
| DEVELOPMENT.md | Configuration de l'IDE et conventions |

## Licence

Projet académique – Bachelier en Informatique de Gestion.
Licence MIT (voir LICENSE).
