"""Diagrammes d'états-transitions — deal, paiement, compte membre."""

from svg import Canvas, clip_rect, mid, text_width

ST = {}


def state(c, key, x, y, w, h, name, inner=(), fill="#ffffff"):
    ST[key] = (x, y, w, h)
    c.add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#1d2433" stroke-width="1.4"/>'
    )
    if inner:
        c.text(x + w / 2, y + 21, name, "t13 b")
        c.add(
            f'<line x1="{x}" y1="{y + 30}" x2="{x + w}" y2="{y + 30}" stroke="#1d2433" stroke-width="1"/>'
        )
        for i, row in enumerate(inner):
            c.text(x + 10, y + 48 + i * 16, row, "t11", "start")
    else:
        c.text(x + w / 2, y + h / 2 + 5, name, "t13 b")


def composite(c, key, x, y, w, h, name):
    ST[key] = (x, y, w, h)
    c.add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#f7f8fa" stroke="#1d2433" stroke-width="1.4"/>'
    )
    c.text(x + 16, y + 22, name, "t13 b", "start")


def initial(c, key, x, y):
    ST[key] = (x - 9, y - 9, 18, 18)
    c.add(f'<circle cx="{x}" cy="{y}" r="9" fill="#1d2433"/>')


def label(c, x, y, rows, anchor="middle"):
    w = max(text_width(r, 11) for r in rows) + 10
    h = len(rows) * 14 + 6
    lx = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
    c.add(
        f'<rect x="{lx:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h}" fill="#ffffff" opacity="0.92"/>'
    )
    tx = x if anchor == "middle" else (lx + 5 if anchor == "start" else x - 5)
    for i, r in enumerate(rows):
        c.text(tx, y - h / 2 + 14 + i * 14, r, "t11", anchor)


def trans(c, a, b, rows=(), pa=None, pb=None, via=None, at=None, anchor="middle", dash=False):
    ca = ST[a]
    cb = ST[b]
    cen_a = (ca[0] + ca[2] / 2, ca[1] + ca[3] / 2)
    cen_b = (cb[0] + cb[2] / 2, cb[1] + cb[3] / 2)
    first = via[0] if via else (pb or cen_b)
    last = via[-1] if via else (pa or cen_a)
    p1 = pa or clip_rect(*ca, *first)
    p2 = pb or clip_rect(*cb, *last)
    pts = [p1] + (via or []) + [p2]
    c.path(pts, "ln dash" if dash else "ln", marker_end="filled")
    if rows:
        if at is None:
            i = len(pts) // 2
            at = mid(pts[i - 1], pts[i]) if len(pts) % 2 == 0 else pts[i]
        label(c, at[0], at[1], rows, anchor)


def note(c, x, y, w, rows):
    h = len(rows) * 15 + 14
    c.add(
        f'<path d="M{x},{y} L{x + w - 14},{y} L{x + w},{y + 14} L{x + w},{y + h} L{x},{y + h} Z" fill="#fffbe6" stroke="#8a7a3a" stroke-width="1"/>'
    )
    c.add(
        f'<path d="M{x + w - 14},{y} L{x + w - 14},{y + 14} L{x + w},{y + 14}" fill="none" stroke="#8a7a3a" stroke-width="1"/>'
    )
    for i, r in enumerate(rows):
        c.text(x + 10, y + 19 + i * 15, r, "t11", "start")


# ============================================================ 1. Deal
c = Canvas(1320, 720, "DealTrack.be — états d'un deal")
c.text(
    20,
    30,
    "Diagramme d'états-transitions : cycle de vie d'un deal (Deal.status et Deal.deleted_at)",
    "t13 b",
    "start",
)
composite(
    c, "base", 140, 60, 880, 540, "Présent dans le flux ou l'historique  [deleted_at vide]"
)
initial(c, "i", 70, 205)
state(
    c,
    "attente",
    190,
    160,
    250,
    90,
    "En attente de modération",
    [
        "entry / premier relevé de prix (PricePoint)",
        "statut imposé par le serveur",
    ],
)
state(
    c,
    "publie",
    620,
    120,
    340,
    130,
    "Publié",
    [
        "entry / published_at, alertes déclenchées",
        "          (VIP tout de suite, autres après 2 h)",
        "voter / recalcul de la température",
        "prix modifié / nouveau PricePoint",
    ],
)
state(c, "refuse", 190, 430, 250, 60, "Refusé")
state(c, "expire", 620, 430, 340, 60, "Expiré")
state(
    c,
    "supprime",
    1090,
    290,
    200,
    100,
    "Supprimé (logique)",
    ["entry / deleted_at = maintenant", "invisible, ligne conservée"],
)

trans(c, "i", "attente", ["soumettre (membre,", "formulaire ou API)"], at=(120, 270))
trans(
    c,
    "attente",
    "publie",
    ["publier [modérateur]", "/ ModerationDecision + AuditLog"],
    pa=(440, 195),
    pb=(620, 195),
    at=(530, 170),
)
trans(
    c,
    "attente",
    "refuse",
    ["refuser [modérateur, motif obligatoire]", "/ ModerationDecision + AuditLog"],
    at=(315, 345),
)
trans(
    c,
    "publie",
    "expire",
    ["[ends_at dépassé]", "ou marquer expiré (modérateur)"],
    at=(790, 345),
)
trans(
    c,
    "base",
    "supprime",
    ["supprimer (auteur ou modérateur)", "/ AuditLog"],
    pa=(1020, 540),
    pb=(1190, 390),
    via=[(1190, 540)],
    at=(1105, 515),
)
note(
    c,
    140,
    625,
    880,
    [
        "La valeur « draft » (brouillon) existe dans l'énumération DealStatus mais n'est utilisée par aucun écran : un deal soumis passe directement en attente.",
        "La suppression est logique : votes, commentaires, signalements et décisions de modération restent rattachés au deal.",
    ],
)
open("../03_etats_deal.svg", "w", encoding="utf-8").write(c.svg())

# ============================================================ 2. Paiement
c = Canvas(1240, 500, "DealTrack.be — états d'un paiement")
c.text(
    20,
    30,
    "Diagramme d'états-transitions : paiement d'un abonnement VIP (Payment.status)",
    "t13 b",
    "start",
)
initial(c, "i", 50, 215)
state(
    c,
    "attente",
    150,
    165,
    270,
    100,
    "En attente",
    [
        "entry / ligne Payment créée AVANT",
        "          l'appel à Stripe (référence, TVA)",
        "          puis session Stripe Checkout",
    ],
)
state(
    c,
    "reussi",
    640,
    70,
    290,
    100,
    "Réussi",
    [
        "entry / Subscription créée (durée du plan)",
        "          membre VIP, AuditLog",
        "          carte : marque + 4 derniers chiffres",
    ],
)
state(c, "echoue", 640, 330, 290, 60, "Échoué")
state(c, "rembourse", 1000, 85, 210, 70, "Remboursé")

trans(c, "i", "attente", ["clic « Payer »", "[case de rétractation", "cochée]"], at=(95, 300))
trans(
    c,
    "attente",
    "reussi",
    ["[Stripe confirme payment_status = paid]", "(retour sur le site ou webhook signé)"],
    pa=(420, 190),
    pb=(640, 120),
    at=(522, 156),
)
trans(
    c,
    "attente",
    "echoue",
    ["annulation par le membre", "ou refus de la banque"],
    pa=(420, 240),
    pb=(640, 360),
    at=(530, 320),
)
c.path([(250, 265), (250, 300), (320, 300), (320, 265)], "ln", marker_end="filled")
label(c, 285, 322, ["retour sans paiement", "/ reste en attente"])
trans(c, "reussi", "rembourse", ["rembourser"], dash=True, at=(965, 105))
note(
    c,
    640,
    420,
    570,
    [
        "« Remboursé » est prévu dans le modèle, sans automatisation (traitement manuel).",
        "Un second retour sur le site ne crée pas de second abonnement (idempotence).",
    ],
)
open("../04_etats_paiement.svg", "w", encoding="utf-8").write(c.svg())

# ============================================================ 3. Compte membre
c = Canvas(1240, 560, "DealTrack.be — états d'un compte membre")
c.text(
    20,
    30,
    "Diagramme d'états-transitions : compte membre et désinscription (User.deleted_at, User.anonymised_at)",
    "t13 b",
    "start",
)
initial(c, "i", 50, 190)
composite(c, "actif", 130, 70, 540, 290, "Actif  [is_active, deleted_at vide]")
initial(c, "i2", 175, 165)
state(c, "gratuit", 220, 135, 160, 60, "Gratuit")
state(c, "vip", 470, 135, 160, 60, "VIP")
trans(c, "i2", "gratuit")
trans(c, "gratuit", "vip", ["paiement réussi"], pa=(380, 152), pb=(470, 152), at=(425, 128))
trans(c, "vip", "gratuit", ["[ends_at dépassé]"], pa=(470, 180), pb=(380, 180), at=(425, 208))
c.text(
    150,
    262,
    "Connexion : 5 mots de passe erronés → blocage 15 minutes (django-axes)",
    "t11 muted",
    "start",
)
c.text(
    150,
    280,
    "Mot de passe : Argon2, 12 caractères, trois classes, pas de mot courant",
    "t11 muted",
    "start",
)
c.text(
    150,
    298,
    "Export de mes données (JSON) possible à tout moment (portabilité RGPD)",
    "t11 muted",
    "start",
)

state(
    c,
    "desinscrit",
    870,
    90,
    300,
    100,
    "Désinscrit (soft delete)",
    [
        "entry / deleted_at, is_active = faux, AuditLog",
        "factures et abonnements conservés",
        "(obligation comptable : 7 ans)",
    ],
)
state(
    c,
    "anonyme",
    870,
    330,
    300,
    100,
    "Anonymisé (droit à l'oubli)",
    [
        "entry / e-mail et pseudo écrasés,",
        "          mot de passe inutilisable, AuditLog",
        "la clé primaire subsiste (factures)",
    ],
)
trans(
    c,
    "i",
    "actif",
    ["s'inscrire", "[CGU acceptées,", "mot de passe", "robuste]"],
    pa=(59, 190),
    pb=(130, 190),
    at=(66, 262),
)
trans(
    c,
    "actif",
    "desinscrit",
    ["fermer son compte [confirmation]", "ou désactiver (administrateur)"],
    pa=(670, 140),
    pb=(870, 140),
    at=(770, 112),
)
trans(c, "desinscrit", "anonyme", ["anonymiser", "(administrateur)"], at=(1080, 260))
trans(
    c,
    "actif",
    "anonyme",
    ["supprimer via l'API", "[aucun paiement]"],
    pa=(560, 360),
    pb=(870, 400),
    via=[(560, 400)],
    at=(715, 428),
)
note(
    c,
    130,
    470,
    1040,
    [
        "Une suppression physique est impossible pour un membre qui a payé : Payment.user est protégé (on_delete=PROTECT).",
        "La désinscription coupe donc l'accès sans détruire la ligne : c'est le principe du « soft delete ».",
    ],
)
open("../05_etats_compte.svg", "w", encoding="utf-8").write(c.svg())
print("ok états")
