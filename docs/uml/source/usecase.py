"""Diagramme de cas d'utilisation — DealTrack.be."""

from svg import Canvas, clip_ellipse, mid

W, H = 1400, 1010
c = Canvas(W, H, "DealTrack.be — diagramme de cas d'utilisation")

# Système
SX, SY, SW, SH = 250, 50, 930, 940
c.add(
    f'<rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="6" fill="#f7f8fa" stroke="#1d2433" stroke-width="1.4"/>'
)
c.text(SX + SW / 2, SY + 26, "Système DealTrack.be", "t13 b")

UC = {}


def usecase(key, x, y, rows, rx=150, ry=27, fill="#ffffff"):
    UC[key] = (x, y, rx, ry)
    c.add(
        f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="#1d2433" stroke-width="1.3"/>'
    )
    c.lines(x, y, rows, "t12")


ACT = {}


def actor(key, x, y, rows, system=False):
    if system:
        c.add(
            f'<rect x="{x - 55}" y="{y - 34}" width="110" height="56" rx="4" fill="#fff" stroke="#1d2433" stroke-width="1.3"/>'
        )
        c.text(x, y - 14, "«système»", "t11 muted")
        c.text(x, y + 4, rows[0], "t13 b")
        ACT[key] = (x, y, "box")
        return
    s = 'stroke="#1d2433" stroke-width="1.5" fill="none"'
    c.add(f'<circle cx="{x}" cy="{y - 38}" r="11" {s}/>')
    c.add(
        f'<path d="M{x},{y - 27} L{x},{y + 2} M{x - 18},{y - 16} L{x + 18},{y - 16} M{x},{y + 2} L{x - 14},{y + 26} M{x},{y + 2} L{x + 14},{y + 26}" {s}/>'
    )
    c.lines(x, y + 44 + (len(rows) - 1) * 8, rows, "t13 b")
    ACT[key] = (x, y, "stick")


def link(a, u):
    ax, ay, kind = ACT[a]
    ux, uy, rx, ry = UC[u]
    start = (
        (ax + (24 if ux > ax else -24), ay - 12)
        if kind == "stick"
        else (ax + (55 if ux > ax else -55), ay)
    )
    end = clip_ellipse(ux, uy, rx, ry, *start)
    c.path([start, end])


def include(a, b, label="«include»"):
    ax, ay, arx, ary = UC[a]
    bx, by, brx, bry = UC[b]
    p1 = clip_ellipse(ax, ay, arx, ary, bx, by)
    p2 = clip_ellipse(bx, by, brx, bry, ax, ay)
    c.path([p1, p2], "ln dash", marker_end="open")
    m = mid(p1, p2)
    c.text(m[0], m[1] - 6, label, "t11 muted")


def generalize(child, parent):
    cx, cy, _ = ACT[child]
    px, py, _ = ACT[parent]
    c.path([(cx, cy - 52), (px, py + 66)], marker_end="hollow")


# Acteurs
actor("visiteur", 110, 200, ["Visiteur"])
actor("membre", 110, 520, ["Membre"])
actor("vip", 110, 850, ["Membre VIP"])
actor("moderateur", 1290, 250, ["Modérateur"])
actor("admin", 1290, 520, ["Administrateur"])
actor("stripe", 1290, 720, ["Stripe"], system=True)
generalize("membre", "visiteur")
generalize("vip", "membre")
c.path([(1290, 520 - 52), (1290, 250 + 66)], marker_end="hollow")  # admin → modérateur

# Cas d'utilisation — colonne gauche
L, M, R = 450, 770, 1020
usecase("consulter", L, 110, ["Consulter, rechercher", "et trier les deals"])
usecase("langue", L, 170, ["Changer de langue (FR/NL/DE)"])
usecase("locaux", L, 230, ["Voir les commerçants locaux"])
usecase("inscrire", L, 290, ["S'inscrire"])
usecase("publier", L, 370, ["Publier un deal"])
usecase("voter", L, 430, ["Voter et commenter"])
usecase("signaler", L, 490, ["Signaler un deal"])
usecase("alertes", L, 550, ["Gérer ses alertes"])
usecase("vipsub", L, 610, ["S'abonner au VIP"])
usecase("exporter", L, 670, ["Exporter ses données (RGPD)"])
usecase("fermer", L, 730, ["Fermer son compte"])
usecase("historique", L, 820, ["Voir l'historique du prix"])
usecase("comparer", L, 880, ["Comparer avec d'autres sites"])
usecase("priorite", L, 940, ["Recevoir les alertes en priorité"])

# Cas inclus — colonne centrale
usecase(
    "prefill", M, 370, ["Pré-remplir depuis", "un lien (prix, photo)"], rx=112, fill="#fbfbfd"
)
usecase("payer", M, 610, ["Payer en ligne", "(Stripe Checkout)"], rx=105, fill="#fbfbfd")
usecase(
    "softdel", 930, 745, ["Désinscription logique", "(soft delete)"], rx=112, fill="#fbfbfd"
)

# Personnel — colonne droite
usecase("moderer", R, 200, ["Modérer les deals", "(publier / refuser)"], rx=140)
usecase("signalements", R, 275, ["Traiter les signalements"], rx=140)
usecase("membres", R, 600, ["Gérer les membres", "(désactiver, anonymiser)"], rx=140)
usecase("catalogue", R, 525, ["Gérer marchands", "et catégories"], rx=140)
usecase("audit", R, 450, ["Consulter le journal d'audit"], rx=140)

for u in ("consulter", "langue", "locaux", "inscrire"):
    link("visiteur", u)
for u in ("publier", "voter", "signaler", "alertes", "vipsub", "exporter", "fermer"):
    link("membre", u)
for u in ("historique", "comparer", "priorite"):
    link("vip", u)
for u in ("moderer", "signalements"):
    link("moderateur", u)
for u in ("membres", "catalogue", "audit"):
    link("admin", u)
link("stripe", "payer")

include("publier", "prefill")
include("vipsub", "payer")
include("fermer", "softdel")
include("membres", "softdel")

# Légende
c.text(
    SX + 14,
    SY + SH - 14,
    "Un Membre hérite des cas du Visiteur, un Membre VIP de ceux du Membre, un Administrateur de ceux du Modérateur.",
    "t11 muted",
    "start",
)

open("../01_cas_utilisation.svg", "w", encoding="utf-8").write(c.svg())
print("ok cas d'utilisation")
