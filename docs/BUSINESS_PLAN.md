# Business plan — DealTrack.be

> Partie 3 de l'épreuve intégrée : positionnement face à la concurrence, forces
> et faiblesses, analyse de rentabilité, aspects juridiques.
>
> Les chiffres marqués **(hypothèse)** sont des estimations de travail, à
> vérifier avant tout lancement réel. Les chiffres propres à l'application
> (prix des formules, nombre de commerçants…) viennent de la base de données.

---

## 1. Le projet en une phrase

DealTrack.be est la communauté belge des bons plans : les membres partagent les
meilleures offres des enseignes et des commerçants indépendants belges, votent
pour les faire remonter et les commentent, en français, en néerlandais et en
allemand.

**Problème.** Un consommateur belge qui cherche une bonne affaire en ligne
tombe sur des communautés étrangères (offres livrables en France ou aux
Pays-Bas, dans une seule langue) ou sur des folders publicitaires sans avis
d'utilisateurs. Les fausses réductions restent fréquentes, et les commerces de
quartier sont absents de ces plateformes.

**Solution.** Une plateforme pensée pour la Belgique :

- trois langues nationales, interface et contenus (traduction des offres et des
  commentaires) ;
- offres livrables en Belgique, avec le prix de référence légal (prix le plus
  bas des 30 derniers jours) et la réduction calculée automatiquement ;
- annuaire des commerçants indépendants (127 commerces locaux référencés) ;
- modération humaine avant publication, signalements, journal d'audit ;
- un abonnement **VIP** pour les acheteurs exigeants : historique du prix,
  comparaison avec d'autres sites, alertes reçues en priorité.

---

## 2. Marché et cible

| Cible | Besoin | Ce que DealTrack apporte |
|---|---|---|
| Chasseurs de bons plans (18-45 ans, à l'aise en ligne) | Trouver vite les vraies bonnes affaires | Flux trié par la communauté (température), alertes |
| Familles et ménages attentifs au budget | Économiser sur l'électroménager, l'alimentation, les loisirs | Catégories, prix de référence, signalement des fausses promos |
| Acheteurs « réfléchis » | Savoir si c'est le bon moment d'acheter | VIP : historique du prix et comparaison |
| Commerçants indépendants belges | Être visibles face aux grandes enseignes | Annuaire local gratuit, mise en avant payante (piste) |

**Pourquoi la Belgique.** Un marché trilingue, souvent servi par des
plateformes françaises ou néerlandaises qui ne parlent qu'une de ses langues.
La seule fonction de traduction et la prise en compte des trois communautés
linguistiques constituent déjà une différence nette.

---

## 3. Concurrence et positionnement

| Acteur | Type | Points forts | Limites pour un Belge |
|---|---|---|---|
| **Dealabs** (France, réseau Pepper) | Communauté de bons plans | Très grande communauté, vote et commentaires | Français uniquement, offres pensées pour le marché français (livraison, enseignes) |
| **Pepper NL** (Pays-Bas, réseau Pepper) | Communauté de bons plans | Même modèle, en néerlandais | Offres et enseignes néerlandaises, pas de français ni d'allemand |
| **Promobutler** (Belgique, groupe Publitas) | Folders promotionnels des enseignes | Très connu en Belgique, toutes les enseignes | Contenu publicitaire des marques : pas de vote, pas d'avis, pas de bons plans repérés par les utilisateurs |
| **Comparateurs de prix** (Google Shopping, etc.) | Prix par produit | Exhaustifs | Pas de communauté, pas de détection des fausses réductions, pas de commerces de quartier |

D'après nos recherches, le réseau Pepper (Dealabs, mydealz, Pepper NL…) ne
compte pas de communauté propre à la Belgique : c'est l'espace que vise
DealTrack.

**Positionnement.** *La communauté de bons plans belge, trilingue, qui défend
le vrai prix et le commerce local.* DealTrack ne cherche pas à rivaliser en
volume avec Dealabs, mais à être plus pertinent pour un acheteur en Belgique.

```
                  Communautaire (votes, avis)
                            ▲
              Dealabs ●     │     ● DealTrack.be
            Pepper NL ●     │
   Étranger ◄───────────────┼───────────────► Belge
                            │
                            │     ● Promobutler
     Comparateurs de prix ● │
                            ▼
                  Publicitaire / catalogue
```

---

## 4. Forces, faiblesses, opportunités, menaces (SWOT)

| | Positif | Négatif |
|---|---|---|
| **Interne** | **Forces** <br>• FR / NL / DE, contenus traduits <br>• Prix de référence légal sur 30 jours et réduction calculée <br>• Commerçants locaux (OpenStreetMap) <br>• Modération avant publication : qualité, confiance <br>• Publication en collant un lien (pré-remplissage automatique) <br>• Sécurité et RGPD intégrés dès la conception <br>• Coûts techniques faibles | **Faiblesses** <br>• Notoriété nulle au lancement <br>• Une communauté se construit lentement (effet réseau) <br>• Dépend de membres actifs qui publient bénévolement <br>• Certains sites bloquent la lecture automatique des prix (Coolblue, bol.com) <br>• Équipe d'une personne |
| **Externe** | **Opportunités** <br>• Pas de communauté Pepper dédiée à la Belgique <br>• Pics saisonniers : Black Friday, Black November / December, soldes <br>• Règles européennes sur l'annonce des réductions (prix des 30 derniers jours) : la transparence devient un argument <br>• Soutien au commerce local | **Menaces** <br>• Le réseau Pepper pourrait ouvrir une version belge <br>• Habitudes déjà prises sur Dealabs, Pepper NL ou Promobutler <br>• Évolution du statut des plateformes (DSA) et de la responsabilité de l'hébergeur <br>• Dépendance au prestataire de paiement et aux sites marchands |

---

## 5. Modèle économique

| Source de revenu | Statut | Détail |
|---|---|---|
| **Abonnement VIP** | ✅ en place | 2,50 € par mois ou 24 € par an (TVA 21 % comprise), paiement Stripe (carte, Bancontact) |
| **Publicité maison** | ✅ en place | Deux emplacements, aujourd'hui pour les offres de DealTrack ; vendables à des annonceurs sans traceur tiers |
| **Mise en avant des commerçants locaux** | 💡 piste | Abonnement « vitrine » pour un commerce indépendant, par exemple 9,99 € par mois **(hypothèse)** |
| **Liens d'affiliation** | 💡 piste | Commission sur les achats via les liens sortants ; impose d'abord de signaler clairement les liens affiliés (voir LEGAL_GDPR.md §2.5) |

Le site reste **gratuit** pour lire, publier, voter et commenter : c'est ce qui
fait vivre la communauté. Le VIP vend du confort et de l'avance, pas l'accès.

---

## 6. Analyse de rentabilité

### 6.1 Ce que rapporte un membre VIP

Hypothèse de frais Stripe : 1,5 % + 0,25 € par paiement par carte européenne
**(hypothèse, à vérifier sur stripe.com/fr-be/pricing)**.

| | VIP mensuel | VIP annuel |
|---|---|---|
| Prix payé (TVAC) | 2,50 € | 24,00 € |
| Hors TVA (21 %) | 2,07 € | 19,83 € |
| Frais Stripe estimés | 0,29 € par mois | 0,61 € par an |
| **Revenu net par mois** | **1,78 €** | **1,60 €** |

**Constat.** Sur un petit montant, la commission fixe de Stripe pèse lourd :
0,25 € sur 2,50 €, c'est 10 % du prix. La formule annuelle, payée une seule fois
par an, perd beaucoup moins en frais : il faut la mettre en avant (deux mois
offerts : 24 € au lieu de 30 €).

Pour la suite, on retient un revenu net moyen de **1,70 € par VIP et par mois**.

### 6.2 Coûts mensuels

| Poste | Coût mensuel |
|---|---|
| Hébergement web + base PostgreSQL | ≈ 20 € **(hypothèse)** |
| Nom de domaine dealtrack.be | ≈ 1 € (≈ 12 € par an, **hypothèse**) |
| Envoi des e-mails (alertes, confirmations) | 0 à 10 € selon le volume **(hypothèse)** |
| **Total technique** | **≈ 30 € par mois** |
| Développeur à mi-temps (si le projet grandit) | ≈ 2 000 € **(hypothèse)** |

### 6.3 Seuil de rentabilité

| Objectif | Calcul | Membres VIP nécessaires |
|---|---|---|
| Couvrir les coûts techniques | 30 € ÷ 1,70 € | **≈ 18 VIP** |
| Payer aussi un mi-temps | 2 030 € ÷ 1,70 € | **≈ 1 200 VIP** |

Avec un taux de conversion des membres gratuits vers le VIP de 2 à 5 %
**(hypothèse, ordre de grandeur courant pour un modèle « freemium »)** :

- 18 VIP demandent environ **360 à 900 membres actifs** : atteignable dès la
  première année ;
- 1 200 VIP demandent environ **24 000 à 60 000 membres actifs** : objectif à
  plusieurs années, qui suppose les revenus complémentaires (publicité,
  commerçants locaux, affiliation).

### 6.4 Trois scénarios sur trois ans

| | Année 1 | Année 2 | Année 3 |
|---|---|---|---|
| Membres actifs **(hypothèse)** | 2 000 | 8 000 | 20 000 |
| VIP à 3 % de conversion | 60 | 240 | 600 |
| Revenu VIP net par an | 1 224 € | 4 896 € | 12 240 € |
| Commerçants « vitrine » **(hypothèse)** | 5 | 20 | 50 |
| Revenu vitrines HT par an (8,26 € HT / mois, hors frais de paiement) | 496 € | 1 982 € | 4 956 € |
| **Total des revenus** | **≈ 1 720 €** | **≈ 6 880 €** | **≈ 17 200 €** |
| Coûts techniques par an | ≈ 360 € | ≈ 480 € | ≈ 720 € |
| **Résultat avant salaire** | **≈ + 1 360 €** | **≈ + 6 400 €** | **≈ + 16 480 €** |

**Lecture.** Le projet couvre ses frais techniques dès la première année. Il
devient une activité complémentaire viable en année 3, mais pas encore un
salaire complet : c'est un projet à faire grandir progressivement, sans gros
investissement de départ.

---

## 7. Plan d'action

1. **Lancement (mois 1-3)** : mise en ligne, 500 premiers bons plans publiés par
   l'équipe et quelques membres fondateurs, présence sur les réseaux sociaux
   belges.
2. **Saisons fortes** : opérations Black November / Black December (déjà dans
   l'application), soldes de janvier et de juillet.
3. **Commerçants locaux (mois 4-12)** : démarchage dans une commune test,
   offre de lancement gratuite pour la vitrine.
4. **Mesure** : membres actifs, deals publiés par semaine, taux de conversion
   VIP, coût par membre acquis.

---

## 8. Aspects juridiques (résumé)

Le détail figure dans `docs/LEGAL_GDPR.md`.

| Domaine | Ce que fait DealTrack |
|---|---|
| **RGPD** | Registre des traitements, minimisation des données, consentement marketing séparé, export des données (portabilité), journal d'audit, mots de passe Argon2 |
| **Droit à l'oubli** | Désinscription logique puis anonymisation : les données personnelles sont effacées, les factures restent rattachées à une entité anonyme (conservation comptable de 7 ans) |
| **E-commerce belge (CDE)** | Annonce de réduction par rapport au prix le plus bas des 30 derniers jours ; renonciation expresse au droit de rétractation de 14 jours pour un démarrage immédiat ; prix TVA comprise et facture |
| **Paiement** | Aucune donnée de carte chez DealTrack (page hébergée par Stripe), confirmation côté serveur, webhook signé |
| **Statut de la plateforme** | Hébergeur de contenus des membres ; la modération a priori est un choix assumé, avec signalement, motif de refus et traçabilité (exigences du DSA) |
| **Droit d'auteur et marques** | Noms des enseignes utilisés seulement pour identifier le vendeur. Photos produit affichées par lien depuis la page du marchand, sans copie : défendable (jurisprudence européenne sur les liens), mais à sécuriser par accord ou flux officiel avant un lancement commercial — c'est le risque juridique le plus concret |
| **Affiliation** | Si elle est activée, chaque lien affilié devra être signalé clairement (pratiques trompeuses, art. VI.97 CDE) |

---

## 9. Le pitch en trois minutes (pour la présentation)

1. **Le constat** : les Belges chassent les bons plans sur des sites français ou
   néerlandais, dans une seule langue, avec des offres souvent pas livrables chez
   eux, et sans les commerces de leur quartier.
2. **La réponse** : DealTrack.be, la communauté de bons plans belge, en trois
   langues, qui affiche le vrai prix de référence et met en avant les
   indépendants.
3. **La différence** : trilingue, prix de référence légal, commerçants locaux,
   modération avant publication. Le VIP ajoute l'historique du prix, la
   comparaison et les alertes en premier.
4. **Le modèle** : gratuit pour la communauté, VIP à 2,50 € par mois ou 24 € par
   an, publicité et vitrines locales en complément.
5. **Les chiffres** : environ 18 VIP suffisent à couvrir les frais techniques ;
   le projet grandit sans investissement lourd.
6. **Les risques assumés** : construire la communauté et l'arrivée possible d'un
   grand concurrent. La réponse : être plus belge, plus local et plus fiable.

---

## Sources

- Réseau Pepper (Dealabs, mydealz, Pepper NL) :
  [tech.eu](https://tech.eu/2015/11/03/pepper-com-social-commerce/),
  [communiqué Dealabs](https://www.dealabs.com/presse/162536-pepper-com-le-reseau-mondial-de-bons-plans-dont-dealabs-fait-partie-lance-une-plateforme-espagnole-chollometro-com/)
- Promobutler (groupe Publitas) : [publitas.com/publitas-brands](https://publitas.com/publitas-brands)
- Bancontact, moyen de paiement en ligne le plus utilisé en Belgique :
  [documentation Stripe](https://docs.stripe.com/payments/bancontact)
- Frais Stripe : grille officielle à consulter sur stripe.com (Belgique) ; le
  montant utilisé ici est une hypothèse de travail.
