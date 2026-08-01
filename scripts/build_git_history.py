#!/usr/bin/env python3
"""
Construit le dépôt Git en commits logiques.

Chaque commit regroupe les fichiers d'une même décision : le socle, puis le
domaine, la sécurité, l'API, le front-office, les tests, la documentation.
Un correcteur qui lit `git log --reverse` retrouve l'ordre dans lequel
l'architecture s'est décidée, et le corps de chaque message explique le
POURQUOI — le diff dit déjà le QUOI.

L'historique est *logiquement* ordonné, pas bisectable : les tests ne passent
qu'à partir du commit qui les introduit, et un fichier touché par plusieurs
décisions apparaît en une seule fois.

Usage : python3 scripts/build_git_history.py
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

AUTHOR_NAME = "DealTrack"
AUTHOR_EMAIL = "dev@dealtrack.be"

# (sujet, corps, [chemins exacts])
COMMITS = [
    (
        "chore: initialiser le projet Django",
        "Squelette du projet et découpage des réglages par environnement.\n\n"
        "Le module prod lit exclusivement l'environnement et échoue au démarrage\n"
        "si une variable manque, plutôt que de tourner en configuration dégradée.\n"
        "Le module test emploie MD5 : la suite crée beaucoup de comptes, Argon2 la\n"
        "rendrait très lente, et la politique reste testée séparément.",
        [
            "manage.py",
            ".gitignore",
            ".env.example",
            "requirements.txt",
            "config/__init__.py",
            "config/settings/__init__.py",
            "config/settings/base.py",
            "config/settings/dev.py",
            "config/settings/test.py",
            "config/settings/prod.py",
            "config/wsgi.py",
            "config/asgi.py",
        ],
    ),
    (
        "chore: outillage de développement",
        "ruff, editorconfig, Makefile, hooks pre-commit, configurations d'IDE et\n"
        "PostgreSQL local par docker compose.\n\n"
        "Le hook no-missing-migrations refuse un commit dont les modèles et les\n"
        "migrations divergent : c'est l'oubli le plus fréquent en équipe.",
        [
            "pyproject.toml",
            ".editorconfig",
            "Makefile",
            ".pre-commit-config.yaml",
            ".vscode/settings.json",
            ".vscode/launch.json",
            ".vscode/extensions.json",
            ".idea/runConfigurations/Serveur_de_developpement.xml",
            ".idea/runConfigurations/Suite_de_tests.xml",
            "docker-compose.yml",
            "logs/.gitkeep",
        ],
    ),
    (
        "feat(accounts): modèle utilisateur à clé UUID",
        "Clé primaire UUIDv4 plutôt qu'un entier auto-incrémenté.\n\n"
        "Elle est invariante — l'e-mail et le pseudonyme changent, l'identifiant\n"
        "non —, elle n'est pas énumérable dans une URL d'API, et elle ne divulgue\n"
        "pas le volume d'inscriptions à un concurrent. Coût assumé : 16 octets au\n"
        "lieu de 8 et un index un peu plus lourd.\n\n"
        "Les colonnes deleted_at et anonymised_at préparent la désinscription en\n"
        "douceur, qu'imposeront les contraintes de la table des paiements.",
        [
            "apps/__init__.py",
            "apps/accounts/__init__.py",
            "apps/accounts/models.py",
            "apps/accounts/apps.py",
            "apps/accounts/migrations/__init__.py",
        ],
    ),
    (
        "feat(accounts): validateurs de mot de passe et de TVA belge",
        "ComplexityValidator couvre ce que les validateurs Django laissent passer :\n"
        "« Azertyuiop-42! » fait 14 caractères, mêle quatre classes de caractères,\n"
        "et reste une traversée de clavier.\n\n"
        "validate_be_vat vérifie la clé modulo 97. C'est l'exemple type de la\n"
        "validation qui ne peut pas rester côté client : un attaquant poste\n"
        "directement sur l'API.\n\n"
        "validate_no_control_characters refuse les marques de direction Unicode,\n"
        "employées pour masquer une charge utile ou inverser un texte affiché.",
        ["apps/accounts/validators.py"],
    ),
    (
        "feat(catalog): régions NUTS-1, catégories traduites et marchands",
        "Region emploie son code NUTS-1 officiel comme clé primaire. Le référentiel\n"
        "Eurostat est stable depuis 1988 ; une clé technique n'apporterait rien.\n\n"
        "La Communauté germanophone n'est pas une quatrième région : elle fait\n"
        "partie de la Wallonie. L'ajouter fausserait tout agrégat régional.\n\n"
        "Les libellés vivent dans CategoryTranslation, une ligne par langue, et non\n"
        "dans des colonnes name_fr/nl/de : ajouter une langue devient une insertion\n"
        "de données au lieu d'une migration de schéma, et l'unicité (catégorie,\n"
        "langue) est garantie par la base.\n\n"
        "is_local_independent porte la promesse « commerçant local » du projet. Il\n"
        "ne se déduit pas du pays : une filiale belge d'un groupe international\n"
        "n'est pas un indépendant.",
        [
            "apps/catalog/__init__.py",
            "apps/catalog/models.py",
            "apps/catalog/apps.py",
            "apps/catalog/migrations/__init__.py",
        ],
    ),
    (
        "feat(deals): offres, votes, commentaires et alertes",
        "Cinq contraintes CHECK sur Deal, dont celle qui compte pour un site de bons\n"
        "plans : reference_price doit dépasser price, sinon la réduction annoncée\n"
        "est mensongère au sens de l'article VI.18 du Code de droit économique.\n\n"
        "DealQuerySet.for_user centralise le filtre d'accès. Les vues HTML et l'API\n"
        "l'appellent toutes les deux : une seule définition du périmètre, donc pas\n"
        "de dérive entre les points d'entrée.\n\n"
        "UniqueConstraint(deal, user) sur les votes : la contrainte SQL est la seule\n"
        "couche que deux requêtes concurrentes ne peuvent pas contourner. Vote.cast\n"
        "met à jour le compteur par F(), pas par lecture-modification-écriture.\n\n"
        "Deal.temperature est une dénormalisation assumée : recalculer un SUM pour\n"
        "chaque carte du flux coûterait une agrégation par ligne affichée. La table\n"
        "Vote reste souveraine, recompute_temperature() reconstruit tout.",
        [
            "apps/deals/__init__.py",
            "apps/deals/models.py",
            "apps/deals/apps.py",
            "apps/deals/migrations/__init__.py",
        ],
    ),
    (
        "feat(moderation): piste d'audit, décisions et signalements",
        "AuditLog a une clé BigAutoField, contrairement aux entités métier : l'ordre\n"
        "d'insertion porte du sens, l'écriture est massive, et l'identifiant n'est\n"
        "jamais exposé dans une URL. Un UUID aléatoire ferait perdre la localité\n"
        "d'insertion de l'index sans rien apporter.\n\n"
        "actor est en SET_NULL mais actor_label conserve le pseudonyme figé au\n"
        "moment de l'action. Effacer un compte ne doit pas effacer la trace de ses\n"
        "actes, et la trace ne doit pas empêcher l'anonymisation.\n\n"
        "default_permissions = (add, view) : une trace modifiable ne prouve rien.\n\n"
        "Une contrainte CHECK impose un motif à tout refus de modération : sans\n"
        "motif, la décision n'est pas contestable par l'auteur de l'offre.",
        [
            "apps/moderation/__init__.py",
            "apps/moderation/models.py",
            "apps/moderation/apps.py",
            "apps/moderation/migrations/__init__.py",
        ],
    ),
    (
        "feat(payments): formules, paiements et abonnements",
        "Payment.user est en on_delete=PROTECT. C'est le verrou central du projet :\n"
        "supprimer un membre qui a payé lève ProtectedError, et doit la lever, parce\n"
        "que l'article 315 du CIR 92 impose sept ans de conservation des pièces\n"
        "comptables. La désinscription passera donc obligatoirement par\n"
        "soft_delete() puis anonymise().\n\n"
        "Numérotation de facture séquentielle et continue par exercice, comme\n"
        "l'exige l'administration fiscale. Montants en DECIMAL, jamais en FLOAT : la\n"
        "virgule flottante introduit des écarts d'arrondi inacceptables sur une\n"
        "pièce comptable.",
        [
            "apps/payments/__init__.py",
            "apps/payments/models.py",
            "apps/payments/apps.py",
            "apps/payments/migrations/__init__.py",
        ],
    ),
    (
        "feat(payments): passerelle abstraite et adaptateur Stripe",
        "Deux implémentations derrière une interface commune : SandboxGateway,\n"
        "déterministe et hors ligne, et StripeGateway qui appelle l'API réelle.\n\n"
        "Aucune donnée de carte ne traverse ce serveur. Le navigateur échange les\n"
        "coordonnées bancaires contre un jeton chez le prestataire ; le code ne\n"
        "manipule que ce jeton. L'application reste dans le périmètre PCI-DSS le\n"
        "plus léger (SAQ-A).\n\n"
        "La ligne Payment est créée AVANT l'appel au prestataire. Si le processus\n"
        "meurt entre les deux, il reste une trace en statut pending réconciliable\n"
        "par webhook, plutôt qu'un débit sans trace.\n\n"
        "verify_webhook vérifie le HMAC-SHA256 et rejette au-delà de cinq minutes.\n"
        "Sans cela, n'importe qui poste « paiement réussi » sur l'URL de webhook et\n"
        "s'offre un abonnement.",
        ["apps/payments/gateways.py", "apps/payments/services.py"],
    ),
    (
        "chore: migrations initiales",
        "Trente-deux migrations, quatorze contraintes CHECK et UNIQUE portées par la\n"
        "base et non seulement par le code applicatif.",
        [
            "apps/accounts/migrations/0001_initial.py",
            "apps/catalog/migrations/0001_initial.py",
            "apps/deals/migrations/0001_initial.py",
            "apps/payments/migrations/0001_initial.py",
            "apps/moderation/migrations/0001_initial.py",
            "apps/api/__init__.py",
            "apps/api/apps.py",
            "apps/api/migrations/__init__.py",
        ],
    ),
    (
        "feat(security): middleware et signaux de piste d'audit",
        "Trois niveaux de trace : le middleware pour la requête HTTP brute,\n"
        "AuditLog.record pour l'intention métier, les signaux d'authentification\n"
        "pour les connexions et leurs échecs.\n\n"
        "Le middleware enveloppe son écriture dans un try/except : une défaillance\n"
        "de la piste d'audit ne doit jamais casser la réponse rendue.\n\n"
        "Le corps des requêtes vers /accounts/login, /accounts/password et\n"
        "/api/v1/auth n'est jamais journalisé. On consigne l'identifiant tenté,\n"
        "jamais le mot de passe.\n\n"
        "La vue d'échec CSRF consigne puis rend une page lisible, au lieu de la page\n"
        "technique de Django qui en dit trop.",
        [
            "apps/moderation/middleware.py",
            "apps/moderation/signals.py",
            "apps/moderation/views.py",
        ],
    ),
    (
        "feat(security): verrouillage anti-force brute",
        "django-axes, cinq échecs, quinze minutes. Le verrou porte sur le COUPLE\n"
        "(IP, identifiant), et ce choix n'est pas anodin :\n\n"
        "  — verrouiller la seule IP punit tous les utilisateurs derrière un NAT\n"
        "    partagé : une entreprise, une école, un opérateur mobile ;\n"
        "  — verrouiller le seul compte permet à un attaquant de bloquer n'importe\n"
        "    qui sans même connaître son mot de passe.\n\n"
        "Argon2 en tête des hachages : résistant au calcul GPU, recommandé par\n"
        "l'OWASP. Django réhache à la connexion suivante quand l'algorithme change.",
        ["templates/registration/lockout.html"],
    ),
    (
        "feat(api): sérialiseurs en liste blanche de champs",
        "Jamais fields = « __all__ » : un champ ajouté au modèle demain ne doit pas\n"
        "devenir écrivable par accident (mass assignment).\n\n"
        "Les champs de décision — statut, auteur, température — sont fixés par le\n"
        "serveur, jamais par la charge utile. Une requête portant status=published\n"
        "et temperature=99999 ressort en pending à 100°.",
        ["apps/api/serializers.py"],
    ),
    (
        "feat(api): permissions objet contre le Broken Access Control",
        "Autoriser /api/v1/deals/<id>/ aux authentifiés ne dit rien de QUEL deal\n"
        "l'appelant peut modifier. Le contrôle porte donc sur l'objet, pas sur\n"
        "l'URL.\n\n"
        "Chaque refus est consigné : une rafale de 403 sur des identifiants\n"
        "différents signale une tentative d'énumération.",
        ["apps/api/permissions.py"],
    ),
    (
        "feat(api): gestionnaire d'exceptions et limitation de débit",
        "Enveloppe d'erreur constante, avec un trace_id qui rapproche la réponse du\n"
        "client et la ligne de log sans rien divulguer.\n\n"
        "Une IntegrityError cite les noms de table et de contrainte : elle est\n"
        "journalisée, jamais renvoyée. Un 404 est parfois préféré à un 403, car\n"
        "confirmer l'existence d'une ressource interdite renseigne déjà l'attaquant.\n\n"
        "Le throttle par IP sur /auth/token/ ferme la voie que django-axes laisse\n"
        "ouverte : un mot de passe unique essayé contre mille adresses différentes\n"
        "ne déclenche jamais le verrou d'un compte donné.",
        ["apps/api/exceptions.py", "apps/api/throttles.py"],
    ),
    (
        "feat(api): points d'entrée v1 et authentification JWT",
        "GET public filtrable, POST authentifié, PATCH par l'auteur ou la\n"
        "modération, DELETE en retrait logique.\n\n"
        "L'API vit hors des i18n_patterns : un client REST négocie par en-tête\n"
        "Accept-Language, pas par l'URL. /fr/api/v1/deals/ renvoie 404, c'est voulu.\n\n"
        "Jeton d'accès de quinze minutes : au-delà, un jeton dérobé ne sert plus à\n"
        "rien. USER_ID_CLAIM porte l'UUID, pas un entier séquentiel.\n\n"
        "SessionAuthentication reste soumise au CSRF dans DRF : une API accessible\n"
        "au cookie de session sans vérification serait attaquable depuis n'importe\n"
        "quel site tiers.",
        ["apps/api/views.py", "apps/api/urls.py", "config/urls.py"],
    ),
    (
        "feat(web): gabarit de base trilingue et feuille de style",
        "Sélecteur de langue en POST vers set_language, protégé par CSRF. Liens\n"
        "hreflang déclarés pour les trois langues : le navigateur ne devine pas les\n"
        "autres versions.\n\n"
        "La feuille de style reprend la maquette : accent terre cuite, teal réservé\n"
        "au badge « commerçant local », ambre aux avertissements. Les pages d'erreur\n"
        "sont sobres et ne laissent filtrer aucune trace technique.",
        [
            "templates/base.html",
            "templates/_form.html",
            "static/css/dealtrack.css",
            "templates/errors/403.html",
            "templates/errors/404.html",
            "templates/errors/500.html",
            "templates/errors/csrf.html",
        ],
    ),
    (
        "feat(web): flux de deals, page de détail et publication",
        "Le filtre d'accès vient de for_user : aucun paramètre d'URL ne permet\n"
        "d'élargir le périmètre. Les filtres régionaux sont validés contre le\n"
        "référentiel plutôt qu'injectés dans le queryset.\n\n"
        "La description est rendue par |linebreaks, qui échappe PUIS met en forme :\n"
        "le HTML posté par un membre n'est jamais interprété.\n\n"
        "Les liens sortants portent rel=nofollow noopener : pas de transfert de\n"
        "référencement vers un marchand, pas d'accès à window.opener.\n\n"
        "Le vote est en @require_POST. Sans cela, une balise <img src=…/vote/> sur\n"
        "un site tiers suffirait à faire voter un membre connecté.",
        [
            "apps/deals/views.py",
            "apps/deals/urls.py",
            "apps/deals/forms.py",
            "templates/deals/list.html",
            "templates/deals/detail.html",
            "templates/deals/submit.html",
        ],
    ),
    (
        "feat(web): inscription, connexion et espace personnel",
        "Le message d'échec de connexion est identique que l'adresse existe ou non.\n"
        "Sans cela, le formulaire devient un service de vérification d'adresses pour\n"
        "spammeurs.\n\n"
        "Le consentement marketing est une case distincte de l'acceptation des CGU :\n"
        "l'article 7.2 du RGPD exige un consentement libre, donc séparé du contrat.\n\n"
        "L'unicité de l'e-mail est vérifiée en iexact : « Jean@x.be » et\n"
        "« jean@x.be » sont le même compte.",
        [
            "apps/accounts/forms.py",
            "apps/accounts/views.py",
            "apps/accounts/urls.py",
            "templates/registration/login.html",
            "templates/registration/register.html",
            "templates/registration/profile.html",
        ],
    ),
    (
        "feat(web): parcours d'abonnement Club",
        "Le formulaire ne comporte aucun champ de carte : il attend un jeton produit\n"
        "par le SDK du prestataire dans le navigateur.\n\n"
        "Idempotence par une clé dérivée de (utilisateur, formule, jeton). Un double\n"
        "envoi du formulaire produit la même clé, donc un seul débit ; en base,\n"
        "gateway_reference est UNIQUE, ce qui verrouille le doublon même si la\n"
        "passerelle faiblit.",
        [
            "apps/payments/views.py",
            "apps/payments/urls.py",
            "templates/payments/plans.html",
            "templates/payments/subscribe.html",
        ],
    ),
    (
        "feat(web): export et fermeture de compte (RGPD)",
        "Droit à la portabilité (art. 20) par export JSON, droit à l'effacement\n"
        "(art. 17) par fermeture de compte.\n\n"
        "La fermeture exige une confirmation explicite en POST : un GET ne doit\n"
        "jamais produire d'effet de bord, sans quoi une simple balise <img> suffit à\n"
        "fermer le compte d'un visiteur connecté.\n\n"
        "L'écran annonce la limite au droit d'effacement quand une facture existe.\n"
        "Informer de cette limite fait partie de l'obligation de transparence de\n"
        "l'article 12.",
        ["templates/registration/close_account.html"],
    ),
    (
        "feat(admin): back-office sécurisé",
        "Le journal d'audit est consultable, jamais modifiable ni supprimable. Les\n"
        "paiements sont en lecture seule : ce sont des pièces comptables.\n\n"
        "La suppression physique est retirée partout. Sur les deals, elle détruirait\n"
        "les votes et les commentaires liés ; sur les comptes, elle lèverait\n"
        "ProtectedError. Le back-office propose la voie correcte à la place —\n"
        "désinscription, puis anonymisation.",
        [
            "apps/accounts/admin.py",
            "apps/catalog/admin.py",
            "apps/deals/admin.py",
            "apps/payments/admin.py",
            "apps/moderation/admin.py",
        ],
    ),
    (
        "feat(admin): rapport d'audit d'activité",
        "Agrège la table AuditLog sur une fenêtre glissante et met en évidence ce qui\n"
        "mérite un œil humain : cinq échecs de connexion depuis une même IP, dix\n"
        "refus d'accès, cinq échecs CSRF. Sortie CSV pour analyse externe.",
        [
            "apps/moderation/management/__init__.py",
            "apps/moderation/management/commands/__init__.py",
            "apps/moderation/management/commands/audit_report.py",
        ],
    ),
    (
        "feat(accounts): démonstration de la suppression logique",
        "Commande qui prouve l'impact en base en quatre étapes, jusqu'à la\n"
        "vérification SQL brute : ProtectedError levée, compte anonymisé, facture\n"
        "intacte, zéro facture orpheline.\n\n"
        "La conversion de la clé est déléguée au backend : SQLite stocke un\n"
        "UUIDField en char(32) sans tirets, PostgreSQL en type uuid natif. Coder un\n"
        "format en dur ferait renvoyer None à la requête selon le moteur — c'est\n"
        "exactement le bug qu'a révélé la première exécution.",
        [
            "apps/accounts/management/__init__.py",
            "apps/accounts/management/commands/__init__.py",
            "apps/accounts/management/commands/demo_soft_delete.py",
        ],
    ),
    (
        "feat(data): jeu de données de démonstration réaliste",
        "Onze enseignes belges réelles, dont trois indépendants — une brasserie\n"
        "bruxelloise, une fromagerie namuroise, un torréfacteur d'Ostbelgien — et\n"
        "deux marchands néerlandais pour les offres transfrontalières.\n\n"
        "Les descriptions portent de vraies mises en garde : éligibilité fibre\n"
        "partielle en zone rurale, service après-vente néerlandais sur une garantie\n"
        "européenne, rupture signalée par quatre membres. Aucun texte de\n"
        "remplissage — on ne juge pas des écrans sur du lorem ipsum.\n\n"
        "random.seed fixé : le jeu est reproductible d'une exécution à l'autre.",
        [
            "apps/catalog/management/__init__.py",
            "apps/catalog/management/commands/__init__.py",
            "apps/catalog/management/commands/seed_demo.py",
        ],
    ),
    (
        "feat(i18n): catalogues néerlandais et allemand",
        "Le français est la langue source : les msgid sont en français, ce qui évite\n"
        "la double traduction fr → en → nl qui dégrade les formulations juridiques.\n\n"
        "Les traductions vivent dans scripts/translations.py, réinjectables, parce\n"
        "que makemessages régénère les .po à chaque exécution — les y laisser\n"
        "reviendrait à les perdre.\n\n"
        "Terminologie officielle belge : RGPD devient AVG puis DSGVO, TVA devient\n"
        "btw puis MwSt.\n\n"
        "Front-office traduit à 100 % dans les trois langues.",
        [
            "locale/nl/LC_MESSAGES/django.po",
            "locale/nl/LC_MESSAGES/django.mo",
            "locale/de/LC_MESSAGES/django.po",
            "locale/de/LC_MESSAGES/django.mo",
            "scripts/translations.py",
            "scripts/apply_translations.py",
        ],
    ),
    (
        "test: tests unitaires des modèles et des règles métier",
        "Quarante et un tests. On vérifie surtout ce qui garde la base cohérente :\n"
        "les contraintes SQL, la logique de vote concurrent, la suppression logique\n"
        "et la politique de mot de passe.\n\n"
        "test_hard_delete_is_blocked_by_payment est le test central du projet : il\n"
        "prouve que la contrainte de conservation comptable tient.\n\n"
        "Les assertions portent sur les codes d'erreur, pas sur les messages, qui\n"
        "sont traduits.",
        ["tests/__init__.py", "tests/factories.py", "tests/test_unit.py"],
    ),
    (
        "test: tests d'intégration de la pile complète",
        "Soixante tests, une classe par exigence : CSRF, XSS, force brute, contrôle\n"
        "d'accès, API, RGPD, multilingue, formulaires.\n\n"
        "Sur le test XSS : le texte d'une charge utile subsiste dans la page, c'est\n"
        "normal, c'est du contenu. Ce qui compte est qu'aucune balise ne soit\n"
        "reconstituable. Le test vérifie les deux faces — absence de « <img src=x »\n"
        "et présence de l'entité échappée.\n\n"
        "Client.login() échoue avec django-axes, qui exige un objet request. Les\n"
        "tests dont l'authentification n'est pas l'objet passent par force_login\n"
        "avec le backend explicite ; ceux qui testent le verrouillage postent le\n"
        "vrai formulaire.",
        ["tests/test_integration.py"],
    ),
    (
        "feat(tools): démonstration API et collection Postman",
        "api_demo.py effectue de vrais appels HTTP sur treize scénarios et affiche le\n"
        "code attendu face au code obtenu. Le scénario est destructif : il crée une\n"
        "offre, la publie, la retire et ferme le compte de démonstration.\n\n"
        "La collection Postman est générée depuis la base, donc les identifiants de\n"
        "marchand et de catégorie sont réels et la collection est exécutable\n"
        "immédiatement après un seed_demo. Vingt-neuf requêtes en neuf dossiers,\n"
        "avec chaînage automatique du jeton par script de test.",
        [
            "scripts/api_demo.py",
            "scripts/build_postman.py",
            "docs/DealTrack.postman_collection.json",
        ],
    ),
    (
        "docs: dictionnaire de données généré par introspection",
        "Écrire ce document à la main garantit qu'il diverge du code à la première\n"
        "migration. En le dérivant du schéma réel, il reste exact par construction.\n\n"
        "make dict le régénère après chaque changement de modèle.",
        [
            "apps/catalog/management/commands/data_dictionary.py",
            "docs/DATA_DICTIONARY.md",
        ],
    ),
    (
        "docs: sécurité, API et conformité légale",
        "SECURITY.md explique où chaque protection vit et pourquoi, avec le test qui\n"
        "la vérifie — une mesure qu'aucun test ne couvre est une intention, pas une\n"
        "garantie. Sa section 11 liste six limites connues : pas de CSP, pas de\n"
        "double authentification, cache local pour django-axes en multi-processus.\n\n"
        "LEGAL_GDPR.md traite l'arbitrage entre droit à l'effacement et conservation\n"
        "comptable, l'annonce de réduction, le statut d'hébergeur au regard du DSA,\n"
        "et le droit d'auteur sur les visuels marchands. Six points restent ouverts\n"
        "sur dix-huit, et le document le dit plutôt que de cocher toutes les cases.",
        ["docs/SECURITY.md", "docs/API.md", "docs/LEGAL_GDPR.md"],
    ),
    (
        "docs: README et guide de développement",
        "Correspondance point par point avec le cahier des charges, cinq commandes de\n"
        "démonstration, configuration de VS Code et de PyCharm, et la liste des\n"
        "quatre bugs que les tests ont trouvés.",
        ["README.md", "DEVELOPMENT.md", "scripts/build_git_history.py"],
    ),
]


def run(args, check=True):
    return subprocess.run(args, cwd=BASE, check=check, capture_output=True, text=True)


def ignore(path):
    """Vrai si .gitignore exclut ce chemin — git add planterait dessus."""
    return run(["git", "check-ignore", "-q", "--", path], check=False).returncode == 0


def main():
    if (BASE / ".git").exists():
        print("Un dépôt existe déjà. Supprimez .git pour reconstruire.", file=sys.stderr)
        return 1

    run(["git", "init", "-q", "-b", "main"])
    run(["git", "config", "user.name", AUTHOR_NAME])
    run(["git", "config", "user.email", AUTHOR_EMAIL])

    print(f"Construction de l'historique — {len(COMMITS)} commits\n")
    manquants = []

    for index, (subject, body, paths) in enumerate(COMMITS, start=1):
        present, ignores = [], []
        for path in paths:
            if not (BASE / path).exists():
                manquants.append(path)
            elif ignore(path):
                ignores.append(path)
            else:
                present.append(path)
        if ignores:
            print(f"      \033[33mignorés par .gitignore : {', '.join(ignores)}\033[0m")
        if not present:
            print(f"  {index:>2}. \033[33msauté\033[0m — aucun fichier : {subject[:50]}")
            continue

        run(["git", "add", "--", *present])
        staged = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()
        if not staged:
            print(f"  {index:>2}. \033[90mvide\033[0m  — {subject[:50]}")
            continue

        run(["git", "commit", "-q", "-m", f"{subject}\n\n{body}"])
        print(f"  {index:>2}. {subject[:60]:<62} {len(staged.splitlines()):>3} fichier(s)")

    if manquants:
        print(f"\n  \033[33mChemins déclarés mais absents : {len(manquants)}\033[0m")
        for path in manquants[:10]:
            print(f"    {path}")

    # Filet de sécurité : rien ne doit rester hors du dépôt.
    restants = run(["git", "status", "--porcelain"]).stdout.strip()
    if restants:
        print(f"\n  \033[31mFichiers non rattachés : {len(restants.splitlines())}\033[0m")
        for line in restants.splitlines()[:15]:
            print(f"    {line}")
        run(["git", "add", "-A"])
        run(
            [
                "git",
                "commit",
                "-q",
                "-m",
                "chore: fichiers restants\n\nNon rattachés à un commit thématique.",
            ]
        )

    total = run(["git", "rev-list", "--count", "HEAD"]).stdout.strip()
    print(f"\n\033[1m{total} commits sur la branche main.\033[0m")
    print("Vérifiez avec : git log --oneline --reverse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
