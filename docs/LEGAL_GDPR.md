# Conformité légale — DealTrack.be

> **Avertissement.** Ce document décrit les choix techniques du projet au regard
> du droit applicable et les raisons qui les motivent. Il ne constitue pas un
> avis juridique. Avant toute exploitation réelle, faites valider ces points par
> un juriste : les analyses ci-dessous sont celles d'un développeur, pas d'un
> avocat, et certaines questions — le statut d'hébergeur, notamment — sont
> discutées en doctrine.

Cadre applicable : RGPD (règlement UE 2016/679), loi belge du 30 juillet 2018,
Code de droit économique belge (CDE), Code des impôts sur les revenus (CIR 92),
livre XI du CDE pour le droit d'auteur.

---

## 1. RGPD — traitement des données

### 1.1 Registre des traitements (art. 30)

| Traitement | Base légale | Données | Conservation |
|---|---|---|---|
| Compte membre | contrat (art. 6.1.b) | e-mail, pseudonyme, langue, région | durée du compte, puis anonymisation |
| Publication de deals | contrat | contenu, horodatage, auteur | conservé, réattribué à un pseudonyme anonyme |
| Paiement de l'abonnement | contrat + **obligation légale** (art. 6.1.c) | montant, TVA, référence, 4 derniers chiffres | **7 ans** (art. 315 CIR 92) |
| Journal de sécurité | intérêt légitime (art. 6.1.f) | IP, user-agent, action, horodatage | 365 jours |
| Newsletter | **consentement** (art. 6.1.a) | e-mail | jusqu'au retrait |
| Modération | intérêt légitime | décision, motif, modérateur | durée du compte |

Le consentement marketing est un champ **distinct** de l'acceptation des CGU,
avec sa propre case non pré-cochée. C'est l'exigence de l'article 7.2 : un
consentement groupé avec l'acceptation d'un contrat n'est pas libre.

```python
# apps/accounts/models.py
marketing_consent = models.BooleanField(
    default=False,
    help_text=_("Consentement explicite, distinct des CGU (art. 7 RGPD)."),
)
```

### 1.2 Minimisation (art. 5.1.c)

Ce que le projet **ne collecte pas**, délibérément : nom civil, adresse postale,
date de naissance, numéro de téléphone, numéro de carte bancaire. Un site de
bons plans n'en a pas besoin. Le pseudonyme suffit à l'identité publique,
l'e-mail à la connexion et aux alertes.

L'adresse IP est collectée, mais uniquement dans la piste d'audit, et à des fins
de sécurité — pas de profilage.

### 1.3 Droit à l'effacement (art. 17) — le point délicat

**La difficulté.** L'article 17.1 donne un droit à l'effacement. L'article
17.3.b y apporte une exception lorsque le traitement est nécessaire pour
respecter une obligation légale. Or l'article 315 du CIR 92 impose de conserver
les pièces comptables **sept ans**.

Ces deux textes ne se contredisent pas : le second l'emporte sur le premier pour
les seules données figurant sur une pièce comptable.

**La traduction technique.** Deux opérations distinctes, dans cet ordre.

```python
user.soft_delete()   # accès coupé, ligne conservée, deleted_at renseigné
user.anonymise()     # e-mail et pseudonyme écrasés, mot de passe rendu inutilisable
```

Et une contrainte de base qui rend l'erreur impossible :

```python
# apps/payments/models.py
user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
```

Une suppression physique lève `ProtectedError`. Ce n'est pas un effet de bord
qu'on tolère : c'est le mécanisme voulu. Le back-office ne propose d'ailleurs
pas la suppression, seulement la désinscription et l'anonymisation.

**Le résultat, vérifié en SQL brut** par
`python3 manage.py demo_soft_delete --anonymise` :

```
ProtectedError levée. Objets protégés : Comment, Deal, Payment, Report, Subscription

accounts_user    → ('anonyme-39dbb0e3@anonymised.dealtrack.invalid',
                    'membre-supprimé-39dbb0e3', False, 1)
payments_payment → ('DT-2026-000001', 24, 'succeeded')
Factures orphelines : 0
```

La facture reste rattachable à une entité comptable, sans que cette entité soit
encore identifiable. L'anonymisation est **irréversible** : aucune table de
correspondance n'est conservée, sans quoi il s'agirait de pseudonymisation — qui
reste, elle, une donnée personnelle au sens du considérant 26.

**Ce que l'API répond.** `DELETE /api/v1/me/` distingue les deux cas :

```json
{"status": "anonymised"}                          // aucun paiement
{"status": "soft_deleted_pending_retention"}      // facture existante
```

Le second cas est annoncé à l'utilisateur avant confirmation, sur la page de
fermeture de compte. Informer d'une limite au droit d'effacement fait partie de
l'obligation de transparence (art. 12).

### 1.4 Droit à la portabilité (art. 20)

`GET /api/v1/me/export/`, ou le bouton du profil, produit un JSON structuré :
identité, préférences, deals publiés, commentaires, factures. Format lisible par
machine et interopérable, comme l'exige l'article 20.1.

Chaque export est consigné dans la piste d'audit — utile en cas de contestation
sur le respect du délai d'un mois (art. 12.3).

### 1.5 Autres droits

| Droit | Article | Mise en œuvre |
|---|---|---|
| Accès | 15 | page de profil + export JSON |
| Rectification | 16 | édition du profil |
| Opposition au marketing | 21 | case décochable, effet immédiat |
| Ne pas subir de décision automatisée | 22 | sans objet : toute modération est humaine et tracée |

Sur l'article 22 : la file de modération affiche des indicateurs automatiques
(« prix de référence contesté », « indépendant à vérifier »), mais la décision
appartient toujours à un modérateur identifié, et son motif est enregistré.

### 1.6 Sécurité du traitement (art. 32)

Argon2, TLS obligatoire en production, HSTS, journalisation des accès, principe
du moindre privilège via trois rôles. Détail dans [`SECURITY.md`](SECURITY.md).

### 1.7 Violation de données (art. 33-34)

Non implémenté, et c'est une lacune à combler : notification à l'Autorité de
protection des données sous 72 heures, information des personnes concernées si
le risque est élevé. Le projet fournit les éléments nécessaires — piste d'audit
horodatée, journal de sécurité — mais pas la procédure organisationnelle.

### 1.8 Autorité compétente

Autorité de protection des données (APD/GBA), rue de la Presse 35, 1000
Bruxelles. La désignation d'un DPO n'est pas obligatoire ici : le traitement
n'est pas à grande échelle au sens de l'article 37.1.b, et les données ne
relèvent pas de l'article 9. Elle deviendrait recommandée à partir de quelques
dizaines de milliers de membres actifs.

---

## 2. Droit belge de l'e-commerce

### 2.1 Annonce de réduction de prix — le point le plus surveillé

**La règle.** L'article VI.18 du CDE, qui transpose la directive Omnibus
(UE 2019/2161), impose que toute annonce de réduction indique le **prix le plus
bas pratiqué durant les 30 jours précédents**.

C'est la règle qu'une plateforme de bons plans risque le plus de contourner : un
prix barré gonflé rend n'importe quelle offre attirante.

**Trois niveaux de défense.**

1. **En base** — une contrainte `CHECK` :

```python
models.CheckConstraint(
    condition=models.Q(reference_price__isnull=True)
    | models.Q(reference_price__gt=models.F("price")),
    name="deal_reference_price_above_price",
)
```

2. **Côté serveur** — formulaire et sérialiseur refusent avec un message
   explicite qui cite la règle.

3. **À l'interface** — un encart d'avertissement sur la page de publication, et
   sur la page de détail la mention de ce que le prix de référence signifie
   exactement.

Ces trois niveaux ne remplacent pas la vérification humaine : le système ne peut
pas savoir si le prix barré déclaré correspond vraiment au plancher des 30 jours.
Il peut seulement rendre l'incohérence évidente et forcer un passage par la
modération. Le motif de signalement « Réduction trompeuse » existe pour la suite.

### 2.2 Droit de rétractation

Article VI.47 : quatorze jours pour les contrats à distance. L'abonnement Club
en relève.

Article VI.53, 13° : le droit s'éteint si le service a été pleinement exécuté
après accord préalable exprès du consommateur et reconnaissance de la perte de
son droit. La page de souscription mentionne la règle ; en production, il
faudrait une case de renonciation distincte, non pré-cochée.

**Ce que le projet ne fait pas :** l'abonnement démarre immédiatement sans
recueillir cette renonciation expresse. À corriger avant exploitation.

### 2.3 Information précontractuelle (art. VI.45)

Sur la page de souscription : prix TVAC, taux de TVA, durée, identité du
vendeur, modalités de paiement. La facture porte un numéro séquentiel continu
et fait apparaître la TVA séparément, comme l'exige l'article 5 de l'AR n° 1 en
matière de TVA.

```python
def next_reference():
    """Numérotation continue par exercice comptable."""
    return f"DT-{year}-{nxt:06d}"
```

### 2.4 Statut de la plateforme

DealTrack héberge des contenus déposés par ses membres. Le régime de
responsabilité limitée de l'hébergeur (art. XII.19 CDE, transposant la directive
2000/31/CE) suppose de ne pas jouer de rôle actif dans la connaissance ou le
contrôle des contenus.

**Or ce projet modère a priori** : chaque offre passe en file d'attente et est
validée par un humain avant publication. Cela peut être analysé comme un rôle
actif, et donc fragiliser le bénéfice du régime.

Le choix reste défendable — modérer améliore nettement la qualité et protège les
membres — mais il doit être fait en connaissance de cause. C'est typiquement le
point à soumettre à un juriste, d'autant que le DSA (règlement UE 2022/2065) a
depuis modifié le paysage pour les plateformes en ligne.

Ce que le projet met en place indépendamment de cette question : mécanisme de
signalement par les membres, traçabilité nominative des décisions de modération,
motif obligatoire en cas de refus — trois éléments que le DSA exige de toute
façon.

### 2.5 Affiliation

Si DealTrack perçoit une commission sur les liens sortants, l'article VI.97 du
CDE (pratiques trompeuses) impose de le divulguer clairement.

**Non implémenté.** Aucun champ ne distingue actuellement un lien affilié d'un
lien ordinaire. À ajouter avant toute monétisation : un booléen `is_affiliate`
sur `Deal` ou `Merchant`, et une mention visible sur chaque carte concernée.

Le motif de signalement « Lien d'affiliation personnel » vise un autre problème :
un membre qui glisse son propre lien affilié dans une offre.

### 2.6 Langues

Le front-office est disponible en français, néerlandais et allemand — les trois
langues officielles de Belgique. Ce n'est pas qu'une commodité : proposer un
service à un consommateur néerlandophone en français seulement pose un problème
d'information compréhensible au sens de l'article VI.45 §1er.

---

## 3. Propriété intellectuelle

### 3.1 Contenus déposés par les membres

Un titre et une description de deal sont protégeables par le droit d'auteur dès
lors qu'ils sont originaux (art. XI.165 CDE). L'auteur reste titulaire de ses
droits ; les CGU doivent prévoir une licence non exclusive d'exploitation sur la
plateforme, ce qui relève de la rédaction juridique et non du code.

Techniquement, le projet conserve le lien vers l'auteur (`submitted_by` en
`PROTECT`) même après désinscription, ce qui permet d'honorer le droit de
paternité tout en respectant l'anonymisation : le contenu reste attribué, mais
à un pseudonyme non identifiant.

### 3.2 Marques et visuels des marchands

Citer « Colruyt » ou « Coolblue » pour désigner l'enseigne où l'offre est
disponible relève de l'usage descriptif et référentiel, admis par l'article 14.1.c
du règlement UE 2017/1001 sur la marque de l'Union européenne. C'est ce que fait
le projet : le nom sert à identifier le vendeur, sans suggérer un partenariat.

**Le point sensible est ailleurs.** Reproduire les photographies produit d'un
marchand est une reproduction d'œuvre protégée, sans exception applicable. C'est
le risque juridique le plus concret d'un site de ce type.

Le projet stocke donc uniquement un **lien** (`external_url`) et n'héberge aucune
image marchande. Les vignettes sont des illustrations génériques. Toute
évolution vers l'affichage de photos produit exigerait soit un accord avec les
marchands, soit un flux officiel de type Open Graph avec autorisation explicite.

### 3.3 Données de la plateforme

L'ensemble des offres accumulées peut constituer une base de données protégée
par le droit *sui generis* (art. XI.306 CDE) si son obtention représente un
investissement substantiel. La limitation de débit anonyme à 60 requêtes par
heure sert accessoirement à faire obstacle à l'extraction systématique.

---

## 4. Récapitulatif : conforme, partiel, à faire

| Exigence | État | Où |
|---|---|---|
| Bases légales identifiées et distinctes | ✅ | ce document, §1.1 |
| Consentement marketing séparé des CGU | ✅ | `RegistrationForm` |
| Minimisation des données | ✅ | modèle `User` |
| Droit d'accès et portabilité | ✅ | `/me/export/`, page profil |
| Droit à l'effacement, arbitré avec la conservation comptable | ✅ | `soft_delete` + `anonymise` |
| Conservation comptable de 7 ans garantie par contrainte | ✅ | `PROTECT` sur `Payment.user` |
| Traçabilité des accès et décisions | ✅ | `AuditLog` |
| Sécurité du traitement (art. 32) | ✅ | `SECURITY.md` |
| Contrôle de l'annonce de réduction | ✅ | contrainte + validation + interface |
| Facturation numérotée avec TVA distincte | ✅ | `Payment.next_reference` |
| Trilinguisme du front-office | ✅ | `locale/` |
| Signalement et modération tracée | ✅ | `Report`, `ModerationDecision` |
| Renonciation expresse au droit de rétractation | ⚠️ mentionnée, pas recueillie | `payments/subscribe.html` |
| Divulgation des liens d'affiliation | ❌ à implémenter | — |
| Procédure de notification de violation | ❌ organisationnelle | — |
| Purge automatique du journal après 365 jours | ❌ réglage défini, tâche absente | `AUDIT_LOG_RETENTION_DAYS` |
| CGU et politique de confidentialité rédigées | ❌ hors périmètre technique | — |
| Analyse du statut d'hébergeur au regard du DSA | ❌ à soumettre à un juriste | §2.4 |

Six points ouverts sur dix-huit. Les énumérer vaut mieux que de prétendre à une
conformité complète : un projet qui affiche vingt cases cochées sur vingt n'a
généralement pas regardé d'assez près.
