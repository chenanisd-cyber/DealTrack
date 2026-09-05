# Guide de développement

## Mise en route

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install ruff polib          # outillage, hors production

make reset                      # base vierge + données de démonstration
make run
```

`make` sans argument liste toutes les cibles.

## Configuration de l'IDE

**VS Code** — les réglages sont dans `.vscode/`. Installez les extensions
recommandées à l'ouverture du projet : Python, Ruff, Django. Quatre
configurations de débogage sont fournies (F5), dont « test sous le curseur ».

**PyCharm** — ouvrez le dossier racine, puis :
1. *Settings → Languages & Frameworks → Django* : cocher « Enable Django Support »,
   racine = le dossier du projet, settings = `config/settings/dev.py`,
   manage script = `manage.py`.
2. *Project Structure* : marquer `templates` comme *Template folder* et
   `static` comme *Resource root*.
3. Deux configurations d'exécution sont déjà présentes dans
   `.idea/runConfigurations/`.

**Interpréteur** — pointez-le sur `.venv/bin/python`. Sans cela, l'IDE ne
résout ni Django ni les imports `apps.*`.

## Réglages par environnement

| Module | Usage | Particularités |
|---|---|---|
| `config.settings.dev` | développement | `DEBUG=True`, SQLite, cookies non sécurisés |
| `config.settings.test` | tests | base en mémoire, hachage MD5 pour la vitesse |
| `config.settings.prod` | production | PostgreSQL, HSTS, **échoue si une variable manque** |

Le module par défaut de `manage.py` est `dev`. Pour les tests, l'option
`--settings=config.settings.test` est obligatoire : sans elle, django-axes
verrouille les comptes entre deux exécutions.

## Conventions

**Messages de commit** — format Conventional Commits :

```
<type>(<portée>): <description à l'infinitif ou au présent>

Corps facultatif expliquant le POURQUOI, pas le QUOI :
le diff dit déjà ce qui change.
```

Types employés : `feat`, `fix`, `test`, `docs`, `refactor`, `chore`.
Portées : `accounts`, `catalog`, `deals`, `payments`, `moderation`, `api`,
`web`, `admin`, `security`, `i18n`, `data`.

**Style** — ruff, 96 colonnes. `make format` avant de committer, ou installez
les hooks : `pre-commit install`.

**Commentaires** — expliquer une décision, jamais paraphraser le code.
Un commentaire qui répète la ligne suivante est du bruit.

## Ajouter un champ à un modèle

```bash
# 1. modifier le modèle
# 2. générer la migration
python3 manage.py makemigrations <app>
# 3. relire le fichier généré : Django se trompe parfois sur les valeurs par défaut
# 4. appliquer et tester
make migrate test
# 5. régénérer le dictionnaire, qui est dérivé du schéma
make dict
```

Le hook `no-missing-migrations` refuse un commit dont les modèles et les
migrations divergent.

## Ajouter une langue

```bash
python3 manage.py makemessages -l es
# ajouter le dictionnaire ES dans scripts/translations.py
python3 scripts/apply_translations.py
```

Puis déclarer la langue dans `LANGUAGES` (`config/settings/base.py`). Les
libellés de catégorie sont en base : une ligne `CategoryTranslation` par
catégorie, aucune migration nécessaire.

## Tests

```bash
make test                                              # les 101
python3 manage.py test tests.test_unit --settings=config.settings.test
python3 manage.py test tests.test_integration.ApiTests --settings=config.settings.test
```

Les fabriques sont dans `tests/factories.py`. `seed_reference_data()` crée le
minimum de référentiels ; `make_user`, `make_deal` et `make_merchant` produisent
des objets valides qu'on surcharge par mots-clés.

**Piège connu** — `Client.login()` échoue avec django-axes, qui exige un objet
`request`. Utilisez `self.login(user)` de `BaseIntegrationTest`, qui passe par
`force_login` avec le backend explicite. Les tests qui vérifient le
verrouillage postent le vrai formulaire.

## PostgreSQL en local

SQLite convient au quotidien, mais certaines contraintes se comportent
différemment. Pour vérifier :

```bash
docker compose up -d
cp .env.example .env       # renseigner POSTGRES_*
DJANGO_SETTINGS_MODULE=config.settings.prod python3 manage.py migrate
```

## Pour aller plus loin

| Sujet | Document |
|---|---|
| Schéma détaillé | `docs/DATA_DICTIONARY.md` |
| Sécurité, couche par couche | `docs/SECURITY.md` |
| Points d'entrée de l'API | `docs/API.md` |
| RGPD et droit belge | `docs/LEGAL_GDPR.md` |

## Historique Git

Le dépôt compte 32 commits, un par décision d'architecture, dans l'ordre où
elles se posent : le socle, le domaine, la sécurité, l'API, le front-office,
les tests, la documentation.

```bash
git log --oneline --reverse      # la progression d'un coup d'œil
git log --format="%B" -1 <sha>   # le raisonnement derrière un commit
git show --stat <sha>            # les fichiers d'une décision
```

Le corps de chaque message explique le **pourquoi**. Par exemple, celui du
commit sur les paiements dit pourquoi `PROTECT` plutôt que `CASCADE`, et
celui sur django-axes pourquoi le verrou porte sur le couple (IP, identifiant)
plutôt que sur l'un des deux.

**Deux limites à connaître.** L'historique est logiquement ordonné mais **pas
bisectable** : un `git checkout` sur un commit intermédiaire ne donne pas
forcément un projet qui démarre, puisque les tests n'arrivent qu'au commit qui
les introduit. Et un fichier touché par plusieurs décisions apparaît en une
seule fois, à la décision qui l'a motivé.

**Reconstruire l'historique** — par exemple après avoir réorganisé les commits :

```bash
rm -rf .git && python3 scripts/build_git_history.py
```

La table `COMMITS` du script associe chaque fichier à un commit. Si vous ajoutez
un fichier sans l'y déclarer, le script le signale et le rattache à un commit de
rattrapage : rien ne peut sortir du dépôt par inadvertance.

## Publier le dépôt

```bash
git remote add origin git@github.com:<vous>/dealtrack.git
git push -u origin main
```

Vérifiez avant de pousser qu'aucun secret n'est suivi :

```bash
git ls-files | grep -E "^\.env$|\.pem$"    # doit ne rien renvoyer
```

Le hook `detect-private-key` de pre-commit couvre déjà ce cas à chaque commit.
