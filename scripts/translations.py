"""
Traductions néerlandaise et allemande.

Le français est la langue source : les msgid sont en français, ce qui évite la
double traduction fr → en → nl qui dégrade les formulations juridiques.

Les termes réglementaires suivent la terminologie officielle belge : « RGPD »
devient AVG en néerlandais et DSGVO en allemand, « TVA » devient btw puis MwSt.
"""

NL = {
    # -- Navigation et structure -----------------------------------------
    "Français": "Frans",
    "Nederlands": "Nederlands",
    "Deutsch": "Duits",
    "DealTrack.be": "DealTrack.be",
    "La plateforme communautaire des bons plans en Belgique.": "Het community-platform voor koopjes in België.",
    "Rechercher un bon plan": "Zoek een koopje",
    "Recherche…": "Zoeken…",
    "Catégories": "Categorieën",
    "Tous les deals": "Alle deals",
    "Commerçants locaux": "Lokale handelaars",
    "Club": "Club",
    "Connexion": "Aanmelden",
    "Inscription": "Registreren",
    "Déconnexion": "Afmelden",
    "Modération": "Moderatie",
    "Publier": "Plaatsen",
    "Accueil": "Home",
    "Découvrir": "Ontdekken",
    "Participer": "Deelnemen",
    "Vos données": "Uw gegevens",
    "Région": "Regio",
    "Filtrer par région": "Filter op regio",
    "Toute la Belgique": "Heel België",
    "Tendance": "Trending",
    "Nouveaux": "Nieuw",
    "Prix croissant": "Prijs oplopend",
    "Pagination": "Paginering",
    "Précédent": "Vorige",
    "Suivant": "Volgende",
    "Page %(n)s sur %(total)s": "Pagina %(n)s van %(total)s",
    "Bruxelles, Belgique": "Brussel, België",
    "Prix TVA belge comprise.": "Prijzen inclusief Belgische btw.",
    "Plateforme communautaire des bons plans en Belgique, disponible en français, "
    "néerlandais et allemand.": "Community-platform voor koopjes in België, beschikbaar in het Frans, "
    "Nederlands en Duits.",
    "Politique de confidentialité": "Privacybeleid",
    # -- Flux de deals ----------------------------------------------------
    "Les meilleurs bons plans en Belgique": "De beste koopjes van België",
    "Refroidir": "Afkoelen",
    "Réchauffer": "Opwarmen",
    "Expiré": "Verlopen",
    "Publié il y a %(when)s": "%(when)s geleden geplaatst",
    "Offre vérifiée": "Geverifieerde aanbieding",
    "Commerçant local": "Lokale handelaar",
    "Transfrontalier": "Grensoverschrijdend",
    # Repli d'une offre non traduite : le nom de la langue est injecté dans la
    # phrase, d'où les trois entrées qui suivent.
    "Offre rédigée en %(lang)s": "Aanbieding opgesteld in het %(lang)s",
    "français": "Frans",
    "néerlandais": "Nederlands",
    "allemand": "Duits",
    "Livraison gratuite": "Gratis levering",
    "Livraison": "Levering",
    "Dispo. chez": "Beschikbaar bij",
    "Partagé par": "Gedeeld door",
    "commentaires": "reacties",
    "Voir le deal": "Bekijk de deal",
    "Aucun deal ne correspond à ces critères.": "Geen enkele deal voldoet aan deze criteria.",
    "Les plus hot": "Populairste",
    "Créer une alerte": "Melding instellen",
    "Recevez un e-mail dès qu'un deal correspond à vos critères.": "Ontvang een e-mail zodra een deal aan uw criteria voldoet.",
    "Gérer mes alertes": "Mijn meldingen beheren",
    "Créer un compte": "Account aanmaken",
    "À propos de ce deal": "Over deze deal",
    "Membre depuis": "Lid sinds",
    "Achat confirmé": "Aankoop bevestigd",
    "Aucun commentaire pour l'instant.": "Nog geen reacties.",
    "Ajouter un commentaire": "Een reactie toevoegen",
    "Publier le commentaire": "Reactie plaatsen",
    "Connectez-vous pour commenter.": "Meld u aan om te reageren.",
    "Commentaire publié.": "Reactie geplaatst.",
    "Réduction annoncée conforme": "Aangekondigde korting conform",
    "Le prix de référence de %(ref)s € correspond au prix le plus bas pratiqué par le "
    "marchand durant les 30 jours précédents, comme l'exige le Code de droit économique.": "De referentieprijs van %(ref)s € is de laagste prijs die de handelaar in de "
    "voorgaande 30 dagen hanteerde, zoals het Wetboek van economisch recht vereist.",
    "Disponibilité, qualité du service, conditions réelles…": "Beschikbaarheid, kwaliteit van de service, werkelijke voorwaarden…",
    # -- Publication ------------------------------------------------------
    "Publier un deal": "Een deal plaatsen",
    "Chaque publication passe par la modération avant d'apparaître dans le flux.": "Elke inzending wordt gemodereerd voordat ze in de feed verschijnt.",
    "Règle belge sur l'annonce de réduction": "Belgische regel voor kortingsaankondigingen",
    "Le prix de référence doit être le prix le plus bas pratiqué par le marchand durant "
    "les 30 jours précédents. Un prix barré gonflé entraîne le refus.": "De referentieprijs moet de laagste prijs zijn die de handelaar in de voorgaande "
    "30 dagen hanteerde. Een opgeblazen doorstreepte prijs leidt tot weigering.",
    "Soumettre à la modération": "Ter moderatie indienen",
    "Merci. Votre offre part en modération et sera visible sous deux heures environ.": "Bedankt. Uw aanbieding gaat naar de moderatie en is binnen ongeveer twee uur zichtbaar.",
    "Ex. : machine à café": "Bv.: koffiemachine",
    "Le lien doit être en HTTPS.": "De link moet HTTPS gebruiken.",
    "Évitez les titres entièrement en majuscules.": "Vermijd titels volledig in hoofdletters.",
    "Un seul point d'exclamation au maximum.": "Maximaal één uitroepteken.",
    "Un marchand hors Belgique impose de cocher « offre transfrontalière ».": "Bij een handelaar buiten België moet u « grensoverschrijdende aanbieding » aanvinken.",
    "Le prix de référence doit dépasser le prix affiché. La loi belge impose d'y indiquer "
    "le prix le plus bas des 30 derniers jours.": "De referentieprijs moet hoger zijn dan de getoonde prijs. De Belgische wet vereist "
    "de laagste prijs van de voorbije 30 dagen.",
    "Le prix de référence doit dépasser le prix affiché, sinon la réduction annoncée est "
    "trompeuse.": "De referentieprijs moet hoger zijn dan de getoonde prijs, anders is de aangekondigde "
    "korting misleidend.",
    "La fin de l'offre doit suivre son début.": "Het einde van de aanbieding moet na het begin liggen.",
    "Le prix ne peut pas être négatif.": "De prijs mag niet negatief zijn.",
    "Prix invraisemblable pour un bon plan.": "Onwaarschijnlijke prijs voor een koopje.",
    "Commentaire trop court.": "Reactie te kort.",
    "Commentaire refusé : %(e)s": "Reactie geweigerd: %(e)s",
    "Mot-clé": "Trefwoord",
    "Mot-clé trop court.": "Trefwoord te kort.",
    "Prix maximum": "Maximumprijs",
    # -- Comptes ----------------------------------------------------------
    "Mon compte": "Mijn account",
    "Se connecter": "Aanmelden",
    "Pas encore de compte ?": "Nog geen account?",
    "Adresse e-mail": "E-mailadres",
    "Mot de passe": "Wachtwoord",
    "Adresse e-mail ou mot de passe incorrect.": "E-mailadres of wachtwoord onjuist.",
    "Douze caractères minimum, mêlant plusieurs types de caractères.": "Minstens twaalf tekens, met verschillende soorten tekens.",
    "Créer mon compte": "Mijn account aanmaken",
    "Bienvenue sur DealTrack, %(name)s.": "Welkom bij DealTrack, %(name)s.",
    "J'accepte les conditions d'utilisation et la politique de confidentialité": "Ik ga akkoord met de gebruiksvoorwaarden en het privacybeleid",
    "L'acceptation des conditions est obligatoire.": "Aanvaarding van de voorwaarden is verplicht.",
    "Je souhaite recevoir la sélection hebdomadaire des meilleurs deals": "Ik wil de wekelijkse selectie van de beste deals ontvangen",
    "Facultatif, révocable à tout moment. Consentement distinct des CGU.": "Optioneel, op elk moment intrekbaar. Losstaande toestemming van de voorwaarden.",
    "Un compte existe déjà avec cette adresse.": "Er bestaat al een account met dit adres.",
    "Ce pseudonyme est déjà pris.": "Deze gebruikersnaam is al in gebruik.",
    "Vos données sont traitées conformément au RGPD. Vous pouvez les exporter ou fermer "
    "votre compte à tout moment.": "Uw gegevens worden verwerkt conform de AVG. U kunt ze exporteren of uw account op "
    "elk moment sluiten.",
    "Mes deals": "Mijn deals",
    "Mes factures": "Mijn facturen",
    "Titre": "Titel",
    "Statut": "Status",
    "Soumis le": "Ingediend op",
    "Référence": "Referentie",
    "Montant": "Bedrag",
    "Date": "Datum",
    "dont TVA": "waarvan btw",
    "Aucun deal publié pour l'instant.": "Nog geen deals geplaatst.",
    "Aucune facture.": "Geen facturen.",
    "Mes données personnelles": "Mijn persoonsgegevens",
    "Le règlement européen vous donne un droit d'accès, de portabilité et d'effacement "
    "sur vos données.": "De Europese verordening geeft u recht op inzage, overdraagbaarheid en wissing van "
    "uw gegevens.",
    "Exporter mes données (JSON)": "Mijn gegevens exporteren (JSON)",
    "Exporter mes données": "Mijn gegevens exporteren",
    "Fermer mon compte": "Mijn account sluiten",
    # -- Fermeture de compte ----------------------------------------------
    "Vos factures seront conservées": "Uw facturen worden bewaard",
    "Le droit comptable belge impose de conserver les pièces justificatives sept ans. "
    "Votre compte sera immédiatement désactivé et vos données personnelles anonymisées à "
    "l'expiration de ce délai. Vos factures resteront rattachées à un identifiant non "
    "nominatif.": "Het Belgische boekhoudrecht verplicht bewijsstukken zeven jaar te bewaren. Uw account "
    "wordt onmiddellijk gedeactiveerd en uw persoonsgegevens worden na die termijn "
    "geanonimiseerd. Uw facturen blijven gekoppeld aan een niet-herleidbare identificatie.",
    "Aucune facture n'est rattachée à ce compte : vos données personnelles seront "
    "effacées immédiatement.": "Aan dit account is geen factuur gekoppeld: uw persoonsgegevens worden onmiddellijk "
    "gewist.",
    "Vos deals et commentaires publiés restent en ligne, réattribués à un pseudonyme "
    "anonyme, afin de ne pas trouer les discussions de la communauté.": "Uw geplaatste deals en reacties blijven online onder een anonieme gebruikersnaam, "
    "zodat de discussies van de community intact blijven.",
    "Tapez « %(name)s » pour confirmer": "Typ « %(name)s » om te bevestigen",
    "Motif (facultatif)": "Reden (optioneel)",
    "Fermer définitivement mon compte": "Mijn account definitief sluiten",
    "La confirmation ne correspond pas à votre pseudonyme.": "De bevestiging komt niet overeen met uw gebruikersnaam.",
    "Votre compte est fermé et vos données personnelles ont été effacées.": "Uw account is gesloten en uw persoonsgegevens zijn gewist.",
    "Votre compte est fermé. Vos factures sont conservées le temps du délai légal, puis "
    "vos données seront anonymisées.": "Uw account is gesloten. Uw facturen worden gedurende de wettelijke termijn bewaard, "
    "daarna worden uw gegevens geanonimiseerd.",
    # -- Verrouillage et sécurité -----------------------------------------
    "Compte temporairement bloqué": "Account tijdelijk geblokkeerd",
    "Trop de tentatives": "Te veel pogingen",
    "Après cinq échecs de connexion, l'accès est suspendu quinze minutes depuis cette "
    "adresse. Cette mesure protège votre compte contre les tentatives automatisées.": "Na vijf mislukte aanmeldpogingen wordt de toegang vanaf dit adres vijftien minuten "
    "opgeschort. Deze maatregel beschermt uw account tegen geautomatiseerde pogingen.",
    "Si vous avez oublié votre mot de passe, attendez la fin du délai puis utilisez la "
    "réinitialisation.": "Bent u uw wachtwoord vergeten, wacht dan tot de termijn verstreken is en gebruik de "
    "herstelprocedure.",
    "Session expirée": "Sessie verlopen",
    "Le jeton de sécurité de votre formulaire n'est plus valide. Cela arrive après une "
    "longue inactivité, ou si la requête ne provient pas de DealTrack. Revenez en arrière "
    "et renvoyez le formulaire.": "Het beveiligingstoken van uw formulier is niet meer geldig. Dat gebeurt na lange "
    "inactiviteit, of als het verzoek niet van DealTrack komt. Ga terug en verstuur het "
    "formulier opnieuw.",
    "Cette page n'est pas accessible.": "Deze pagina is niet toegankelijk.",
    "Retour aux deals": "Terug naar de deals",
    # -- Politique de mot de passe ----------------------------------------
    "Au moins 12 caractères, combinant minuscules, majuscules, chiffres ou symboles, "
    "sans suite de touches.": "Minstens 12 tekens, met kleine letters, hoofdletters, cijfers of symbolen, zonder "
    "toetsenbordreeksen.",
    "Le mot de passe contient une suite de touches trop évidente (« %(s)s »).": "Het wachtwoord bevat een te voorspelbare toetsenbordreeks (« %(s)s »).",
    "Le texte contient un caractère de contrôle interdit.": "De tekst bevat een verboden controleteken.",
    "Format attendu : BE suivi de 10 chiffres, par exemple BE0123456749.": "Verwacht formaat: BE gevolgd door 10 cijfers, bijvoorbeeld BE0123456749.",
    "La clé de contrôle du numéro de TVA est incorrecte.": "Het controlegetal van het btw-nummer is onjuist.",
    "Une adresse e-mail est obligatoire.": "Een e-mailadres is verplicht.",
    # -- Paiement ----------------------------------------------------------
    "Abonnement Club": "Clubabonnement",
    "Souscrire": "Abonneren",
    "Souscrire ": "Abonneren ",
    "TVA %(vat)s %% comprise · valable %(days)s jours": "Inclusief %(vat)s %% btw · %(days)s dagen geldig",
    "Aucune donnée bancaire ne transite par DealTrack": "Er gaan geen bankgegevens via DealTrack",
    "Votre navigateur communique vos coordonnées directement au prestataire de paiement, "
    "qui renvoie un jeton à usage unique. Nos serveurs ne voient jamais votre numéro de "
    "carte.": "Uw browser stuurt uw gegevens rechtstreeks naar de betaaldienstverlener, die een "
    "eenmalig token teruggeeft. Onze servers zien uw kaartnummer nooit.",
    "Jeton de paiement": "Betaaltoken",
    "Environnement de démonstration : « tok_demo_visa » aboutit, « tok_demo_fail » est "
    "refusé.": "Demo-omgeving: « tok_demo_visa » slaagt, « tok_demo_fail » wordt geweigerd.",
    "Payer %(amount)s €": "%(amount)s € betalen",
    "Droit de rétractation : quatorze jours, sauf renonciation expresse à l'exécution "
    "immédiate du service (art. VI.53 CDE).": "Herroepingsrecht: veertien dagen, tenzij u uitdrukkelijk afziet van onmiddellijke "
    "uitvoering van de dienst (art. VI.53 WER).",
    "Le paiement a été refusé. Aucun montant n'a été débité.": "De betaling is geweigerd. Er is geen bedrag afgeschreven.",
    "Abonnement actif jusqu'au %(date)s. Facture %(ref)s.": "Abonnement actief tot %(date)s. Factuur %(ref)s.",
    "Cette formule n'est plus proposée.": "Deze formule wordt niet meer aangeboden.",
    "Ce compte est désinscrit.": "Dit account is opgezegd.",
    # -- Modèles : libellés de champs --------------------------------------
    "adresse e-mail": "e-mailadres",
    "pseudonyme": "gebruikersnaam",
    "rôle": "rol",
    "langue préférée": "voorkeurstaal",
    "région": "regio",
    "régions": "regio's",
    "actif": "actief",
    "utilisateur": "gebruiker",
    "utilisateurs": "gebruikers",
    "Membre": "Lid",
    "Modérateur": "Moderator",
    "Administrateur": "Beheerder",
    "catégorie": "categorie",
    "catégories": "categorieën",
    "marchand": "handelaar",
    "marchands": "handelaars",
    "enseigne": "winkelketen",
    "pays": "land",
    "Belgique": "België",
    "Pays-Bas": "Nederland",
    "France": "Frankrijk",
    "Allemagne": "Duitsland",
    "Luxembourg": "Luxemburg",
    "titre": "titel",
    "description": "beschrijving",
    "prix": "prijs",
    "prix de référence": "referentieprijs",
    "devise": "munteenheid",
    "frais de livraison": "leveringskosten",
    "statut": "status",
    "auteur": "auteur",
    "deal": "deal",
    "deals": "deals",
    "vote": "stem",
    "votes": "stemmen",
    "commentaire": "reactie",
    "température": "temperatuur",
    "Brouillon": "Concept",
    "En attente de modération": "In afwachting van moderatie",
    "Publié": "Gepubliceerd",
    "Refusé": "Geweigerd",
    "alerte": "melding",
    "alertes": "meldingen",
    "paiement": "betaling",
    "paiements": "betalingen",
    "abonnement": "abonnement",
    "abonnements": "abonnementen",
    "formule": "formule",
    "formules": "formules",
    "En attente": "In afwachting",
    "Réussi": "Geslaagd",
    "Échoué": "Mislukt",
    "Remboursé": "Terugbetaald",
    "Active": "Actief",
    "Expirée": "Verlopen",
    "Résiliée": "Opgezegd",
    "signalement": "melding van misbruik",
    "signalements": "meldingen van misbruik",
    "Rupture de stock": "Niet meer op voorraad",
    "Prix incorrect": "Onjuiste prijs",
    "Réduction trompeuse": "Misleidende korting",
    "Spam ou compte promotionnel": "Spam of promotieaccount",
    "Ouvert": "Open",
    "Traité": "Behandeld",
    "Écarté": "Afgewezen",
}

DE = {
    # -- Navigation et structure -----------------------------------------
    "Français": "Französisch",
    "Nederlands": "Niederländisch",
    "Deutsch": "Deutsch",
    "DealTrack.be": "DealTrack.be",
    "La plateforme communautaire des bons plans en Belgique.": "Die Community-Plattform für Schnäppchen in Belgien.",
    "Rechercher un bon plan": "Ein Schnäppchen suchen",
    "Recherche…": "Suche…",
    "Catégories": "Kategorien",
    "Tous les deals": "Alle Deals",
    "Commerçants locaux": "Lokale Händler",
    "Club": "Club",
    "Connexion": "Anmelden",
    "Inscription": "Registrieren",
    "Déconnexion": "Abmelden",
    "Modération": "Moderation",
    "Publier": "Veröffentlichen",
    "Accueil": "Startseite",
    "Découvrir": "Entdecken",
    "Participer": "Mitmachen",
    "Vos données": "Ihre Daten",
    "Région": "Region",
    "Filtrer par région": "Nach Region filtern",
    "Toute la Belgique": "Ganz Belgien",
    "Tendance": "Beliebt",
    "Nouveaux": "Neu",
    "Prix croissant": "Preis aufsteigend",
    "Pagination": "Seitennavigation",
    "Précédent": "Zurück",
    "Suivant": "Weiter",
    "Page %(n)s sur %(total)s": "Seite %(n)s von %(total)s",
    "Bruxelles, Belgique": "Brüssel, Belgien",
    "Prix TVA belge comprise.": "Preise inklusive belgischer MwSt.",
    "Plateforme communautaire des bons plans en Belgique, disponible en français, "
    "néerlandais et allemand.": "Community-Plattform für Schnäppchen in Belgien, verfügbar auf Französisch, "
    "Niederländisch und Deutsch.",
    "Politique de confidentialité": "Datenschutzerklärung",
    # -- Flux de deals ----------------------------------------------------
    "Les meilleurs bons plans en Belgique": "Die besten Schnäppchen Belgiens",
    "Refroidir": "Abkühlen",
    "Réchauffer": "Aufwärmen",
    "Expiré": "Abgelaufen",
    "Publié il y a %(when)s": "Vor %(when)s veröffentlicht",
    "Offre vérifiée": "Geprüftes Angebot",
    "Commerçant local": "Lokaler Händler",
    "Transfrontalier": "Grenzüberschreitend",
    # Repli d'une offre non traduite, cf. la section néerlandaise.
    "Offre rédigée en %(lang)s": "Angebot verfasst auf %(lang)s",
    "français": "Französisch",
    "néerlandais": "Niederländisch",
    "allemand": "Deutsch",
    "Livraison gratuite": "Kostenlose Lieferung",
    "Livraison": "Lieferung",
    "Dispo. chez": "Verfügbar bei",
    "Partagé par": "Geteilt von",
    "commentaires": "Kommentare",
    "Voir le deal": "Zum Angebot",
    "Aucun deal ne correspond à ces critères.": "Kein Deal entspricht diesen Kriterien.",
    "Les plus hot": "Am beliebtesten",
    "Créer une alerte": "Benachrichtigung einrichten",
    "Recevez un e-mail dès qu'un deal correspond à vos critères.": "Erhalten Sie eine E-Mail, sobald ein Deal Ihren Kriterien entspricht.",
    "Gérer mes alertes": "Meine Benachrichtigungen verwalten",
    "Créer un compte": "Konto erstellen",
    "À propos de ce deal": "Über diesen Deal",
    "Membre depuis": "Mitglied seit",
    "Achat confirmé": "Kauf bestätigt",
    "Aucun commentaire pour l'instant.": "Noch keine Kommentare.",
    "Ajouter un commentaire": "Kommentar hinzufügen",
    "Publier le commentaire": "Kommentar veröffentlichen",
    "Connectez-vous pour commenter.": "Melden Sie sich an, um zu kommentieren.",
    "Réduction annoncée conforme": "Angekündigte Ermäßigung konform",
    "Le prix de référence de %(ref)s € correspond au prix le plus bas pratiqué par le "
    "marchand durant les 30 jours précédents, comme l'exige le Code de droit économique.": "Der Referenzpreis von %(ref)s € entspricht dem niedrigsten Preis, den der Händler "
    "in den vorangegangenen 30 Tagen verlangt hat, wie es das Wirtschaftsgesetzbuch "
    "vorschreibt.",
    "Disponibilité, qualité du service, conditions réelles…": "Verfügbarkeit, Servicequalität, tatsächliche Bedingungen…",
    "Commentaire publié.": "Kommentar veröffentlicht.",
    # -- Publication ------------------------------------------------------
    "Publier un deal": "Einen Deal veröffentlichen",
    "Chaque publication passe par la modération avant d'apparaître dans le flux.": "Jeder Beitrag wird moderiert, bevor er im Feed erscheint.",
    "Règle belge sur l'annonce de réduction": "Belgische Regel zur Ermäßigungsankündigung",
    "Le prix de référence doit être le prix le plus bas pratiqué par le marchand durant "
    "les 30 jours précédents. Un prix barré gonflé entraîne le refus.": "Der Referenzpreis muss der niedrigste Preis sein, den der Händler in den "
    "vorangegangenen 30 Tagen verlangt hat. Ein überhöhter Streichpreis führt zur "
    "Ablehnung.",
    "Soumettre à la modération": "Zur Moderation einreichen",
    "Merci. Votre offre part en modération et sera visible sous deux heures environ.": "Danke. Ihr Angebot geht in die Moderation und ist in etwa zwei Stunden sichtbar.",
    "Ex. : machine à café": "Z. B.: Kaffeemaschine",
    "Le lien doit être en HTTPS.": "Der Link muss HTTPS verwenden.",
    "Évitez les titres entièrement en majuscules.": "Vermeiden Sie Titel in Großbuchstaben.",
    "Un seul point d'exclamation au maximum.": "Höchstens ein Ausrufezeichen.",
    "Un marchand hors Belgique impose de cocher « offre transfrontalière ».": "Bei einem Händler außerhalb Belgiens muss « grenzüberschreitendes Angebot » "
    "angekreuzt werden.",
    "Le prix de référence doit dépasser le prix affiché. La loi belge impose d'y indiquer "
    "le prix le plus bas des 30 derniers jours.": "Der Referenzpreis muss über dem angezeigten Preis liegen. Das belgische Recht "
    "verlangt den niedrigsten Preis der letzten 30 Tage.",
    "Le prix de référence doit dépasser le prix affiché, sinon la réduction annoncée est "
    "trompeuse.": "Der Referenzpreis muss über dem angezeigten Preis liegen, sonst ist die "
    "angekündigte Ermäßigung irreführend.",
    "La fin de l'offre doit suivre son début.": "Das Ende des Angebots muss nach seinem Beginn liegen.",
    "Le prix ne peut pas être négatif.": "Der Preis darf nicht negativ sein.",
    "Prix invraisemblable pour un bon plan.": "Unglaubwürdiger Preis für ein Schnäppchen.",
    "Commentaire trop court.": "Kommentar zu kurz.",
    "Commentaire refusé : %(e)s": "Kommentar abgelehnt: %(e)s",
    "Mot-clé": "Stichwort",
    "Mot-clé trop court.": "Stichwort zu kurz.",
    "Prix maximum": "Höchstpreis",
    # -- Comptes ----------------------------------------------------------
    "Mon compte": "Mein Konto",
    "Se connecter": "Anmelden",
    "Pas encore de compte ?": "Noch kein Konto?",
    "Adresse e-mail": "E-Mail-Adresse",
    "Mot de passe": "Passwort",
    "Adresse e-mail ou mot de passe incorrect.": "E-Mail-Adresse oder Passwort falsch.",
    "Douze caractères minimum, mêlant plusieurs types de caractères.": "Mindestens zwölf Zeichen, mit verschiedenen Zeichenarten.",
    "Créer mon compte": "Mein Konto erstellen",
    "Bienvenue sur DealTrack, %(name)s.": "Willkommen bei DealTrack, %(name)s.",
    "J'accepte les conditions d'utilisation et la politique de confidentialité": "Ich akzeptiere die Nutzungsbedingungen und die Datenschutzerklärung",
    "L'acceptation des conditions est obligatoire.": "Die Zustimmung zu den Bedingungen ist erforderlich.",
    "Je souhaite recevoir la sélection hebdomadaire des meilleurs deals": "Ich möchte die wöchentliche Auswahl der besten Deals erhalten",
    "Facultatif, révocable à tout moment. Consentement distinct des CGU.": "Optional, jederzeit widerrufbar. Von den Nutzungsbedingungen getrennte Einwilligung.",
    "Un compte existe déjà avec cette adresse.": "Mit dieser Adresse besteht bereits ein Konto.",
    "Ce pseudonyme est déjà pris.": "Dieser Benutzername ist bereits vergeben.",
    "Vos données sont traitées conformément au RGPD. Vous pouvez les exporter ou fermer "
    "votre compte à tout moment.": "Ihre Daten werden gemäß der DSGVO verarbeitet. Sie können sie jederzeit "
    "exportieren oder Ihr Konto schließen.",
    "Mes deals": "Meine Deals",
    "Mes factures": "Meine Rechnungen",
    "Titre": "Titel",
    "Statut": "Status",
    "Soumis le": "Eingereicht am",
    "Référence": "Referenz",
    "Montant": "Betrag",
    "Date": "Datum",
    "dont TVA": "davon MwSt.",
    "Aucun deal publié pour l'instant.": "Noch keine Deals veröffentlicht.",
    "Aucune facture.": "Keine Rechnungen.",
    "Mes données personnelles": "Meine personenbezogenen Daten",
    "Le règlement européen vous donne un droit d'accès, de portabilité et d'effacement "
    "sur vos données.": "Die europäische Verordnung gibt Ihnen ein Recht auf Auskunft, Übertragbarkeit und "
    "Löschung Ihrer Daten.",
    "Exporter mes données (JSON)": "Meine Daten exportieren (JSON)",
    "Exporter mes données": "Meine Daten exportieren",
    "Fermer mon compte": "Mein Konto schließen",
    # -- Fermeture de compte ----------------------------------------------
    "Vos factures seront conservées": "Ihre Rechnungen werden aufbewahrt",
    "Le droit comptable belge impose de conserver les pièces justificatives sept ans. "
    "Votre compte sera immédiatement désactivé et vos données personnelles anonymisées à "
    "l'expiration de ce délai. Vos factures resteront rattachées à un identifiant non "
    "nominatif.": "Das belgische Buchhaltungsrecht verlangt die Aufbewahrung von Belegen für sieben "
    "Jahre. Ihr Konto wird sofort deaktiviert und Ihre personenbezogenen Daten nach "
    "Ablauf dieser Frist anonymisiert. Ihre Rechnungen bleiben mit einer nicht "
    "namentlichen Kennung verknüpft.",
    "Aucune facture n'est rattachée à ce compte : vos données personnelles seront "
    "effacées immédiatement.": "Diesem Konto ist keine Rechnung zugeordnet: Ihre personenbezogenen Daten werden "
    "sofort gelöscht.",
    "Vos deals et commentaires publiés restent en ligne, réattribués à un pseudonyme "
    "anonyme, afin de ne pas trouer les discussions de la communauté.": "Ihre veröffentlichten Deals und Kommentare bleiben unter einem anonymen "
    "Benutzernamen online, damit die Diskussionen der Community lückenlos bleiben.",
    "Tapez « %(name)s » pour confirmer": "Geben Sie « %(name)s » ein, um zu bestätigen",
    "Motif (facultatif)": "Grund (optional)",
    "Fermer définitivement mon compte": "Mein Konto endgültig schließen",
    "La confirmation ne correspond pas à votre pseudonyme.": "Die Bestätigung stimmt nicht mit Ihrem Benutzernamen überein.",
    "Votre compte est fermé et vos données personnelles ont été effacées.": "Ihr Konto ist geschlossen und Ihre personenbezogenen Daten wurden gelöscht.",
    "Votre compte est fermé. Vos factures sont conservées le temps du délai légal, puis "
    "vos données seront anonymisées.": "Ihr Konto ist geschlossen. Ihre Rechnungen werden für die gesetzliche Frist "
    "aufbewahrt, danach werden Ihre Daten anonymisiert.",
    # -- Verrouillage et sécurité -----------------------------------------
    "Compte temporairement bloqué": "Konto vorübergehend gesperrt",
    "Trop de tentatives": "Zu viele Versuche",
    "Après cinq échecs de connexion, l'accès est suspendu quinze minutes depuis cette "
    "adresse. Cette mesure protège votre compte contre les tentatives automatisées.": "Nach fünf fehlgeschlagenen Anmeldeversuchen wird der Zugang von dieser Adresse für "
    "fünfzehn Minuten gesperrt. Diese Maßnahme schützt Ihr Konto vor automatisierten "
    "Versuchen.",
    "Si vous avez oublié votre mot de passe, attendez la fin du délai puis utilisez la "
    "réinitialisation.": "Haben Sie Ihr Passwort vergessen, warten Sie das Ende der Frist ab und nutzen Sie "
    "die Zurücksetzung.",
    "Session expirée": "Sitzung abgelaufen",
    "Le jeton de sécurité de votre formulaire n'est plus valide. Cela arrive après une "
    "longue inactivité, ou si la requête ne provient pas de DealTrack. Revenez en arrière "
    "et renvoyez le formulaire.": "Das Sicherheitstoken Ihres Formulars ist nicht mehr gültig. Das passiert nach "
    "längerer Inaktivität oder wenn die Anfrage nicht von DealTrack stammt. Gehen Sie "
    "zurück und senden Sie das Formular erneut.",
    "Cette page n'est pas accessible.": "Diese Seite ist nicht zugänglich.",
    "Retour aux deals": "Zurück zu den Deals",
    # -- Politique de mot de passe ----------------------------------------
    "Au moins 12 caractères, combinant minuscules, majuscules, chiffres ou symboles, "
    "sans suite de touches.": "Mindestens 12 Zeichen, mit Klein- und Großbuchstaben, Ziffern oder Symbolen, ohne "
    "Tastaturfolgen.",
    "Le mot de passe contient une suite de touches trop évidente (« %(s)s »).": "Das Passwort enthält eine zu offensichtliche Tastaturfolge (« %(s)s »).",
    "Le texte contient un caractère de contrôle interdit.": "Der Text enthält ein unzulässiges Steuerzeichen.",
    "Format attendu : BE suivi de 10 chiffres, par exemple BE0123456749.": "Erwartetes Format: BE gefolgt von 10 Ziffern, zum Beispiel BE0123456749.",
    "La clé de contrôle du numéro de TVA est incorrecte.": "Die Prüfziffer der MwSt.-Nummer ist falsch.",
    "Une adresse e-mail est obligatoire.": "Eine E-Mail-Adresse ist erforderlich.",
    # -- Paiement ----------------------------------------------------------
    "Abonnement Club": "Club-Abonnement",
    "Souscrire": "Abonnieren",
    "TVA %(vat)s %% comprise · valable %(days)s jours": "Inklusive %(vat)s %% MwSt. · %(days)s Tage gültig",
    "Aucune donnée bancaire ne transite par DealTrack": "Keine Bankdaten laufen über DealTrack",
    "Votre navigateur communique vos coordonnées directement au prestataire de paiement, "
    "qui renvoie un jeton à usage unique. Nos serveurs ne voient jamais votre numéro de "
    "carte.": "Ihr Browser übermittelt Ihre Daten direkt an den Zahlungsdienstleister, der ein "
    "Einmal-Token zurückgibt. Unsere Server sehen Ihre Kartennummer nie.",
    "Jeton de paiement": "Zahlungstoken",
    "Environnement de démonstration : « tok_demo_visa » aboutit, « tok_demo_fail » est "
    "refusé.": "Demo-Umgebung: « tok_demo_visa » gelingt, « tok_demo_fail » wird abgelehnt.",
    "Payer %(amount)s €": "%(amount)s € bezahlen",
    "Droit de rétractation : quatorze jours, sauf renonciation expresse à l'exécution "
    "immédiate du service (art. VI.53 CDE).": "Widerrufsrecht: vierzehn Tage, außer bei ausdrücklichem Verzicht auf die sofortige "
    "Ausführung der Dienstleistung (Art. VI.53 WGB).",
    "Le paiement a été refusé. Aucun montant n'a été débité.": "Die Zahlung wurde abgelehnt. Es wurde kein Betrag abgebucht.",
    "Abonnement actif jusqu'au %(date)s. Facture %(ref)s.": "Abonnement aktiv bis %(date)s. Rechnung %(ref)s.",
    "Cette formule n'est plus proposée.": "Diese Formel wird nicht mehr angeboten.",
    "Ce compte est désinscrit.": "Dieses Konto ist abgemeldet.",
    # -- Modèles : libellés de champs --------------------------------------
    "adresse e-mail": "E-Mail-Adresse",
    "pseudonyme": "Benutzername",
    "rôle": "Rolle",
    "langue préférée": "bevorzugte Sprache",
    "région": "Region",
    "régions": "Regionen",
    "actif": "aktiv",
    "utilisateur": "Benutzer",
    "utilisateurs": "Benutzer",
    "Membre": "Mitglied",
    "Modérateur": "Moderator",
    "Administrateur": "Administrator",
    "catégorie": "Kategorie",
    "catégories": "Kategorien",
    "marchand": "Händler",
    "marchands": "Händler",
    "enseigne": "Handelskette",
    "pays": "Land",
    "Belgique": "Belgien",
    "Pays-Bas": "Niederlande",
    "France": "Frankreich",
    "Allemagne": "Deutschland",
    "Luxembourg": "Luxemburg",
    "titre": "Titel",
    "description": "Beschreibung",
    "prix": "Preis",
    "prix de référence": "Referenzpreis",
    "devise": "Währung",
    "frais de livraison": "Lieferkosten",
    "statut": "Status",
    "auteur": "Autor",
    "deal": "Deal",
    "deals": "Deals",
    "vote": "Stimme",
    "votes": "Stimmen",
    "commentaire": "Kommentar",
    "température": "Temperatur",
    "Brouillon": "Entwurf",
    "En attente de modération": "Wartet auf Moderation",
    "Publié": "Veröffentlicht",
    "Refusé": "Abgelehnt",
    "alerte": "Benachrichtigung",
    "alertes": "Benachrichtigungen",
    "paiement": "Zahlung",
    "paiements": "Zahlungen",
    "abonnement": "Abonnement",
    "abonnements": "Abonnements",
    "formule": "Formel",
    "formules": "Formeln",
    "En attente": "Ausstehend",
    "Réussi": "Erfolgreich",
    "Échoué": "Fehlgeschlagen",
    "Remboursé": "Erstattet",
    "Active": "Aktiv",
    "Expirée": "Abgelaufen",
    "Résiliée": "Gekündigt",
    "signalement": "Meldung",
    "signalements": "Meldungen",
    "Rupture de stock": "Nicht mehr vorrätig",
    "Prix incorrect": "Falscher Preis",
    "Réduction trompeuse": "Irreführende Ermäßigung",
    "Spam ou compte promotionnel": "Spam oder Werbekonto",
    "Ouvert": "Offen",
    "Traité": "Bearbeitet",
    "Écarté": "Verworfen",
}

CATALOGUES = {"nl": NL, "de": DE}
