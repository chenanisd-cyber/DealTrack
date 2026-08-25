# Sécurité — DealTrack.be

Ce document explique **où** chaque protection est implémentée et **pourquoi**
elle est conçue ainsi. Chaque section renvoie au test qui la vérifie : une
mesure de sécurité qu'aucun test ne couvre est une intention, pas une garantie.

---

## 1. Comment l'API est sécurisée

C'est la question posée par le cahier des charges, alors traitons-la d'abord et
en entier.

### 1.1 Authentification — deux mécanismes, deux usages

| Mécanisme | Pour qui | Où |
|---|---|---|
| **JWT** (`rest_framework_simplejwt`) | clients tiers, applications mobiles, Postman | `POST /api/v1/auth/token/` |
| **Session Django** | le front-office lui-même, en AJAX | cookie de session |

Le jeton d'accès vit **15 minutes**, le jeton de rafraîchissement **7 jours**
avec rotation. Une fenêtre courte limite la valeur d'un jeton dérobé : au-delà
d'un quart d'heure, il ne sert plus à rien.

`USER_ID_CLAIM` porte l'UUID du compte, pas un entier séquentiel. Un jeton
intercepté ne renseigne donc pas sur le nombre d'inscrits.

Point important : `SessionAuthentication` **reste soumise au CSRF** dans DRF.
Une API accessible au cookie de session sans vérification de jeton serait
attaquable depuis n'importe quel site tiers.

### 1.2 Autorisation — trois couches, volontairement redondantes

Oublier un contrôle arrive. Trois couches indépendantes font qu'un oubli seul ne
suffit pas à ouvrir une brèche.

**Couche 1 — permission de classe.** Qui a le droit d'atteindre la vue.

```python
# apps/api/views.py
permission_classes = [ReadOnlyOrAuthenticated, IsAuthorOrModerator]
```

Le réglage global est fermé par défaut : `DEFAULT_PERMISSION_CLASSES` vaut
`IsAuthenticated`. Chaque vue ouvre explicitement ce qu'elle expose ; une vue
nouvelle est donc fermée tant qu'on ne l'a pas ouverte, et non l'inverse.

**Couche 2 — permission d'objet.** Sur *quelle ressource* précisément.

```python
# apps/api/permissions.py — IsAuthorOrModerator
author = getattr(obj, "submitted_by", None) or getattr(obj, "author", None)
allowed = author == user and obj.status in (DRAFT, PENDING)
```

C'est la parade au **Broken Access Control** : autoriser `/api/v1/deals/<id>/`
aux authentifiés ne dit rien de *quel* deal l'appelant peut modifier.

**Couche 3 — queryset filtré.** Ce que l'appelant peut seulement *voir*.

```python
# apps/deals/models.py — DealQuerySet.for_user
def get_queryset(self):
    return Deal.objects.for_user(self.request.user)
```

Cette méthode est partagée par les vues HTML et par l'API : une seule définition
du périmètre, donc pas de dérive entre les deux points d'entrée.

**Conséquence observable.** Un membre qui tente de modifier l'offre en attente
d'un autre reçoit **404, pas 403**. La ressource est filtrée avant l'évaluation
des permissions, et répondre 403 confirmerait son existence — ce qui suffit à
énumérer les identifiants.

### 1.3 Ce que le client ne peut pas décider

Les sérialiseurs utilisent une **liste blanche** de champs, jamais
`fields = "__all__"`. Un champ ajouté au modèle demain n'est pas écrivable par
accident (*mass assignment*).

Les champs de décision sont fixés par le serveur :

```python
# apps/api/serializers.py — DealWriteSerializer.create
deal = Deal.objects.create(
    **validated,
    submitted_by=request.user,     # ignore toute valeur envoyée
    status=DealStatus.PENDING,     # imposé, quoi que dise la charge utile
)
```

Vérifié par `test_post_deal_cannot_force_published_status` : un POST portant
`"status": "published"` et `"temperature": 99999` ressort en `pending` à 100°.

### 1.4 Limitation de débit

| Portée | Limite | Motif |
|---|---|---|
| `anon` | 60 / heure | moisson du catalogue par un robot |
| `user` | 1000 / heure | usage normal confortable |
| `deal-write` | 20 / heure | spam d'offres |
| `vote` | 60 / heure | gonflage artificiel de température |
| `token` | 10 / heure **par IP** | balayage d'identifiants |

Le throttle sur `/auth/token/` mérite une explication. `django-axes` verrouille
un *compte* après 5 échecs. Un attaquant qui essaie un mot de passe unique
contre mille adresses différentes ne déclenche jamais ce verrou : chaque compte
n'enregistre qu'un seul échec. La limite par IP ferme cette voie.

### 1.5 Erreurs — format constant, aucune fuite

```json
{"error": {"code": "permission_denied", "trace_id": "8e13aab8a839",
           "detail": {"detail": "Vous n'avez pas les droits pour cette action."}}}
```

`apps/api/exceptions.py` intercepte tout. Une `IntegrityError` cite les noms de
table et de contrainte : elle est **journalisée**, jamais renvoyée. Le
`trace_id` permet de rapprocher la réponse du client et la ligne de log, sans
rien divulguer.

Vérifié par `test_server_does_not_leak_stack_trace` et
`test_error_envelope_has_stable_shape`.

---

## 2. CSRF

**Mécanisme.** `CsrfViewMiddleware` actif, cookie `SameSite=Lax`,
`CSRF_COOKIE_SECURE = True` en production.

**Vue d'échec personnalisée.** `apps/moderation/views.csrf_failure` consigne
l'échec dans la piste d'audit puis rend une page lisible, au lieu de la page
technique de Django qui en dit trop.

**Discipline des verbes.** Aucune action modifiant l'état n'accepte GET :

```python
@login_required
@require_POST          # ← sans ça, <img src="…/vote/"> suffit à faire voter
def deal_vote(request, slug):
```

**Tests.** `test_post_without_token_is_rejected` (403),
`test_post_with_token_succeeds` (302), `test_csrf_failure_is_audited`,
`test_state_changing_action_refuses_get` (405).

---

## 3. XSS

**Échappement.** Les gabarits Django échappent par défaut. Le projet n'utilise
`|safe` ni `mark_safe` **nulle part** — vérifiable par `grep`.

**Description d'un deal.** Rendue par `{{ deal.description|linebreaks }}` :
le filtre échappe *puis* met en forme. Le HTML posté par un membre n'est jamais
interprété.

**Validation en entrée.** `validate_no_control_characters` refuse les caractères
de contrôle et les marques de direction Unicode, employés pour masquer une
charge utile ou inverser un texte à l'affichage.

**Schémas d'URL.** `validate_external_url` exige `https://`, ce qui écarte
`javascript:`, `data:` et les URL protocolaires relatives.

**En-têtes.** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: same-origin`, `Cross-Origin-Opener-Policy: same-origin`.

**Liens sortants.** `rel="nofollow noopener external"` : pas de transfert de
référencement vers un marchand, et pas d'accès à `window.opener` depuis la page
ouverte.

**Sur ce que le test prouve exactement.** Le texte d'une charge utile *subsiste*
dans la page — c'est normal, c'est du contenu. Ce qui compte est qu'aucune
balise ne soit reconstituable :

```
saisi   : <img src=x onerror=alert(1)>
rendu   : &lt;img src=x onerror=alert(1)&gt;
```

Le navigateur affiche au lieu d'exécuter. `test_comment_payload_is_escaped_in_page`
vérifie les deux faces : absence de `<img src=x` et présence de l'entité échappée.

---

## 4. Force brute

**`django-axes`** — 5 échecs, verrou de 15 minutes.

**Clé de verrouillage.** `AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]`,
c'est-à-dire le **couple**. Ce choix n'est pas anodin :

- verrouiller la seule IP punit tous les utilisateurs derrière un NAT partagé —
  une entreprise, une école, un opérateur mobile ;
- verrouiller le seul compte permet à un attaquant de bloquer n'importe qui,
  sans même connaître son mot de passe (déni de service sur autrui).

**Pas d'oracle d'existence de compte.** Les messages d'échec sont identiques que
l'adresse existe ou non :

```python
error_messages = {
    "invalid_login": _("Adresse e-mail ou mot de passe incorrect."),
    "inactive":      _("Adresse e-mail ou mot de passe incorrect."),  # ← identique
}
```

Sans cela, le formulaire de connexion devient un service de vérification
d'adresses pour spammeurs.

**Journalisation sans secret.** Le signal `user_login_failed` consigne
l'identifiant tenté, jamais le mot de passe. Les vues sensibles portent
`@sensitive_post_parameters`, qui masque les champs dans les rapports d'erreur.

**Tests.** `test_account_locks_after_repeated_failures`,
`test_login_error_does_not_reveal_account_existence`,
`test_api_token_endpoint_is_throttled`.

---

## 5. Mots de passe

**Hachage.** Argon2 en tête de `PASSWORD_HASHERS` — résistant au calcul GPU,
recommandé par l'OWASP. Django réhache automatiquement à la connexion suivante
lorsque l'algorithme change.

**Politique.** Cinq validateurs cumulés :

| Validateur | Refuse |
|---|---|
| `MinimumLengthValidator` (12) | trop court |
| `CommonPasswordValidator` | les mots de passe des fuites publiques |
| `NumericPasswordValidator` | uniquement des chiffres |
| `UserAttributeSimilarityValidator` | trop proche de l'adresse ou du pseudonyme |
| `ComplexityValidator` (maison) | moins de 3 classes de caractères sur 4, suites de clavier |

Le validateur maison couvre le cas que les validateurs standard laissent
passer : `Azertyuiop-42!` fait 14 caractères, mêle quatre classes, et reste une
traversée de clavier.

**Double contrôle.** La règle vit sur le serveur. Le navigateur reçoit
`minlength="12"` par commodité, mais un POST direct sur l'API subit exactement
les mêmes validateurs.

**Tests.** Six cas dans `PasswordPolicyTests`.

---

## 6. Validation, front et back

Chaque règle existe **deux fois** : une fois dans le formulaire HTML pour le
confort, une fois côté serveur pour la sécurité. Et une troisième fois en base
lorsque la cohérence des données en dépend.

| Règle | Navigateur | Serveur | Base |
|---|---|---|---|
| Longueur du titre | `minlength=15` | `MinLengthValidator` | — |
| Prix positif | `min=0` | `MinValueValidator` | `CheckConstraint` |
| Prix de référence > prix | — | `clean()` + sérialiseur | `CheckConstraint` |
| Lien HTTPS | `type=url` | `clean_external_url` | — |
| TVA belge valide | — | `validate_be_vat` (modulo 97) | — |
| Un vote par membre | — | `Vote.cast` | `UniqueConstraint` |
| Fin après début | `type=datetime-local` | `clean()` | `CheckConstraint` |

La contrainte en base est la seule couche que deux requêtes concurrentes ne
peuvent pas contourner. Deux votes simultanés du même membre franchiraient le
contrôle applicatif ; ils butent sur `uniq_vote_per_user_deal`.

**Paramètres d'URL.** Les filtres du flux sont validés contre le référentiel
plutôt qu'injectés :

```python
if region_code and Region.objects.filter(code=region_code).exists():
    deals = deals.filter(regions__code=region_code)
```

L'ORM paramètre de toute façon ses requêtes — aucune concaténation SQL n'existe
dans le projet. `test_url_parameter_injection_is_ignored` passe `' OR 1=1--`
en paramètre de région : la page répond 200 sans rien révéler.

---

## 7. Journalisation et piste d'audit

**Deux fichiers, deux usages.**

| Fichier | Contenu | Rotation |
|---|---|---|
| `logs/dealtrack.log` | applicatif, erreurs 500 avec trace | 5 Mo × 5 |
| `logs/security.log` | authentification, refus d'accès, CSRF, audit métier | 5 Mo × 10 |

**Trois niveaux de trace.**

1. `AuditTrailMiddleware` — toute requête modifiant l'état, plus les 401/403.
2. `AuditLog.record()` — l'intention métier : qui a publié, refusé, anonymisé.
3. Les signaux `user_logged_in` / `user_login_failed`.

**Ajout seul.** `AuditLog.Meta.default_permissions = ("add", "view")`, et
l'admin refuse explicitement modification et suppression. Une trace modifiable
ne prouve rien.

**Survie à l'anonymisation.** `actor` est en `SET_NULL` mais `actor_label`
conserve le pseudonyme figé au moment de l'action. Effacer un compte n'efface
pas la trace de ses actes, et la trace n'empêche pas l'effacement.

**Ce qui n'est jamais journalisé.** Mots de passe, jetons, corps des requêtes
vers `/accounts/login`, `/accounts/password`, `/api/v1/auth/`.

**Rapport d'activité.** `python3 manage.py audit_report --days 30` agrège la
période et signale ce qui mérite un œil humain : au moins 5 échecs de connexion
depuis une même IP, au moins 10 refus d'accès, au moins 5 échecs CSRF. Sortie
CSV disponible via `--format csv`.

---

## 8. Gestion des exceptions

**Côté API.** Gestionnaire unique, détaillé en 1.5.

**Côté HTML.** `handler403`, `handler404`, `handler500` rendent des gabarits
sobres. `DEBUG = False` en production, donc aucune trace n'atteint le visiteur.

**Le journal encaisse ses propres pannes.** `AuditTrailMiddleware` enveloppe
son écriture dans un `try/except` : une défaillance de la piste d'audit ne doit
jamais casser la réponse rendue à l'utilisateur.

De même, `AuditLog.record()` tolère les `HttpRequest` partiels — ceux que
fabriquent `force_login`, une tâche de fond ou une commande de gestion. Un
`HttpRequest()` nu a `method = None`, ce qui violait la contrainte `NOT NULL` et
annulait la transaction entière. Le bug a été trouvé par les tests, pas par
relecture.

---

## 9. Paiement

**Aucune donnée de carte ne traverse ce serveur.** Le navigateur échange les
coordonnées bancaires contre un jeton chez le prestataire ; le code ne manipule
que ce jeton. L'application reste dans le périmètre PCI-DSS le plus léger
(SAQ-A).

**Idempotence.** La clé est dérivée de `(utilisateur, formule, jeton)`. Un
double envoi du formulaire produit la même clé, donc un seul débit. En base,
`gateway_reference` est `UNIQUE`, ce qui verrouille le doublon même si la
passerelle faiblit.

**Ordre des opérations.** La ligne `Payment` est créée **avant** l'appel au
prestataire. Si le processus meurt entre les deux, il reste une trace en statut
`pending` réconciliable par webhook, plutôt qu'un débit sans trace.

**Signature des webhooks.** `StripeGateway.verify_webhook` vérifie le HMAC-SHA256
et rejette au-delà d'une fenêtre de 5 minutes. Sans cette double vérification,
n'importe qui poste « paiement réussi » sur l'URL et s'offre un abonnement.
`hmac.compare_digest` évite la comparaison en temps variable.

**Test.** `test_webhook_signature_is_verified`.

---

## 10. Configuration de production

| Réglage | Valeur | Effet |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` | tout HTTP est redirigé |
| `SECURE_HSTS_SECONDS` | 31 536 000 | un an, avec `preload` et sous-domaines |
| `SESSION_COOKIE_SECURE` | `True` | cookie jamais transmis en clair |
| `SESSION_COOKIE_HTTPONLY` | `True` | inaccessible au JavaScript |
| `CSRF_COOKIE_SECURE` | `True` | idem pour le jeton CSRF |
| `ManifestStaticFilesStorage` | actif | empreinte dans le nom des fichiers |

**Aucun secret dans le dépôt.** `config/settings/prod.py` lit l'environnement et
**échoue au démarrage** si une variable manque, plutôt que de tourner en
configuration dégradée :

```python
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
```

Voir `.env.example` pour la liste complète.

---

## 11. Limites connues

Un document de sécurité qui n'énonce que des réussites n'est pas crédible.

- **Pas de Content-Security-Policy.** Les gabarits comportent des attributs
  `style=` en ligne, incompatibles avec une CSP stricte sans nonce. À traiter
  avant mise en production réelle.
- **Pas de double authentification.** Souhaitable au moins pour les comptes
  modérateur et administrateur.
- **`SESSION_ENGINE` en base.** Convient jusqu'à quelques milliers de sessions
  simultanées ; au-delà, passer sur Redis.
- **`AXES` s'appuie sur le cache local.** En déploiement multi-processus, il faut
  un cache partagé, sinon le compteur d'échecs se fragmente et le verrou devient
  bien plus permissif qu'annoncé.
- **Adresses IP dans la piste d'audit.** Ce sont des données personnelles au sens
  du RGPD. La rétention est fixée à 365 jours (`AUDIT_LOG_RETENTION_DAYS`), mais
  la purge automatique n'est pas encore planifiée.
- **Aucun audit externe.** Les tests vérifient ce que j'ai pensé à tester. Un
  test de pénétration indépendant reste nécessaire avant toute exploitation.

---

## Récapitulatif : où regarder

| Sujet | Fichier | Tests |
|---|---|---|
| Réglages de sécurité | `config/settings/base.py`, `prod.py` | — |
| Politique de mot de passe | `apps/accounts/validators.py` | `PasswordPolicyTests` |
| Permissions API | `apps/api/permissions.py` | `AccessControlTests` |
| Filtrage d'accès | `apps/deals/models.py` (`for_user`) | `AccessControlTests` |
| Gestion d'erreurs | `apps/api/exceptions.py` | `ApiTests` |
| Limitation de débit | `apps/api/throttles.py` | `BruteForceTests` |
| Piste d'audit | `apps/moderation/` | dispersés |
| Paiement | `apps/payments/gateways.py`, `services.py` | `PaymentTests` |
