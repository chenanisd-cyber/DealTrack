"""Petite boîte à outils pour dessiner des diagrammes UML en SVG (sans dépendance)."""

import math
from html import escape

FONT = "Arial, Helvetica, sans-serif"


def text_width(s, size=13):
    return len(s) * size * 0.53


class Canvas:
    def __init__(self, width, height, title=""):
        self.w, self.h, self.title = width, height, title
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def svg(self):
        defs = """
<defs>
  <marker id="open" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse">
    <path d="M1,1 L11,6 L1,11" fill="none" stroke="#1d2433" stroke-width="1.4"/>
  </marker>
  <marker id="filled" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
    <path d="M1,1 L11,6 L1,11 Z" fill="#1d2433"/>
  </marker>
  <marker id="hollow" viewBox="0 0 16 16" refX="15" refY="8" markerWidth="16" markerHeight="16" orient="auto-start-reverse">
    <path d="M1,1 L15,8 L1,15 Z" fill="#fff" stroke="#1d2433" stroke-width="1.3"/>
  </marker>
  <marker id="diamond" viewBox="0 0 18 12" refX="17" refY="6" markerWidth="18" markerHeight="12" orient="auto-start-reverse">
    <path d="M1,6 L9,1 L17,6 L9,11 Z" fill="#1d2433"/>
  </marker>
</defs>"""
        style = f"""
<style>
  text {{ font-family: {FONT}; fill: #1d2433; }}
  .t13 {{ font-size: 13px; }}
  .t12 {{ font-size: 12px; }}
  .t11 {{ font-size: 11px; }}
  .b {{ font-weight: bold; }}
  .i {{ font-style: italic; }}
  .muted {{ fill: #5b6475; }}
  .ln {{ stroke: #1d2433; stroke-width: 1.3; fill: none; }}
  .dash {{ stroke-dasharray: 6 4; }}
</style>"""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" role="img" aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title>{defs}{style}"
            f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>'
            + "".join(self.parts)
            + "</svg>"
        )

    # -- primitives ---------------------------------------------------------
    def text(self, x, y, s, cls="t13", anchor="middle"):
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{escape(s)}</text>'
        )

    def lines(self, x, y, rows, cls="t13", anchor="middle", lh=16):
        top = y - (len(rows) - 1) * lh / 2 + 4.5
        for i, r in enumerate(rows):
            self.text(x, top + i * lh, r, cls, anchor)

    def path(self, pts, cls="ln", marker_end=None, marker_start=None):
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        m = ""
        if marker_end:
            m += f' marker-end="url(#{marker_end})"'
        if marker_start:
            m += f' marker-start="url(#{marker_start})"'
        self.add(f'<path d="{d}" class="{cls}"{m}/>')


# -- géométrie ----------------------------------------------------------------
def clip_ellipse(cx, cy, rx, ry, tx, ty):
    dx, dy = tx - cx, ty - cy
    t = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return cx + dx * t, cy + dy * t


def clip_rect(x, y, w, h, tx, ty):
    cx, cy = x + w / 2, y + h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else math.inf
    sy = (h / 2) / abs(dy) if dy else math.inf
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def mid(a, b, f=0.5):
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def offset_label(a, b, along, side, f_from_a=True):
    """Point près de l'extrémité a, décalé le long du segment et sur le côté."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    return a[0] + ux * along + px * side, a[1] + uy * along + py * side
