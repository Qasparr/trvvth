# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""charts -- hand-rolled SVG charts. No dependencies, cross-platform.

The API serves these as ``image/svg+xml`` so any browser, dashboard,
or report can embed them directly. Colors follow the alethic axis:
gold for TRVVTH, indigo for UNRESOLVED, iron red for FALSEHOOD.
"""

from __future__ import annotations

import html

VERDICT_COLORS = {
    "TRVVTH": "#c9a227",      # gold
    "UNRESOLVED": "#3b3b6d",  # indigo
    "FALSEHOOD": "#a33327",   # iron red
}

INK = "#1a1a2e"
PAPER = "#faf8f2"
GRID = "#e3ddcf"

_W = 640
_H = 360
_PAD_L = 56
_PAD_R = 20
_PAD_T = 44
_PAD_B = 48


def _frame(title: str, subtitle: str = "") -> tuple[list[str], int, int]:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}"'
        f' role="img" aria-label="{html.escape(title)}">',
        f'<rect width="{_W}" height="{_H}" fill="{PAPER}"/>',
        f'<text x="{_W // 2}" y="26" text-anchor="middle"'
        f' font-family="Georgia,serif" font-size="17" fill="{INK}">'
        f'{html.escape(title)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{_W // 2}" y="42" text-anchor="middle"'
            f' font-family="Georgia,serif" font-size="11" fill="#6b6b7d">'
            f'{html.escape(subtitle)}</text>')
    return parts, _W - _PAD_L - _PAD_R, _H - _PAD_T - _PAD_B


def bar_chart(title: str, items: list[tuple[str, float]],
              subtitle: str = "",
              colors: dict[str, str] | None = None) -> str:
    """Vertical bars. items: (label, value)."""
    parts, pw, ph = _frame(title, subtitle)
    colors = colors or {}
    top = max([v for _, v in items] + [1])
    n = max(len(items), 1)
    slot = pw / n
    bw = min(slot * 0.62, 90)
    for i, (label, value) in enumerate(items):
        x = _PAD_L + slot * i + (slot - bw) / 2
        h = ph * (value / top) if top else 0
        y = _PAD_T + ph - h
        color = colors.get(label, "#3b3b6d")
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}"'
            f' fill="{color}" rx="3"/>')
        parts.append(
            f'<text x="{x + bw / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle"'
            f' font-size="12" font-family="Georgia,serif" fill="{INK}">'
            f'{value:g}</text>')
        parts.append(
            f'<text x="{x + bw / 2:.1f}" y="{_PAD_T + ph + 20:.1f}"'
            f' text-anchor="middle" font-size="11"'
            f' font-family="Georgia,serif" fill="#4a4a5e">'
            f'{html.escape(str(label))}</text>')
    # baseline
    parts.append(
        f'<line x1="{_PAD_L}" y1="{_PAD_T + ph}" x2="{_PAD_L + pw}"'
        f' y2="{_PAD_T + ph}" stroke="{INK}" stroke-width="1"/>')
    parts.append("</svg>")
    return "".join(parts)


def timeline(title: str, points: list[tuple[str, float]],
             subtitle: str = "", color: str = "#3b3b6d") -> str:
    """Bars over time. points: (day-label, value)."""
    parts, pw, ph = _frame(title, subtitle)
    top = max([v for _, v in points] + [1])
    n = max(len(points), 1)
    slot = pw / n
    bw = min(slot * 0.7, 40)
    for i, (label, value) in enumerate(points):
        x = _PAD_L + slot * i + (slot - bw) / 2
        h = ph * (value / top) if top else 0
        y = _PAD_T + ph - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}"'
            f' fill="{color}" rx="2" opacity="0.85"/>')
        if n <= 12 or i % max(n // 10, 1) == 0:
            parts.append(
                f'<text x="{x + bw / 2:.1f}" y="{_PAD_T + ph + 18:.1f}"'
                f' text-anchor="middle" font-size="10"'
                f' font-family="Georgia,serif" fill="#4a4a5e">'
                f'{html.escape(str(label)[5:])}</text>')
    parts.append(
        f'<line x1="{_PAD_L}" y1="{_PAD_T + ph}" x2="{_PAD_L + pw}"'
        f' y2="{_PAD_T + ph}" stroke="{INK}" stroke-width="1"/>')
    parts.append("</svg>")
    return "".join(parts)


def multi_series(title: str, series: dict[str, list[tuple[str, float]]],
                 subtitle: str = "") -> str:
    """Grouped bars: series name -> [(label, value)]. One group per label."""
    parts, pw, ph = _frame(title, subtitle)
    labels: list[str] = []
    for pts in series.values():
        for label, _ in pts:
            if label not in labels:
                labels.append(label)
    lookup = {name: dict(pts) for name, pts in series.items()}
    top = max([v for pts in series.values() for _, v in pts] + [1])
    names = list(series.keys())
    palette = ["#c9a227", "#3b3b6d", "#a33327", "#2e7d6f", "#7d3b6d"]
    n_groups = max(len(labels), 1)
    slot = pw / n_groups
    bw = min(slot / max(len(names), 1) * 0.8, 46)
    for gi, label in enumerate(labels):
        for si, name in enumerate(names):
            value = lookup[name].get(label, 0)
            x = _PAD_L + slot * gi + (slot - bw * len(names)) / 2 + si * bw
            h = ph * (value / top) if top else 0
            y = _PAD_T + ph - h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}"'
                f' height="{h:.1f}" fill="{palette[si % len(palette)]}"'
                f' rx="2"><title>{html.escape(name)}: {value:g}</title></rect>')
        parts.append(
            f'<text x="{_PAD_L + slot * gi + slot / 2:.1f}"'
            f' y="{_PAD_T + ph + 20:.1f}" text-anchor="middle" font-size="11"'
            f' font-family="Georgia,serif" fill="#4a4a5e">'
            f'{html.escape(str(label))}</text>')
    # legend
    lx = _PAD_L
    for si, name in enumerate(names):
        parts.append(
            f'<rect x="{lx}" y="{_H - 16}" width="12" height="12"'
            f' fill="{palette[si % len(palette)]}"/>'
            f'<text x="{lx + 16}" y="{_H - 6}" font-size="11"'
            f' font-family="Georgia,serif" fill="{INK}">'
            f'{html.escape(name)}</text>')
        lx += 16 + len(name) * 7 + 18
    parts.append(
        f'<line x1="{_PAD_L}" y1="{_PAD_T + ph}" x2="{_PAD_L + pw}"'
        f' y2="{_PAD_T + ph}" stroke="{INK}" stroke-width="1"/>')
    parts.append("</svg>")
    return "".join(parts)


def verdict_chart(counts: dict[str, int]) -> str:
    items = [(v, counts.get(v, 0)) for v in ("TRVVTH", "UNRESOLVED", "FALSEHOOD")]
    return bar_chart("Verdicts on the Alethic Axis", items,
                     subtitle="all workings weighed by this gate",
                     colors=VERDICT_COLORS)
