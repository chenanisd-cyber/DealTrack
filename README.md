# DealTrack.be – Django 5

## Équipe de développement

- Mohamed-Amine Chenani

## Description du projet

DealTrack.be est une plateforme communautaire de bons plans pour la Belgique.
Les membres publient des offres commerciales, votent pour faire remonter les
meilleures et commentent leur expérience.

L'application comprend :

- un catalogue d'offres, de marchands et de catégories,
- un système de vote et de commentaires,
- un back-office de modération avec journal d'audit,
- une API RESTful sécurisée par JWT,
- un abonnement VIP payant (historique des prix, comparaison, alertes en
  priorité) avec passerelle de paiement,
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
│   │   ├── catalog/            # Catégories, marchands
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

Cette commande peuple **toutes les tables avec au moins 100 lignes** (sauf
les tables naturellement limitées : catégories, formules) : 120
comptes, 135 marchands dont 133 commerces indépendants réels (OpenStreetMap),
129 offres réelles, 600+ votes, 238 commentaires traduits, 114 paiements…
Le détail et le DUMP SQL sont décrits dans `database/README.md`.

Les 20 offres rédigées à la main sont **de vrais deals** relevés le 7 novembre 2026 sur Coolblue,
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

Marc est membre VIP : il voit l'historique des prix et la comparaison sur la
page d'un deal. Déconnecté, la même page montre l'aperçu verrouillé.

## Adresses de l'application

| URL | Contenu |
|---|---|
| /fr/ /nl/ /de/ | Front-office dans les trois langues |
| /fr/publier/ | Publier un deal : coller le lien suffit |
| /fr/commercants-locaux/ | Annuaire des commerçants indépendants |
| /fr/abonnement/ | Abonnement VIP et paiement |
| /fr/comptes/alertes/ | Mes alertes (VIP : reçues en priorité) |
| /fr/back-office/ | Administration |
| /api/v1/deals/ | API REST, lecture publique |

## Page d'accueil

- **Bannière saisonnière** : « Black November » en novembre, « Black December »
  en décembre (choisie d'après la date du jour, `apps/deals/season.py`) ; aucune
  bannière le reste de l'année.
- **Onglets de tri** Tendance / Nouveaux / Prix croissant sur un bandeau pleine
  largeur, avec un titre propre à chaque onglet.
- **Deux emplacements publicitaires** (colonne de gauche, colonne de droite) :
  annonces maison (abonnement VIP, commerçants locaux). Pas de régie ni de
  script tiers, donc aucun traceur à déclarer au titre du RGPD. Sur petit écran,
  seule la publicité de la colonne de droite reste affichée.

## Abonnement VIP

| Avantage | Fonctionnement |
|---|---|
| Historique du prix | Table `deals_pricepoint` : un relevé à la publication, un à chaque changement de prix, un par passage du suivi automatique. Graphique SVG dessiné côté serveur. Aucun prix inventé. |
| Comparaison | Même produit chez les autres marchands de DealTrack, recherche en direct sur Amazon.com.be (mise en cache 12 h) et liens de recherche Coolblue, bol.com, MediaMarkt, Krëfel. |
| Alertes en priorité | À la publication d'un deal, chaque alerte qui correspond crée une ligne `deals_alertmatch`. Disponible tout de suite pour un VIP, 2 heures plus tard pour les autres. |

Tâches à planifier (une fois par jour pour les prix, toutes les 10 minutes pour
les alertes) :

```bash
python manage.py track_prices    # relit les pages des deals, note les changements de prix
python manage.py send_alerts     # envoie par e-mail les alertes arrivées à échéance
```

## Publier un deal en collant un lien

Comme sur les grands sites de deals : le membre colle le lien de l'offre, le
serveur lit la page et pré-remplit le formulaire (titre, photo, prix, prix de
référence légal des 30 derniers jours, marchand reconnu d'après le domaine,
description). Sources : données structurées schema.org (JSON-LD), balises
Open Graph, repères Amazon. Un site qui bloque les robots (ex. Coolblue) n'est
pas contourné : le membre complète alors les champs. Protections : voir
`docs/SECURITY.md` (SSRF).

## Commerçants locaux (OpenStreetMap)

L'annuaire `/fr/commercants-locaux/` liste des commerces indépendants réels.
Les données viennent d'OpenStreetMap (licence ODbL, attribution affichée),
pas de Google Maps : l'API Google Places est payante et ses conditions
interdisent de recopier les fiches. Pour ajouter une ville :

```bash
python manage.py import_local_merchants --area "Gent"
python manage.py import_local_merchants --area "Bruxelles - Brussel" --admin-level 8
```

Les commerces importés arrivent « non vérifiés » ; la modération confirme.

## Paiement

Bouton « Payer » → page de paiement sécurisée du prestataire (Stripe Checkout :
Bancontact, Visa, Mastercard, 3D Secure) → retour sur DealTrack. Le numéro de
carte ne passe jamais par nos serveurs (PCI-DSS SAQ-A). Au retour, le serveur
demande lui-même au prestataire si la session est payée (aucun paramètre d'URL
n'est cru) ; un webhook signé (HMAC) couvre le cas où le membre ferme son
navigateur. Case obligatoire de renonciation au droit de rétractation pour un
démarrage immédiat (art. VI.53 CDE).

- **Sans clés Stripe** (`PAYMENT_GATEWAY=sandbox`, par défaut) : une page de
  paiement de démonstration remplace celle de Stripe.
- **Avec Stripe en mode test** : créez un compte Stripe, puis créez un fichier
  `.env` à la racine du dépôt (ignoré par git) :

  ```
  PAYMENT_GATEWAY=stripe
  STRIPE_SECRET_KEY=sk_test_…
  ```

  Seules `PAYMENT_GATEWAY`, `STRIPE_SECRET_KEY` et `STRIPE_WEBHOOK_SECRET` sont
  lues dans ce fichier. Carte de test : 4242 4242 4242 4242 ; Bancontact
  s'active dans le tableau de bord Stripe (Paramètres → Moyens de paiement).
- **Clé « live » refusée hors production** : une clé `sk_live_…` (vrai argent)
  n'est acceptée qu'avec `config.settings.prod`. En démonstration, aucun débit
  réel n'est possible par erreur.
- **Webhook** (facultatif en démonstration, le retour sur le site suffit) :
  `https://<site>/fr/abonnement/webhook/stripe/`, événement
  `checkout.session.completed`, secret `whsec_…` dans `STRIPE_WEBHOOK_SECRET`.

## Partager le site (lien WhatsApp)

```powershell
powershell -ExecutionPolicy Bypass -File .\partager.ps1
```

Le script démarre le site en mode partage (`config.settings.share` : DEBUG
désactivé, cookies HTTPS, back-office fermé aux visiteurs d'Internet) et ouvre
un tunnel Cloudflare gratuit. Il affiche un lien `https://….trycloudflare.com`
à envoyer sur WhatsApp. Le lien marche tant que la fenêtre reste ouverte et
change à chaque lancement. `cloudflared.exe` est attendu dans `.tools/`
(téléchargement officiel : github.com/cloudflare/cloudflared/releases).

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
| catalog | Catégories multilingues, marchands avec validation TVA belge |
| deals | Publication, modération, vote, commentaires, alertes par mot-clé |
| payments | Formules d'abonnement, paiement par jeton, facturation numérotée |
| moderation | Journal d'audit en ajout seul, décisions tracées, signalements |
| api | CRUD sur les offres, vote, file de modération, points d'entrée RGPD |

## Tests

```bash
python manage.py test tests --settings=config.settings.test
```

197 tests, répartis en dix fichiers dans `backend/tests/` :

| Fichier | Tests | Contenu |
|---|---|---|
| test_unit.py | 41 | Mots de passe, TVA belge, contraintes de base, vote, suppression logique, paiement |
| test_integration.py | 72 | CSRF, XSS, force brute, contrôle d'accès, API REST, RGPD, multilingue, formulaires |
| test_scraper.py | 11 | Protection SSRF du pré-remplissage par lien, limite d'appels, affichage des erreurs |
| test_images.py | 13 | Validation des photos envoyées, priorité photo / image externe / vignette du marchand |
| test_comments.py | 5 | Commentaires traduits selon la langue de la page, repli sur l'original |
| test_checkout.py | 12 | Paiement hébergé : parcours, fraude au retour, idempotence, webhook, Stripe Checkout (simulé), clé live refusée, fichier .env |
| test_dump.py | 4 | DUMP SQL : structure, clés, contraintes, sessions exclues, rechargement |
| test_home.py | 6 | Bannière Black November / Black December selon le mois, titres des onglets, tri gardé à la page suivante, publicités sans script tiers |
| test_vip.py | 14 | Abonnement VIP : historique du prix, graphique, comparaison réservée, alertes en priorité, régions supprimées |
| test_live_features.py | 19 | Lecture du prix, marchand automatique, assistant de publication, vote en direct, annuaire, mode partage |

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
| import_local_merchants --area … | Importe des commerçants indépendants depuis OpenStreetMap |
| export_dump | Exporte le DUMP SQL complet (structure + données) : SQLite, ou MySQL avec `--settings=config.settings.mysql` |

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

Deux stratégies de clé primaire sont employées :

- UUIDv4 pour les entités métier exposées par l'API,
- BigAutoField pour les tables en ajout seul (journal, votes, historique des prix).

Le détail figure dans `database/DATA_DICTIONARY.md` (régénéré par `make dict`).

## Documentation

| Fichier | Contenu |
|---|---|
| docs/RAPPORT_DEVELOPPEMENT.md | Plan de programmation, modules, choix techniques, difficultés |
| database/DATA_DICTIONARY.md | Dictionnaire de données généré depuis le schéma |
| docs/uml/index.html | Diagrammes UML 2 : cas d'utilisation, classes, états-transitions (deal, paiement, compte) — imprimable en A4 paysage |
| docs/SECURITY.md | Protections mises en œuvre |
| docs/API.md | Documentation de l'API |
| docs/LEGAL_GDPR.md | RGPD et droit belge |
| docs/BUSINESS_PLAN.md | Positionnement, concurrence, SWOT, modèle économique, seuil de rentabilité |
| DEVELOPMENT.md | Configuration de l'IDE et conventions |

## Licence

Projet académique – Bachelier en Informatique de Gestion.
Licence MIT (voir LICENSE).
