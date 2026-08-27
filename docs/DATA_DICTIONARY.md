# Dictionnaire de données — DealTrack.be
> Document généré depuis le schéma réel par `python3 manage.py data_dictionary`.
> Il ne peut donc pas diverger des modèles.

## Conventions
**Clés primaires.** Trois stratégies coexistent, chacune motivée :

| Stratégie | Employée pour | Motif |
|---|---|---|
| `UUIDv4` | entités métier exposées par l'API | invariante, non énumérable, ne divulgue pas le volume de la base |
| code naturel | `catalog_region` (NUTS-1) | référentiel officiel Eurostat, stable depuis 1988 ; une clé technique n'apporterait rien |
| `BIGINT` auto | tables en ajout seul (`moderation_auditlog`, `deals_vote`) | l'ordre d'insertion porte du sens, l'identifiant n'est jamais exposé, et l'index conserve sa localité |

**Suppression.** Aucune entité rattachée à une transaction n'est supprimée physiquement. Les colonnes `deleted_at` portent la suppression logique ; `anonymised_at` marque l'effacement des données personnelles.

**Horodatage.** Toutes les colonnes temporelles sont en UTC (`USE_TZ = True`), converties à l'affichage vers `Europe/Brussels`.

**Montants.** `DECIMAL` et jamais `FLOAT` : un montant en virgule flottante introduit des écarts d'arrondi inacceptables sur une pièce comptable.

## Vue d'ensemble

| Table | Rôle | Clé primaire | Lignes en démo |
|---|---|---|---|
| `accounts_user` | utilisateurs | id · UUID | 10 |
| `catalog_category` | catégories | id · UUID | 6 |
| `catalog_categorytranslation` | libellés de catégorie | id · BIGINT auto | 18 |
| `catalog_merchant` | marchands | id · UUID | 11 |
| `catalog_region` | régions | code · VARCHAR | 3 |
| `deals_alert` | alertes | id · UUID | 0 |
| `deals_comment` | commentaires | id · UUID | 14 |
| `deals_deal` | deals | id · UUID | 10 |
| `deals_vote` | votes | id · BIGINT auto | 32 |
| `payments_payment` | paiements | id · UUID | 4 |
| `payments_plan` | formules | id · UUID | 2 |
| `payments_subscription` | abonnements | id · UUID | 4 |
| `moderation_auditlog` | journal d'audit | id · BIGINT auto | 0 |
| `moderation_moderationdecision` | décisions de modération | id · UUID | 7 |
| `moderation_report` | signalements | id · UUID | 3 |

---

## Comptes
Membres, rôles et cycle de vie du compte.

### `accounts_user`
User(password, last_login, is_superuser, id, email, display_name, role, preferred_language, home_region, is_active, is_staff, date_joined, deleted_at, anonymised_at, accepted_terms_at, marketing_consent)

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `password` | VARCHAR(128) | non | — | — |
| `last_login` | TIMESTAMP | oui | — | — |
| `is_superuser` | BOOLEAN | non | `False` | Précise que l’utilisateur possède toutes les permissions sans les assigner explicitement. |
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `email` | VARCHAR(254) | non | — | unique · Sert d'identifiant de connexion. Stockée en minuscules. |
| `display_name` | VARCHAR(40) | non | — | unique · Nom affiché publiquement à côté des deals et commentaires. |
| `role` | VARCHAR(20) | non | `member` | indexée · valeurs : `member`, `moderator`, `admin` |
| `preferred_language` | VARCHAR(5) | non | `fr` | valeurs : `fr`, `nl`, `de` |
| `home_region_id` | FK | oui | — | indexée · → `catalog_region` · `PROTECT` · _bloque la suppression physique du parent_ · Sert à trier les deals de proximité. Facultatif. |
| `is_active` | BOOLEAN | non | `True` | — |
| `is_staff` | BOOLEAN | non | `False` | — |
| `date_joined` | TIMESTAMP | non | `now` | — |
| `deleted_at` | TIMESTAMP | oui | — | indexée · Renseigné à la désinscription. La ligne n'est jamais supprimée. |
| `anonymised_at` | TIMESTAMP | oui | — | Renseigné une fois les données personnelles écrasées. |
| `accepted_terms_at` | TIMESTAMP | oui | — | — |
| `marketing_consent` | BOOLEAN | non | `False` | Consentement explicite, distinct des CGU (art. 7 RGPD). |
| `groups` | M2M | — | — | table de liaison `accounts_user_groups` vers `auth_group` |
| `user_permissions` | M2M | — | — | table de liaison `accounts_user_user_permissions` vers `auth_permission` |

**Contraintes de table**
- `user_anonymised_implies_deleted` — vérification : `(OR: ('anonymised_at__isnull', True), ('deleted_at__isnull', False))`

**Index** : `user_role_active_idx`

---

## Catalogue
Référentiels partagés : régions, catégories, marchands.

### `catalog_category`
Arbre de catégories sur un seul niveau de profondeur en pratique.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `slug` | VARCHAR (slug)(60) | non | — | unique |
| `parent_id` | FK | oui | — | indexée · → `catalog_category` · `PROTECT` · _bloque la suppression physique du parent_ |
| `position` | SMALLINT ≥ 0 | non | `0` | — |
| `is_active` | BOOLEAN | non | `True` | — |

**Contraintes de table**
- `category_no_self_parent` — vérification : `(NOT (AND: ('parent', F(id))))`

### `catalog_categorytranslation`
Libellés de catégorie, une ligne par langue.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | BIGINT auto | non | auto | **clé primaire** |
| `category_id` | FK | non | — | indexée · → `catalog_category` · `CASCADE` |
| `language` | VARCHAR(5) | non | — | — |
| `name` | VARCHAR(80) | non | — | — |

**Contraintes de table**
- `uniq_category_language` — unicité sur `category`, `language`

### `catalog_merchant`
Enseigne chez qui le deal est disponible.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `name` | VARCHAR(120) | non | — | — |
| `slug` | VARCHAR (slug)(120) | non | — | unique |
| `country` | VARCHAR(2) | non | `BE` | indexée · valeurs : `BE`, `NL`, `FR`, `DE`, `LU` |
| `website` | VARCHAR(300) | non | — | — |
| `vat_number` | VARCHAR(20) | non | — | Format belge uniquement, contrôlé par sa clé modulo 97. |
| `is_local_independent` | BOOLEAN | non | `False` | Déclenche le badge « Commerçant local » dans le flux. |
| `is_verified` | BOOLEAN | non | `False` | Vérifiée par la modération : identité et site marchand contrôlés. |
| `created_at` | TIMESTAMP | non | — | — |

**Contraintes de table**
- `merchant_local_implies_be` — vérification : `(OR: ('is_local_independent', False), ('country', 'BE'))`
- `merchant_vat_implies_be` — vérification : `(OR: ('vat_number', ''), ('country', 'BE'))`

### `catalog_region`
Les trois régions belges, identifiées par leur code NUTS-1 Eurostat.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `code` | VARCHAR(3) | non | — | **clé primaire** |
| `name_fr` | VARCHAR(60) | non | — | — |
| `name_nl` | VARCHAR(60) | non | — | — |
| `name_de` | VARCHAR(60) | non | — | — |

---

## Offres
Cœur métier : deals, votes, discussion, alertes.

### `deals_alert`
Alerte par mot-clé : la fonctionnalité « ne rien manquer » du projet.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `user_id` | FK | non | — | indexée · → `accounts_user` · `CASCADE` |
| `keyword` | VARCHAR(80) | non | — | — |
| `category_id` | FK | oui | — | indexée · → `catalog_category` · `CASCADE` |
| `region_id` | FK | oui | — | indexée · → `catalog_region` · `PROTECT` · _bloque la suppression physique du parent_ |
| `max_price` | DECIMAL(10,2) | oui | — | — |
| `is_active` | BOOLEAN | non | `True` | — |
| `created_at` | TIMESTAMP | non | — | — |
| `last_notified_at` | TIMESTAMP | oui | — | — |

**Contraintes de table**
- `uniq_alert_per_user_criteria` — unicité sur `user`, `keyword`, `category`, `region`
- `alert_max_price_positive` — vérification : `(OR: ('max_price__isnull', True), ('max_price__gt', 0))`

### `deals_comment`
Comment(id, deal, author, body, is_verified_purchase, created_at, deleted_at)

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `deal_id` | FK | non | — | indexée · → `deals_deal` · `CASCADE` |
| `author_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `body` | TEXT | non | — | — |
| `is_verified_purchase` | BOOLEAN | non | `False` | — |
| `created_at` | TIMESTAMP | non | — | indexée |
| `deleted_at` | TIMESTAMP | oui | — | — |

### `deals_deal`
Deal(id, title, slug, description, external_url, price, reference_price, currency, shipping_cost, merchant, category, submitted_by, status, is_cross_border, language, starts_at, ends_at, published_at, temperature, created_at, updated_at, deleted_at)

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `title` | VARCHAR(140) | non | — | — |
| `slug` | VARCHAR (slug)(160) | non | — | unique |
| `description` | TEXT | non | — | — |
| `external_url` | VARCHAR(600) | non | — | — |
| `price` | DECIMAL(10,2) | non | — | — |
| `reference_price` | DECIMAL(10,2) | oui | — | Prix le plus bas pratiqué par le marchand durant les 30 jours précédents (Code de droit économique, art. VI.18). |
| `currency` | VARCHAR(3) | non | `EUR` | — |
| `shipping_cost` | DECIMAL(8,2) | non | `0.00` | — |
| `merchant_id` | FK | non | — | indexée · → `catalog_merchant` · `PROTECT` · _bloque la suppression physique du parent_ |
| `category_id` | FK | non | — | indexée · → `catalog_category` · `PROTECT` · _bloque la suppression physique du parent_ |
| `submitted_by_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `status` | VARCHAR(20) | non | `pending` | indexée · valeurs : `draft`, `pending`, `published`, `rejected`, `expired` |
| `is_cross_border` | BOOLEAN | non | `False` | — |
| `language` | VARCHAR(5) | non | `fr` | valeurs : `fr`, `nl`, `de` |
| `starts_at` | TIMESTAMP | non | `now` | — |
| `ends_at` | TIMESTAMP | oui | — | — |
| `published_at` | TIMESTAMP | oui | — | indexée |
| `temperature` | INT | non | `100` | indexée · Compteur dérivé de la table Vote, recalculable. |
| `created_at` | TIMESTAMP | non | — | — |
| `updated_at` | TIMESTAMP | non | — | — |
| `deleted_at` | TIMESTAMP | oui | — | indexée |
| `regions` | M2M | — | — | table de liaison `deals_deal_regions` vers `catalog_region` |

**Contraintes de table**
- `deal_price_non_negative` — vérification : `(AND: ('price__gte', 0))`
- `deal_shipping_non_negative` — vérification : `(AND: ('shipping_cost__gte', 0))`
- `deal_reference_price_above_price` — vérification : `(OR: ('reference_price__isnull', True), ('reference_price__gt', F(price)))`
- `deal_ends_after_start` — vérification : `(OR: ('ends_at__isnull', True), ('ends_at__gt', F(starts_at)))`
- `deal_published_requires_date` — vérification : `(OR: (NOT (AND: ('status', 'published'))), ('published_at__isnull', False))`

**Index** : `deal_status_pub_idx`, `deal_merchant_status_idx`

### `deals_vote`
Un vote par membre et par deal. La contrainte d'unicité est portée par la base : c'est la seule couche que deux requêtes concurrentes ne peuvent pas contourner.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | BIGINT auto | non | auto | **clé primaire** |
| `deal_id` | FK | non | — | indexée · → `deals_deal` · `CASCADE` |
| `user_id` | FK | non | — | indexée · → `accounts_user` · `CASCADE` |
| `value` | SMALLINT | non | — | valeurs : `-1`, `1` |
| `created_at` | TIMESTAMP | non | — | — |
| `updated_at` | TIMESTAMP | non | — | — |

**Contraintes de table**
- `uniq_vote_per_user_deal` — unicité sur `deal`, `user`
- `vote_value_is_minus_one_or_one` — vérification : `(AND: ('value__in', [-1, 1]))`

---

## Paiements
Abonnement Club, transactions, pièces comptables.

### `payments_payment`
Transaction. Immuable une fois aboutie : un remboursement crée une nouvelle ligne de sens inverse plutôt que de réécrire l'originale, comme en comptabilité en partie double.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `reference` | VARCHAR(30) | non | — | unique · Format DT-AAAA-NNNNNN, séquentiel et sans rupture. |
| `user_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `plan_id` | FK | non | — | indexée · → `payments_plan` · `PROTECT` · _bloque la suppression physique du parent_ |
| `amount` | DECIMAL(10,2) | non | — | — |
| `vat_amount` | DECIMAL(10,2) | non | — | — |
| `currency` | VARCHAR(3) | non | `EUR` | — |
| `status` | VARCHAR(20) | non | `pending` | indexée · valeurs : `pending`, `succeeded`, `failed`, `refunded` |
| `gateway` | VARCHAR(30) | non | `sandbox` | — |
| `gateway_reference` | VARCHAR(120) | non | — | unique · Identifiant côté prestataire. Unique : garantit l'idempotence. |
| `card_last4` | VARCHAR(4) | non | — | — |
| `card_brand` | VARCHAR(20) | non | — | — |
| `created_at` | TIMESTAMP | non | — | indexée |
| `settled_at` | TIMESTAMP | oui | — | — |

**Contraintes de table**
- `payment_amount_non_negative` — vérification : `(AND: ('amount__gte', 0))`
- `payment_vat_within_amount` — vérification : `(AND: ('vat_amount__gte', 0), ('vat_amount__lte', F(amount)))`
- `payment_succeeded_requires_settled_at` — vérification : `(OR: (NOT (AND: ('status', 'succeeded'))), ('settled_at__isnull', False))`

**Index** : `payment_user_date_idx`

### `payments_plan`
Formule d'abonnement. Le prix est historisé sur le paiement, pas ici.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `code` | VARCHAR (slug)(30) | non | — | unique |
| `name_fr` | VARCHAR(80) | non | — | — |
| `name_nl` | VARCHAR(80) | non | — | — |
| `name_de` | VARCHAR(80) | non | — | — |
| `price` | DECIMAL(8,2) | non | — | — |
| `vat_rate` | DECIMAL(4,2) | non | `21.00` | Taux belge standard : 21 %. |
| `duration_days` | SMALLINT ≥ 0 | non | `365` | — |
| `is_active` | BOOLEAN | non | `True` | — |

**Contraintes de table**
- `plan_price_non_negative` — vérification : `(AND: ('price__gte', 0))`
- `plan_duration_positive` — vérification : `(AND: ('duration_days__gt', 0))`

### `payments_subscription`
Adhésion Club active, dérivée d'un paiement abouti.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `user_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `plan_id` | FK | non | — | indexée · → `payments_plan` · `PROTECT` · _bloque la suppression physique du parent_ |
| `payment_id` | FK unique | non | — | unique |
| `status` | VARCHAR(20) | non | `active` | valeurs : `active`, `expired`, `cancelled` |
| `started_at` | TIMESTAMP | non | `now` | — |
| `ends_at` | TIMESTAMP | non | — | — |
| `cancelled_at` | TIMESTAMP | oui | — | — |

**Contraintes de table**
- `subscription_ends_after_start` — vérification : `(AND: ('ends_at__gt', F(started_at)))`

---

## Modération et audit
Piste d'audit, décisions, signalements.

### `moderation_auditlog`
AuditLog(id, actor, actor_label, action, target_type, target_id, ip_address, user_agent, path, method, metadata, created_at)

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | BIGINT auto | non | auto | **clé primaire** |
| `actor_id` | FK | oui | — | indexée · → `accounts_user` · `SET_NULL` |
| `actor_label` | VARCHAR(80) | non | — | Pseudonyme figé au moment de l'action, pour survivre à l'anonymisation. |
| `action` | VARCHAR(40) | non | — | indexée · valeurs : `user.registered`, `user.login`, `user.login_failed`, `user.soft_deleted`, `user.anonymised`, `user.data_exported` |
| `target_type_id` | FK | oui | — | indexée · → `django_content_type` · `SET_NULL` |
| `target_id` | VARCHAR(40) | non | — | — |
| `ip_address` | INET | oui | — | — |
| `user_agent` | VARCHAR(300) | non | — | — |
| `path` | VARCHAR(300) | non | — | — |
| `method` | VARCHAR(10) | non | — | — |
| `metadata` | JSON | non | `dict` | — |
| `created_at` | TIMESTAMP | non | — | indexée |

**Index** : `audit_action_date_idx`, `audit_actor_date_idx`

### `moderation_moderationdecision`
Trace nominative de chaque validation ou refus d'offre.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `deal_id` | FK | non | — | indexée · → `deals_deal` · `CASCADE` |
| `moderator_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `decision` | VARCHAR(20) | non | — | valeurs : `approved`, `rejected`, `expired` |
| `reason` | VARCHAR(300) | non | — | — |
| `created_at` | TIMESTAMP | non | — | — |

**Contraintes de table**
- `rejection_requires_reason` — vérification : `(OR: (NOT (AND: ('decision', 'rejected'))), (NOT (AND: ('reason', ''))))`

### `moderation_report`
Signalement d'un contenu par un membre.

| Colonne | Type | Null | Défaut | Contraintes et rôle |
|---|---|---|---|---|
| `id` | UUID | non | `uuid4` | **clé primaire** |
| `deal_id` | FK | non | — | indexée · → `deals_deal` · `CASCADE` |
| `reporter_id` | FK | non | — | indexée · → `accounts_user` · `PROTECT` · _bloque la suppression physique du parent_ |
| `reason` | VARCHAR(30) | non | — | valeurs : `out_of_stock`, `wrong_price`, `misleading`, `affiliate`, `spam` |
| `detail` | VARCHAR(500) | non | — | — |
| `status` | VARCHAR(20) | non | `open` | indexée · valeurs : `open`, `resolved`, `dismissed` |
| `created_at` | TIMESTAMP | non | — | — |
| `resolved_at` | TIMESTAMP | oui | — | — |
| `resolved_by_id` | FK | oui | — | indexée · → `accounts_user` · `SET_NULL` |

**Contraintes de table**
- `uniq_report_per_user_deal` — unicité sur `deal`, `reporter`
- `report_closed_requires_date` — vérification : `(OR: ('status', 'open'), ('resolved_at__isnull', False))`

---

## Intégrité référentielle
Le comportement de suppression est choisi champ par champ, jamais laissé par défaut.

| Relation | Comportement | Raison |
|---|---|---|
| `payments_payment.user_id` → `accounts_user` | `PROTECT` | verrou de conservation comptable : sept ans (art. 315 CIR 92). C'est cette contrainte qui rend la suppression logique obligatoire. |
| `deals_deal.submitted_by_id` → `accounts_user` | `PROTECT` | la modération doit pouvoir remonter à l'auteur d'une offre litigieuse |
| `deals_deal.merchant_id` → `catalog_merchant` | `PROTECT` | supprimer une enseigne effacerait son historique de prix |
| `deals_vote.deal_id` → `deals_deal` | `CASCADE` | un vote n'a aucun sens sans son offre ; l'offre n'est de toute façon jamais supprimée physiquement |
| `deals_comment.author_id` → `accounts_user` | `PROTECT` | les fils de discussion resteraient troués |
| `moderation_auditlog.actor_id` → `accounts_user` | `SET_NULL` | effacer un compte ne doit pas effacer la trace de ses actes, mais la trace ne doit pas non plus empêcher l'anonymisation ; `actor_label` conserve le pseudonyme figé |
| `catalog_categorytranslation.category_id` → `catalog_category` | `CASCADE` | un libellé n'existe pas sans sa catégorie |

## Dénormalisation assumée
`deals_deal.temperature` duplique une information dérivable de `deals_vote`. C'est délibéré : recalculer un `SUM` sur les votes pour chaque ligne du flux coûterait une agrégation par carte affichée. La table `Vote` reste souveraine et le compteur est recalculable à tout moment par `Deal.recompute_temperature()`, testé par `test_recompute_matches_vote_table`.

`moderation_auditlog.actor_label` duplique le pseudonyme au moment de l'action. Une piste d'audit doit rester lisible après l'anonymisation de l'auteur, ce qu'une simple jointure ne permettrait plus.

---

_Schéma : 28 tables, moteur `sqlite`._
