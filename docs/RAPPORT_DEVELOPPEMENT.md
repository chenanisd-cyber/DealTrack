# Partie « Développement » — DealTrack.be

**Dépôt du code source :** https://github.com/chenanisd-cyber/DealTrack

---

## 1. Produits de développement et langages

### 1.1 Langages

| Langage | Usage | Volume |
|---|---|---|
| **Python 3.12** | logique applicative, modèles, API, tests | 8 366 lignes, 73 fichiers |
| **HTML / gabarits Django** | front-office et formulaires | 576 lignes, 16 fichiers |
| **CSS** | feuille de style unique, sans préprocesseur | 619 lignes |
| **SQL** | via l'ORM ; contraintes déclarées en Python, générées en SQL | 45 contraintes nommées |
| **gettext (.po)** | catalogues de traduction néerlandais et allemand | 2 972 lignes |
| **YAML** | intégration continue GitHub et GitLab | 2 fichiers |

Aucun JavaScript de framework n'est employé. Les rares interactions dynamiques
passent par des formulaires HTML classiques, ce qui garantit que l'application
fonctionne sans JavaScript activé — un choix qui simplifie aussi la protection
CSRF, puisque chaque action passe par un POST horodaté.

### 1.2 Cadriciel et bibliothèques

| Paquet | Version | Rôle |
|---|---|---|
| Django | 5.1.5 | cadriciel web, ORM, gabarits, administration |
| djangorestframework | 3.15.2 | API REST : sérialisation, permissions, limitation de débit |
| djangorestframework-simplejwt | 5.3.1 | jetons JWT pour les clients tiers |
| django-filter | 24.3 | filtres déclaratifs de l'API |
| django-axes | 7.0.0 | verrouillage après échecs de connexion répétés |
| argon2-cffi | 23.1.0 | hachage de mot de passe résistant au calcul GPU |
| psycopg | 3.2.3 | pilote PostgreSQL pour la production |
| gunicorn | 23.0.0 | serveur WSGI de production |

Huit dépendances seulement, toutes épinglées à une version précise. Chaque
ajout de dépendance est une surface d'attaque et une dette de maintenance
supplémentaires ; le projet en compte le minimum.

### 1.3 Outils de développement

| Outil | Rôle |
|---|---|
| **PyCharm Community** | environnement de développement |
| **Git** | gestion de versions, 35 commits thématiques |
| **GitHub Actions / GitLab CI** | intégration continue, 5 contrôles automatiques |
| **ruff** 0.8.4 | analyse statique et formatage |
| **pre-commit** | contrôles avant chaque commit |
| **SQLite** | base de données de développement |
| **PostgreSQL 16** | base de données de production, via docker compose |
| **Postman** | collection de 29 requêtes pour tester l'API |
| **gettext** | extraction et compilation des traductions |

---

## 2. Plan de programmation

### 2.1 Structure logique

L'application suit le patron **MVT** de Django (Modèle – Vue – Gabarit), avec
une couche de services intercalée pour les opérations transactionnelles.

```
                      ┌──────────────────────────┐
   Navigateur ───────▶│  URLs (i18n_patterns)    │
                      │  /fr/ /nl/ /de/          │
                      └────────────┬─────────────┘
                                   │
   Client REST ──────▶┌────────────┴─────────────┐
   (Postman, mobile)  │  /api/v1/ (hors langue)  │
                      └────────────┬─────────────┘
                                   ▼
                      ┌──────────────────────────┐
                      │  MIDDLEWARE              │
                      │  Sécurité · Session ·    │
                      │  Locale · CSRF · Auth ·  │
                      │  AuditTrail · Axes       │
                      └────────────┬─────────────┘
                                   ▼
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
     ┌─────────────────┐                      ┌──────────────────┐
     │  VUES HTML      │                      │  VUES API (DRF)  │
     │  apps/*/views   │                      │  apps/api/views  │
     └────────┬────────┘                      └────────┬─────────┘
              │        ┌──────────────────────┐        │
              ├───────▶│  FORMULAIRES         │        │
              │        │  validation serveur  │        │
              │        └──────────────────────┘        │
              │                                        │
              │        ┌──────────────────────┐        │
              │        │  SÉRIALISEURS        │◀───────┤
              │        │  liste blanche       │        │
              │        └──────────────────────┘        │
              │                                        │
              │        ┌──────────────────────┐        │
              │        │  PERMISSIONS         │◀───────┤
              │        │  classe + objet      │        │
              │        └──────────────────────┘        │
              ▼                                        ▼
     ┌──────────────────────────────────────────────────────────┐
     │  SERVICES                                                │
     │  purchase_subscription() · Vote.cast()                   │
     │  User.soft_delete() · User.anonymise()                   │
     └────────────────────────┬─────────────────────────────────┘
                              ▼
     ┌──────────────────────────────────────────────────────────┐
     │  MODÈLES + QuerySets                                     │
     │  Deal.objects.for_user() ← filtre d'accès unique         │
     └────────────────────────┬─────────────────────────────────┘
                              ▼
     ┌──────────────────────────────────────────────────────────┐
     │  BASE DE DONNÉES — 45 contraintes CHECK et UNIQUE        │
     └──────────────────────────────────────────────────────────┘
```

**Le principe directeur** : chaque règle métier est appliquée à plusieurs
niveaux, et le niveau le plus bas est la base de données. Un contrôle
applicatif peut être contourné par une requête concurrente ; une contrainte
SQL, non.

### 2.2 Découpage en applications

Le projet compte **six applications Django**, séparées par domaine métier et
non par couche technique. Ce découpage permet de lire l'intégralité d'un
domaine dans un seul dossier.

| Application | Responsabilité | Modèles |
|---|---|---|
| `accounts` | comptes, rôles, cycle de vie, RGPD | User |
| `catalog` | référentiels partagés | Region, Category, CategoryTranslation, Merchant |
| `deals` | cœur métier | Deal, DealTranslation, Vote, Comment, Alert |
| `payments` | monétisation et comptabilité | Plan, Payment, Subscription |
| `moderation` | traçabilité et contrôle éditorial | AuditLog, ModerationDecision, Report |
| `api` | exposition REST (aucun modèle propre) | — |

`api` ne définit aucun modèle : c'est une couche d'exposition qui réutilise les
modèles des autres applications. Cela évite la duplication de logique entre le
front-office et l'API.

### 2.3 Inventaire des modules et fonctions

Volumétrie globale : **98 classes, 44 fonctions de module, 267 méthodes**.

#### `apps/accounts` — Comptes et RGPD

| Module | Élément | Rôle |
|---|---|---|
| `models.py` | `Role` | Énumération des trois rôles : membre, modérateur, administrateur |
| | `UserQuerySet.active()` | Comptes non désinscrits — base de tous les écrans publics |
| | `UserQuerySet.deleted()` | Comptes désinscrits, pour le back-office |
| | `UserManager.create_user()` | Création avec normalisation de l'e-mail et validation complète |
| | `User.soft_delete()` | Désinscription sans destruction de la ligne |
| | `User.anonymise()` | Écrasement irréversible des données personnelles (art. 17 RGPD) |
| | `User.export_personal_data()` | Export structuré pour la portabilité (art. 20 RGPD) |
| | `User.is_moderator` / `is_administrator` | Propriétés de rôle, employées par les permissions |
| `validators.py` | `ComplexityValidator` | Trois classes de caractères sur quatre, rejet des suites de clavier |
| | `validate_be_vat()` | Format BE + clé de contrôle modulo 97 |
| | `validate_no_control_characters()` | Refus des caractères de contrôle et marques de direction Unicode |
| `forms.py` | `RegistrationForm` | Inscription, consentement marketing séparé des CGU |
| | `EmailAuthenticationForm` | Connexion par e-mail, message d'échec indifférencié |
| | `AlertForm` | Création d'alerte par mot-clé |
| `views.py` | `register()` | Inscription puis connexion automatique, tracée |
| | `profile()` | Espace personnel : deals, factures, droits RGPD |
| | `export_data()` | Téléchargement JSON des données personnelles |
| | `close_account()` | Fermeture avec confirmation explicite en POST |
| `admin.py` | `UserAdmin` | Actions « Désinscrire » et « Anonymiser », suppression retirée |
| `management/` | `demo_soft_delete` | Démonstration en quatre étapes avec vérification SQL brute |
| | `setup_roles` | Attribution des permissions Django aux rôles |

#### `apps/catalog` — Référentiels

| Module | Élément | Rôle |
|---|---|---|
| `models.py` | `Region` | Trois régions belges, clé primaire = code NUTS-1 Eurostat |
| | `Region.label()` / `label_current` | Libellé traduit, langue explicite ou langue active |
| | `Category` | Arbre de catégories, clé UUID |
| | `Category.label()` | Résolution du libellé avec repli sur le français |
| | `CategoryTranslation` | Une ligne par langue, unicité (catégorie, langue) |
| | `Merchant` | Enseigne, avec indicateur d'indépendant belge et TVA validée |
| `admin.py` | `CategoryTranslationInline` | Édition des libellés depuis la catégorie |
| `management/` | `seed_demo` | Jeu de données réaliste, reproductible (13 méthodes) |
| | `data_dictionary` | Génération du dictionnaire par introspection du schéma |

#### `apps/deals` — Cœur métier

| Module | Élément | Rôle |
|---|---|---|
| `models.py` | `DealStatus` | Cinq statuts : brouillon, en attente, publié, refusé, expiré |
| | `DealQuerySet.visible()` | Ce qu'un visiteur anonyme peut voir |
| | `DealQuerySet.for_user()` | **Filtre d'accès unique**, partagé par les vues HTML et l'API |
| | `Deal.publish()` / `reject()` | Décisions de modération, tracées et motivées |
| | `Deal.soft_delete()` | Retrait du flux sans casser votes et commentaires |
| | `Deal.recompute_temperature()` | Reconstruction du compteur depuis la table Vote |
| | `Deal.discount_percentage` | Remise calculée, jamais stockée |
| | `Deal.title_current` / `description_current` | Contenu dans la langue active, avec repli |
| | `DealTranslation` | Traduction d'une offre, une ligne par langue |
| | `Vote.cast()` | Vote transactionnel, mise à jour par `F()` |
| | `Comment.soft_delete()` | Suppression logique d'un commentaire |
| | `Alert` | Alerte par mot-clé, région et prix maximum |
| `forms.py` | `DealSubmissionForm` | Dépôt d'offre, statut imposé côté serveur |
| | `CommentForm` | Commentaire avec validation de longueur et de caractères |
| `views.py` | `deal_list()` | Flux filtrable, filtres validés contre le référentiel |
| | `deal_detail()` | Page de détail avec commentaires et vote de l'utilisateur |
| | `deal_submit()` | Formulaire de publication |
| | `deal_vote()` | Vote en POST exclusivement |
| | `comment_create()` | Ajout de commentaire |
| | `forbidden()` / `not_found()` / `server_error()` | Pages d'erreur sans trace technique |
| `admin.py` | `DealAdmin` | Trois actions groupées, suppression physique retirée |

#### `apps/payments` — Paiement

| Module | Élément | Rôle |
|---|---|---|
| `models.py` | `Plan` | Formule d'abonnement, prix et taux de TVA |
| | `Payment` | Transaction, `user` en `PROTECT` — verrou de conservation |
| | `Payment.next_reference()` | Numérotation séquentielle continue par exercice |
| | `Subscription.is_current` | Adhésion active et non expirée |
| `gateways.py` | `BaseGateway` | Interface commune aux prestataires |
| | `SandboxGateway` | Réponses déterministes hors ligne, pour tests et démonstration |
| | `StripeGateway` | Appel réel, idempotence, vérification de signature de webhook |
| | `get_gateway()` | Fabrique pilotée par le réglage `PAYMENT_GATEWAY` |
| `services.py` | `purchase_subscription()` | Orchestration transactionnelle du paiement |
| | `_vat_part()` | Extraction de la TVA d'un montant TVAC |
| `views.py` | `plans()` / `subscribe()` | Écrans de souscription, sans champ de carte |

#### `apps/moderation` — Traçabilité

| Module | Élément | Rôle |
|---|---|---|
| `models.py` | `AuditLog` | Piste d'audit en ajout seul, 17 types d'action |
| | `AuditLog.record()` | Point d'entrée unique : base + fichier de log |
| | `_client_ip()` | Extraction de l'IP réelle derrière un reverse proxy |
| | `ModerationDecision` | Trace nominative de chaque validation ou refus |
| | `Report` | Signalement de contenu par un membre |
| `middleware.py` | `AuditTrailMiddleware` | Journalisation des écritures et des refus d'accès |
| `signals.py` | `log_login()` / `log_login_failure()` | Branchement sur les signaux d'authentification |
| `views.py` | `csrf_failure()` | Page d'échec CSRF auditée |
| `management/` | `audit_report` | Rapport d'activité avec détection de signaux anormaux |

#### `apps/api` — Exposition REST

| Module | Élément | Rôle |
|---|---|---|
| `serializers.py` | `DealListSerializer` | Charge utile allégée pour le flux |
| | `DealDetailSerializer` | Vue complète d'une offre |
| | `DealWriteSerializer` | Création et modification, 8 méthodes de validation |
| | `CommentSerializer` / `VoteSerializer` | Commentaires et votes |
| `permissions.py` | `IsModerator` | Accès réservé à l'équipe de modération |
| | `ReadOnlyOrAuthenticated` | Lecture ouverte, écriture authentifiée |
| | `IsAuthorOrModerator` | **Permission d'objet**, refus audité |
| | `IsSelf` | Accès à ses propres ressources uniquement |
| `views.py` | `DealViewSet` | CRUD + actions `vote`, `publish`, `reject` |
| | `CommentViewSet` | Commentaires filtrés par offre visible |
| | `MeView` | Profil et effacement (art. 17) |
| | `MeExportView` | Portabilité (art. 20) |
| | `ModerationQueueViewSet` | File d'attente, lecture seule, réservée |
| `exceptions.py` | `api_exception_handler()` | Enveloppe d'erreur unique, aucune fuite |
| `throttles.py` | `VoteThrottle` / `DealWriteThrottle` / `TokenObtainThrottle` | Limitation par usage |

### 2.4 Enchaînements principaux

**Publication d'une offre**

```
Membre → formulaire /fr/publier/
  → DealSubmissionForm.clean()          validation croisée prix/référence
  → DealSubmissionForm.save()           statut imposé à PENDING
  → AuditLog.record(DEAL_SUBMITTED)     trace
  → l'offre n'apparaît pas dans le flux public

Modérateur → back-office → action « Publier »
  → Deal.publish(moderator=…)
      ├─ statut PUBLISHED + published_at
      ├─ ModerationDecision créée (nominative)
      └─ AuditLog.record(DEAL_PUBLISHED)
  → l'offre entre dans le flux
```

**Vote**

```
POST /deal/<slug>/vote/   (jamais GET)
  → Vote.cast() en transaction atomique
      ├─ select_for_update() sur le vote existant
      ├─ création, inversion, ou annulation si même sens
      └─ Deal.temperature mis à jour par F() — pas de lecture-modification-écriture
  → UniqueConstraint(deal, user) garantit une voix par membre
```

**Souscription**

```
POST /fr/abonnement/club-annuel/   avec un jeton du prestataire
  → purchase_subscription()  @transaction.atomic
      ├─ Payment créé AVANT l'appel externe (statut pending)
      ├─ AuditLog.record(PAYMENT_INITIATED)
      ├─ gateway.charge()  clé d'idempotence = (user, plan, token)
      ├─ succès → statut SUCCEEDED + Subscription créée
      └─ échec  → statut FAILED, aucun abonnement
```

**Désinscription**

```
POST /fr/comptes/profil/fermeture/   avec confirmation du pseudonyme
  → User.soft_delete()      deleted_at + is_active=False
  → si aucun paiement : User.anonymise()  immédiat
     sinon : conservation jusqu'à expiration du délai comptable
  → Payment.user en PROTECT : toute suppression physique lève ProtectedError
```

---

## 3. Commentaires

Le code compte environ **1 200 lignes de commentaires et docstrings**, soit un
ratio proche de 1 pour 7.

**Règle appliquée** : un commentaire explique une **décision**, jamais ce que
fait la ligne suivante. Un commentaire qui paraphrase le code est du bruit qui
se désynchronise à la première modification.

Exemple représentatif, dans `config/settings/base.py` :

```python
# Verrou sur le couple (IP, identifiant) : bloquer la seule IP punit les
# utilisateurs derrière un NAT partagé, bloquer le seul compte permet à un
# attaquant de verrouiller n'importe qui.
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
```

La ligne se lit toute seule. Le commentaire explique pourquoi ce réglage plutôt
qu'un autre — information qui n'existe nulle part ailleurs.

Chaque module porte une docstring qui énonce sa responsabilité et les
arbitrages qui l'ont façonné. Les modèles documentent leur choix de clé
primaire et leur comportement de suppression.

---

## 4. Standards respectés

### 4.1 Code

| Standard | Application |
|---|---|
| **PEP 8** | via ruff, 96 colonnes — 0 signalement sur l'ensemble du projet |
| **PEP 257** | docstrings sur tous les modules et classes publiques |
| **Conventional Commits** | `type(portée): description`, 35 commits |
| **EditorConfig** | indentation uniforme entre PyCharm, VS Code et les autres |

### 4.2 Sécurité

| Standard | Application |
|---|---|
| **OWASP Top 10** | A01 Broken Access Control, A02 défaillances cryptographiques (Argon2), A03 injection (ORM paramétré), A05 mauvaise configuration, A07 authentification |
| **OWASP ASVS** | politique de mot de passe, verrouillage, journalisation |
| **PCI-DSS SAQ-A** | aucune donnée de carte reçue ni stockée |
| **RFC 7519** | jetons JWT |
| **HSTS (RFC 6797)** | un an, sous-domaines inclus, preload |

### 4.3 Données et web

| Standard | Application |
|---|---|
| **3ᵉ forme normale** | aucune dépendance transitive ; la seule dénormalisation est documentée et recalculable |
| **ISO 4217** | codes de devise |
| **ISO 8601** | horodatages, UTC en base |
| **NUTS-1 Eurostat** | codes de région BE1, BE2, BE3 |
| **BCP 47** | codes de langue fr, nl, de |
| **WCAG 2.1 AA** | contrastes vérifiés, libellés de formulaire, navigation au clavier |
| **HTML5 sémantique** | `header`, `nav`, `main`, `article`, `aside`, `footer` |

### 4.4 Réglementaire

RGPD (règlement UE 2016/679), Code de droit économique belge (art. VI.18
annonce de réduction, VI.47 et VI.53 rétractation), CIR 92 art. 315
(conservation comptable de sept ans).

---

## 5. Étapes de test

### 5.1 Stratégie

Trois niveaux, du plus isolé au plus intégré. La règle suivie est qu'**une
mesure de sécurité qu'aucun test ne couvre est une intention, pas une
garantie**.

### 5.2 Tests unitaires — 41 tests

`tests/test_unit.py`, sans HTTP ni gabarit.

| Classe | Tests | Objet |
|---|---|---|
| `PasswordPolicyTests` | 6 | longueur, mots de passe courants, suites de clavier, similarité |
| `VatValidatorTests` | 4 | format et clé de contrôle du numéro de TVA belge |
| `DatabaseConstraintTests` | 10 | les contraintes SQL tiennent réellement |
| `VoteLogicTests` | 5 | vote, annulation, inversion, recalcul |
| `SoftDeleteTests` | 8 | `ProtectedError`, anonymisation, invariance de la clé |
| `PaymentTests` | 8 | succès, refus, TVA, numérotation, signature de webhook |
| `DealBusinessRuleTests` | 6 | remise, expiration, périmètre de visibilité |

### 5.3 Tests d'intégration — 60 tests

`tests/test_integration.py`, pile complète via HTTP.

| Classe | Tests | Exigence couverte |
|---|---|---|
| `CsrfProtectionTests` | 4 | jeton exigé, échec audité, GET refusé |
| `XssProtectionTests` | 4 | échappement, schémas d'URL, en-têtes |
| `BruteForceTests` | 4 | verrouillage, pas d'oracle d'existence, débit du jeton |
| `AccessControlTests` | 12 | trois rôles, permissions d'objet, refus audités |
| `ApiTests` | 14 | GET, POST, PATCH, DELETE, JWT, format d'erreur |
| `GdprTests` | 6 | export, fermeture, arbitrage avec la conservation |
| `MultilingualTests` | 8 | trois langues, repli, API non préfixée |
| `FormValidationTests` | 8 | mot de passe, doublons, HTTPS, injection d'URL |

### 5.4 Tests fonctionnels

**API en direct** — `scripts/api_demo.py` exécute 13 scénarios contre un
serveur réel et compare le code obtenu au code attendu. Résultat : 21 contrôles
conformes, 0 écart.

**Collection Postman** — 29 requêtes en 9 dossiers, avec chaînage automatique
du jeton. Exécutée intégralement : 29 conformes, 0 écart.

**Tests manuels dans le navigateur** — parcours des trois rôles, vérification
du multilingue sur les trois préfixes de langue, tentative d'accès direct par
URL à une ressource interdite.

### 5.5 Intégration continue

Cinq contrôles à chaque `push` : analyse statique, vérification du format,
absence de migration manquante, les 101 tests, contrôles de déploiement. Un
second travail rejoue la démonstration complète, appels API compris.

### 5.6 Résultat

```
Ran 101 tests in 1.05s
OK
```

Toutes les étapes ont été exécutées avant livraison, jamais seulement décrites.

---

## 6. Justification des choix techniques

### 6.1 Pourquoi Django

Le cahier des charges impose une base normalisée, une API REST, un back-office
sécurisé, un audit, du multilingue et des tests. Django fournit nativement
l'ORM avec contraintes déclaratives, l'administration, le système de
permissions, le cadre i18n et le lanceur de tests. Un cadriciel plus léger
aurait exigé d'assembler cinq bibliothèques et d'en assumer la cohérence.

Le coût assumé : Django impose ses conventions. Sur un projet à contraintes
fonctionnelles fortes et à délai contraint, c'est un avantage.

### 6.2 Trois stratégies de clé primaire

| Stratégie | Employée pour | Justification |
|---|---|---|
| **UUIDv4** | entités métier exposées par l'API | Invariante : l'e-mail et le pseudonyme changent, l'identifiant non. Non énumérable dans une URL, ce qui ferme la référence directe d'objet. Ne divulgue pas le volume d'inscriptions. Coût : 16 octets au lieu de 8. |
| **Code naturel** | `Region` (BE1/BE2/BE3) | Référentiel NUTS-1 Eurostat officiel, stable depuis 1988. Une clé technique n'apporterait rien et ajouterait une jointure. |
| **BigAutoField** | `AuditLog`, `Vote` | Tables en ajout seul où l'ordre d'insertion porte du sens. L'identifiant n'est jamais exposé. Un UUID aléatoire ferait perdre la localité d'index sans contrepartie. |

### 6.3 Table de traduction plutôt que colonnes par langue

`CategoryTranslation` et `DealTranslation` stockent une ligne par langue,
plutôt que des colonnes `name_fr`, `name_nl`, `name_de`.

Conséquence : ajouter une quatrième langue devient une **insertion de données**
au lieu d'une **migration de schéma**. L'unicité (entité, langue) est garantie
par la base. C'est aussi la forme normalisée : trois colonnes de libellé
constitueraient un groupe répétitif.

### 6.4 `PROTECT` sur `Payment.user`

C'est le verrou central du projet. Supprimer un membre ayant payé lève
`ProtectedError` — et **doit** la lever, l'article 315 du CIR 92 imposant sept
ans de conservation des pièces comptables.

La désinscription passe donc obligatoirement par `soft_delete()` puis
`anonymise()`. Le back-office ne propose même pas la suppression : il offre la
voie correcte à la place.

### 6.5 Dénormalisation assumée de `Deal.temperature`

Le compteur duplique une information dérivable de la table `Vote`. Recalculer
un `SUM` pour chaque carte du flux coûterait une agrégation par ligne affichée.

Trois garde-fous : la table `Vote` reste souveraine, `recompute_temperature()`
reconstruit le compteur à tout moment, et un test vérifie que les deux
concordent. La dénormalisation est documentée dans le dictionnaire de données.

### 6.6 API hors des préfixes de langue

`/api/v1/` vit en dehors des `i18n_patterns`. `/fr/api/v1/deals/` renvoie 404,
délibérément. Un client REST négocie la langue par l'en-tête `Accept-Language`,
pas par l'URL — c'est la sémantique HTTP.

### 6.7 Trois rôles, pas de permissions granulaires

Membre, modérateur, administrateur. Un système de permissions à grain fin
serait plus flexible et nettement plus difficile à auditer. Trois rôles se
vérifient d'un coup d'œil, ce qui compte davantage sur une application qui
manipule des données personnelles et des pièces comptables.

### 6.8 Abstraction de la passerelle de paiement

`BaseGateway` avec deux implémentations : `SandboxGateway` déterministe et hors
ligne, `StripeGateway` réelle. Le développement et les tests ne dépendent
d'aucun service externe, et changer de prestataire consiste à écrire une
troisième classe.

Dans les deux cas, **aucune donnée de carte n'atteint le serveur** : le
navigateur les échange contre un jeton chez le prestataire.

### 6.9 Verrou anti-force brute sur le couple (IP, identifiant)

Verrouiller la seule IP punit tous les utilisateurs derrière un NAT partagé —
une entreprise, une école, un opérateur mobile. Verrouiller le seul compte
permet à un attaquant de bloquer n'importe qui sans connaître son mot de passe.

Le couple ferme les deux failles. Un throttle séparé par IP sur
`/api/v1/auth/token/` couvre le cas restant : un mot de passe unique essayé
contre mille adresses ne déclenche jamais le verrou d'un compte donné.

### 6.10 404 plutôt que 403

Quand une ressource est hors du périmètre de lecture de l'appelant, l'API
renvoie 404. Répondre 403 confirmerait son existence, ce qui suffit à énumérer
les identifiants.

---

## 7. Difficultés rencontrées

### 7.1 Stockage des UUID selon le moteur

**Problème.** La commande de démonstration du soft delete renvoyait `None` sur
sa vérification SQL brute.

**Cause.** SQLite stocke un `UUIDField` en `char(32)` sans tirets, PostgreSQL
en type `uuid` natif. La requête paramétrée avec `str(user.pk)` ne trouvait
rien.

**Résolution.** Déléguer la conversion au backend plutôt que coder un format en
dur : `User._meta.pk.get_db_prep_value(user.pk, connection)`. Le code
fonctionne désormais sur les deux moteurs.

**Leçon.** Une requête SQL brute doit passer par la couche de conversion de
l'ORM, sinon elle est liée au moteur de développement.

### 7.2 Appel de méthode avec argument dans un gabarit

**Problème.** `{{ region.label(LANGUAGE_CODE) }}` levait une erreur de syntaxe.

**Cause.** Le langage de gabarit Django n'autorise pas les arguments d'appel,
par conception — c'est ce qui l'empêche de devenir un second langage de
programmation dans les vues.

**Résolution.** Ajout de propriétés `label_current` qui lisent la langue active
via `get_language()`.

### 7.3 `django-axes` incompatible avec `Client.login()`

**Problème.** Une trentaine de tests d'intégration échouaient avec
`AxesBackendRequestParameterRequired`.

**Cause.** `AxesStandaloneBackend` exige un objet `request` pour identifier
l'IP, que `Client.login()` ne transmet pas.

**Résolution.** Les tests dont l'authentification n'est pas l'objet passent par
`force_login()` avec backend explicite ; ceux qui testent le verrouillage
postent le vrai formulaire.

### 7.4 Requête HTTP partielle et contrainte NOT NULL

**Problème.** `IntegrityError: NOT NULL constraint failed:
moderation_auditlog.method`, transaction entière annulée.

**Cause.** `force_login()` fabrique un `HttpRequest()` nu dont `method` vaut
`None`.

**Résolution.** `AuditLog.record()` tolère désormais les requêtes partielles.
**Une trace incomplète vaut mieux qu'une transaction perdue** — le journal ne
doit jamais faire échouer l'opération qu'il observe.

### 7.5 Routeur DRF et route de liste

**Problème.** `DELETE /api/v1/me/` renvoyait 405.

**Cause.** Le routeur DRF ne mappe que `GET` et `POST` sur une route de liste.
La ressource « moi » n'ayant pas d'identifiant, aucune route de détail
n'existait.

**Résolution.** Conversion du `ViewSet` en deux `APIView` aux chemins
explicites.

### 7.6 Deux assertions de test elles-mêmes fausses

**Problème.** Deux tests échouaient alors que le code était correct.

Le test XSS exigeait l'absence du texte `onerror=alert` dans la page. Or ce
texte **subsiste normalement** : c'est du contenu affiché. Ce qui compte est
qu'aucune balise ne soit reconstituable — les chevrons sont convertis en
entités.

Le test de contrôle d'accès attendait 403 sur le `PATCH` d'un tiers. Le code
renvoie 404, et c'est **meilleur** : la ressource est filtrée avant
l'évaluation des permissions.

**Leçon.** Un test qui échoue ne signale pas nécessairement un défaut du code.

### 7.7 Permissions du modérateur — le défaut le plus instructif

**Problème.** Un modérateur se connectait au back-office et voyait
« Vous n'avez pas la permission de voir ou de modifier quoi que ce soit ».

**Cause.** `is_staff=True` ouvre la porte du back-office, mais Django exige en
plus une permission par modèle et par action. Aucune n'avait été attribuée. La
porte était ouverte, toutes les pièces fermées.

**Pourquoi les tests ne l'ont pas vu.** Le test existant vérifiait qu'un membre
ordinaire **ne voyait pas** le journal d'audit. Il passait. Personne ne
vérifiait qu'un modérateur **le voyait**. Une page vide satisfait les deux.

**Résolution.** Commande `setup_roles` créant un groupe « Modérateurs » avec 19
permissions, plus un test d'autorisation en regard du test d'interdiction.

**Leçon — la plus importante du projet.** Un test d'interdiction sans son test
d'autorisation ne prouve rien. Ce défaut a été trouvé en testant manuellement
les rôles dans le navigateur, pas par la suite automatisée. L'automatisation ne
remplace pas l'usage réel.

### 7.8 Traduction du contenu et non seulement de l'interface

**Problème.** Sur `/nl/`, l'interface s'affichait en néerlandais mais les
titres et descriptions des offres restaient en français.

**Cause.** Seul le contenant était traduit — les chaînes `{% trans %}`. Le
contenu, saisi par les membres, vivait dans des colonnes uniques.

**Résolution.** Table `DealTranslation` sur le modèle de `CategoryTranslation`,
avec propriétés de repli et badge signalant la langue de rédaction.

**Le piège de performance.** Les propriétés doivent **itérer** sur
`self.translations.all()` et non **filtrer** : un `.filter()` déclenche une
requête même après `prefetch_related`. Mesure sur un flux de huit offres : 8
requêtes contre 2.

### 7.9 Arbitrage entre droit à l'effacement et conservation comptable

**Problème.** L'article 17 du RGPD donne un droit à l'effacement. L'article 315
du CIR 92 impose sept ans de conservation des pièces comptables.

**Analyse.** Ces textes ne se contredisent pas : l'article 17.3.b prévoit
l'exception d'obligation légale.

**Résolution.** Deux opérations distinctes — `soft_delete()` coupe l'accès,
`anonymise()` écrase les données personnelles en conservant la clé primaire. La
facture reste rattachable à une entité comptable sans que celle-ci soit
identifiable.

C'est la difficulté la plus structurante du projet : elle a déterminé le choix
de `PROTECT`, la conception du back-office, et le comportement de l'API.

---

## 8. Points ouverts

Un rapport qui n'énonce que des réussites n'est pas crédible.

| Point | État |
|---|---|
| Content-Security-Policy | absente : les gabarits comportent des styles en ligne |
| Double authentification | absente pour les comptes à privilège |
| Cache `django-axes` | local ; un déploiement multi-processus exige Redis |
| Purge du journal d'audit | délai défini, tâche planifiée absente |
| Renonciation au droit de rétractation | mentionnée, non recueillie |
| Divulgation des liens d'affiliation | non implémentée |
| Statut d'hébergeur au regard du DSA | à soumettre à un juriste |
| Audit de sécurité externe | non réalisé |

Le cadre juridique décrit ici est celui d'un développeur, pas d'un juriste.
