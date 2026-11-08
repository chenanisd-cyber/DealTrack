"""Diagramme de classes — DealTrack.be (fidèle aux modèles Django)."""

from svg import Canvas, clip_rect, mid, offset_label

W, H = 1660, 1115
c = Canvas(W, H, "DealTrack.be — diagramme de classes")
LH, HEAD = 17, 28
BOX = {}


def klass(key, x, y, w, attrs, ops=(), stereo=None, name=None, fill="#ffffff", head="#eef1f6"):
    name = name or key
    h = (
        HEAD
        + (14 if stereo else 0)
        + 8
        + len(attrs) * LH
        + (8 + len(ops) * LH if ops else 0)
        + 6
    )
    BOX[key] = (x, y, w, h)
    hh = HEAD + (14 if stereo else 0)
    c.add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="#1d2433" stroke-width="1.3"/>'
    )
    c.add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" fill="{head}" stroke="#1d2433" stroke-width="1.3"/>'
    )
    if stereo:
        c.text(x + w / 2, y + 15, f"«{stereo}»", "t11 muted")
        c.text(x + w / 2, y + 33, name, "t13 b")
    else:
        c.text(x + w / 2, y + 19, name, "t13 b")
    yy = y + hh + 8
    for a in attrs:
        c.text(x + 8, yy + 12, a, "t12", "start")
        yy += LH
    if ops:
        yy += 4
        c.add(
            f'<line x1="{x}" y1="{yy}" x2="{x + w}" y2="{yy}" stroke="#1d2433" stroke-width="1.1"/>'
        )
        yy += 4
        for o in ops:
            c.text(x + 8, yy + 12, o, "t12", "start")
            yy += LH


def center(k):
    x, y, w, h = BOX[k]
    return x + w / 2, y + h / 2


def assoc(
    a,
    b,
    ma="",
    mb="",
    label="",
    via=None,
    comp=False,
    pa=None,
    pb=None,
    lab_at=0.5,
    side_a=10,
    side_b=10,
):
    """Association a—b. pa/pb : point d'ancrage imposé ; via : points intermédiaires."""
    ca, cb = center(a), center(b)
    first_target = via[0] if via else (pb or cb)
    last_source = via[-1] if via else (pa or ca)
    p1 = pa or clip_rect(*BOX[a], *first_target)
    p2 = pb or clip_rect(*BOX[b], *last_source)
    pts = [p1] + (via or []) + [p2]
    c.path(pts, marker_start="diamond" if comp else None)
    if ma:
        q = offset_label(pts[0], pts[1], 16 if not comp else 26, side_a)
        c.text(q[0], q[1] + 4, ma, "t11")
    if mb:
        q = offset_label(pts[-1], pts[-2], 16, side_b)
        c.text(q[0], q[1] + 4, mb, "t11")
    if label:
        i = len(pts) // 2
        m = mid(pts[i - 1], pts[i], lab_at) if len(pts) % 2 == 0 else pts[i]
        c.text(m[0], m[1] - 6, label, "t11 i muted")


# ---------------------------------------------------------------- classes
klass(
    "Deal",
    400,
    250,
    300,
    [
        "- id : UUID",
        "- title : str",
        "- price : Decimal",
        "- reference_price : Decimal",
        "- status : DealStatus",
        "- temperature : int",
        "- published_at : datetime",
        "- deleted_at : datetime [0..1]",
    ],
    [
        "+ publish(moderator)",
        "+ reject(moderator, reason)",
        "+ soft_delete(actor)",
        "+ discount_percentage() : int",
    ],
)

klass(
    "User",
    1010,
    250,
    300,
    [
        "- id : UUID",
        "- email : str  {unique}",
        "- display_name : str",
        "- role : Role",
        "- preferred_language : str",
        "- deleted_at : datetime [0..1]",
        "- anonymised_at : datetime [0..1]",
    ],
    ["+ is_vip() : bool", "+ soft_delete(reason, actor)", "+ anonymise(actor)"],
)

# colonne centrale (entre Deal et User)
klass("Vote", 760, 40, 190, ["- value : int  {+1 | -1}", "- created_at : datetime"])
klass(
    "Comment",
    760,
    200,
    190,
    ["- body : str", "- language : str", "- deleted_at : datetime [0..1]"],
)
klass("Report", 760, 470, 190, ["- reason : str", "- status : str", "- resolved_at : datetime"])
klass(
    "ModerationDecision",
    760,
    650,
    190,
    ["- decision : str", "- reason : str", "- created_at : datetime"],
)
klass("CommentTranslation", 760, 315, 190, ["- language : str", "- body : str"])

# colonne gauche
klass(
    "DealTranslation", 40, 40, 270, ["- language : str", "- title : str", "- description : str"]
)
klass("DealImage", 40, 190, 270, ["- image / image_url", "- position : int"])
klass(
    "PricePoint",
    40,
    310,
    270,
    ["- price : Decimal", "- source : str", "- recorded_at : datetime"],
)
klass(
    "Merchant",
    40,
    430,
    270,
    [
        "- name : str",
        "- country : str",
        "- vat_number : str",
        "- is_local_independent : bool",
        "- is_verified : bool",
        "- city : str",
    ],
)
klass("CategoryTranslation", 40, 830, 230, ["- language : str", "- name : str"])
klass(
    "AlertMatch",
    400,
    560,
    250,
    ["- is_priority : bool", "- available_at : datetime", "- notified_at : datetime [0..1]"],
    stereo="classe d'association",
)

# sous Deal
klass(
    "Category",
    40,
    640,
    230,
    ["- slug : str", "- position : int", "- is_active : bool"],
    ["+ label(language) : str"],
)
klass(
    "Alert",
    760,
    880,
    230,
    ["- keyword : str", "- max_price : Decimal [0..1]", "- is_active : bool"],
)

# colonne droite
klass(
    "Plan",
    1380,
    40,
    240,
    [
        "- code : str  {unique}",
        "- price : Decimal",
        "- vat_rate : Decimal",
        "- duration_days : int",
    ],
)
klass(
    "Payment",
    1380,
    250,
    240,
    [
        "- reference : str  {unique}",
        "- amount : Decimal",
        "- vat_amount : Decimal",
        "- status : PaymentStatus",
        "- gateway : str",
        "- card_last4 : str",
    ],
)
klass(
    "Subscription",
    1380,
    500,
    240,
    ["- status : str", "- started_at : datetime", "- ends_at : datetime"],
)
klass(
    "AuditLog",
    1380,
    720,
    240,
    [
        "- action : str",
        "- target : objet (générique)",
        "- ip_address : str",
        "- metadata : JSON",
        "- created_at : datetime",
    ],
)

# énumérations
klass("Role", 40, 960, 150, ["member", "moderator", "admin"], stereo="enumeration")
klass(
    "DealStatus",
    210,
    960,
    160,
    ["draft · pending", "published · rejected", "expired"],
    stereo="enumeration",
)
klass(
    "PaymentStatus",
    390,
    960,
    170,
    ["pending · succeeded", "failed · refunded"],
    stereo="enumeration",
)

# ---------------------------------------------------------------- associations
dx, dy, dw, dh = BOX["Deal"]
ux, uy, uw, uh = BOX["User"]

# Deal — User (auteur) : ligne horizontale sous Comment, au-dessus de Report
yline = 430
assoc(
    "Deal", "User", "0..*", "1", "submitted_by", pa=(dx + dw, yline), pb=(ux, yline), lab_at=0.5
)

assoc("Vote", "Deal", "0..*", "1")
assoc("Vote", "User", "0..*", "1")
assoc("Comment", "Deal", "0..*", "1")
assoc("Comment", "User", "0..*", "1", "author")
assoc("Comment", "CommentTranslation", "1", "0..*", comp=True)
assoc("Report", "Deal", "0..*", "1")
assoc("Report", "User", "0..*", "1", "reporter")
assoc("ModerationDecision", "Deal", "0..*", "1")
assoc("ModerationDecision", "User", "0..*", "1", "moderator")

assoc("Deal", "DealTranslation", "1", "0..*", comp=True, pa=(dx, dy + 14))
assoc("Deal", "DealImage", "1", "0..*", comp=True, pa=(dx, dy + 60))
assoc("Deal", "PricePoint", "1", "0..*", comp=True, label="historique (VIP)", pa=(dx, dy + 105))
assoc("Deal", "Merchant", "0..*", "1", pa=(dx, dy + 215))
assoc("Deal", "Category", "0..*", "1")
assoc("Category", "CategoryTranslation", "1", "1..*", comp=True)
cx_, cy_, cw_, ch_ = BOX["Category"]
c.path(
    [
        (cx_ + cw_, cy_ + 40),
        (cx_ + cw_ + 26, cy_ + 40),
        (cx_ + cw_ + 26, cy_ + 70),
        (cx_ + cw_, cy_ + 70),
    ]
)
c.text(cx_ + cw_ + 32, cy_ + 59, "parent 0..1", "t11", "start")

# Alerte ↔ Deal avec classe d'association AlertMatch
ax, ay, aw, ah = BOX["Alert"]
a_pt = (ax + 30, ay)
d_pt = (dx + 220, dy + dh)
c.path([a_pt, d_pt])
c.text(a_pt[0] - 22, a_pt[1] - 8, "0..*", "t11")
c.text(d_pt[0] - 18, d_pt[1] + 18, "0..*", "t11")
m = mid(a_pt, d_pt, 0.55)
mx, my, mw, mh = BOX["AlertMatch"]
c.path([m, (mx + mw, my + mh / 2)], "ln dash")
assoc("Alert", "User", "0..*", "1")
assoc("Alert", "Category", "0..*", "0..1")

assoc("Payment", "User", "0..*", "1")
assoc("Payment", "Plan", "0..*", "1")
assoc("Subscription", "Payment", "0..1", "1")
assoc("Subscription", "User", "0..*", "1")
px, py, pw, ph = BOX["Plan"]
sx, sy, sw, sh = BOX["Subscription"]
c.path(
    [(sx + sw, sy + 30), (sx + sw + 24, sy + 30), (sx + sw + 24, py + 30), (px + pw, py + 30)]
)
c.text(sx + sw + 4, sy + 24, "0..*", "t11", "start")
c.text(px + pw + 4, py + 24, "1", "t11", "start")
assoc("AuditLog", "User", "0..*", "0..1", "actor")

c.text(
    40,
    1100,
    "Losange plein : composition (les parties n'existent pas sans le tout). "
    "Champs « deleted_at » : suppression logique, la ligne reste en base. "
    "Traductions : une ligne par langue (fr, nl, de).",
    "t11 muted",
    "start",
)

open("../02_classes.svg", "w", encoding="utf-8").write(c.svg())
print("ok classes")
