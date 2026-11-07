# frontend/ — interface

Ce que le navigateur reçoit : pages HTML, feuille de style et traductions.
Les pages sont rendues côté serveur par Django (pas de framework JavaScript) :
le backend remplit les gabarits avec les données, puis envoie du HTML.

## Contenu

| Dossier | Rôle |
|---|---|
| `templates/base.html` | Mise en page commune : en-tête, navigation, sélecteur de langue |
| `templates/_form.html` | Affichage générique d'un formulaire et de ses erreurs |
| `templates/deals/` | Flux des offres, détail, publication en deux étapes |
| `templates/registration/` | Connexion, inscription, profil, fermeture du compte, verrouillage |
| `templates/payments/` | Abonnement |
| `templates/errors/` | Pages 403, 404, 500 et échec CSRF (sans trace technique) |
| `static/css/dealtrack.css` | Feuille de style unique, couleurs en variables CSS |
| `locale/nl/`, `locale/de/` | Traductions néerlandaises et allemandes (`.po` source, `.mo` compilé) |

## Sécurité côté interface

- **XSS** : Django échappe automatiquement toute variable affichée (`{{ … }}`).
  Dans le JavaScript, les textes traduits passent par le filtre `escapejs`.
- **CSRF** : chaque formulaire POST contient `{% csrf_token %}` ; les appels
  `fetch` envoient le jeton dans l'en-tête `X-CSRFToken`.
- **Validation** : les champs HTML (`type="url"`, `required`, `maxlength`) et
  le JavaScript aident l'utilisateur, mais le backend revalide tout.

## Traductions

Les textes sont écrits en français dans les gabarits (`{% trans "…" %}`).
Les traductions vivent dans `backend/scripts/translations.py` ; pour les
réinjecter et recompiler les `.mo` :

```bash
python backend/scripts/apply_translations.py
```
