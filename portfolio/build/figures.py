"""Portfolio figures as static SVG, from documented measurements.

Every number here is copied from PLAN.md / reports/ (section noted) - the
site never shows a number that is not in the project's own record.
    .venv/Scripts/python.exe portfolio/build/figures.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "img"

INK = "#0F172A"
MUTED = "#64748B"
GRID = "#E2E8F0"
BLUE = "#1D4ED8"
SLATE = "#94A3B8"
TEAL = "#0E7490"
FONT = "Inter, system-ui, sans-serif"
MONO = "JetBrains Mono, ui-monospace, monospace"

# PLAN §53.5 - sealed test 2018-21, n=3,097, within-league AUC
SEALED = [
    ("Model (play data + value)", 0.742, BLUE),
    ("Play data only", 0.744, TEAL),
    ("Minutes + age baseline", 0.696, SLATE),
    ("Market value baseline", 0.686, SLATE),
]
# PLAN §53.5 - season by season
SEASONS = ["2018/19", "2019/20", "2020/21", "2021/22"]
BY_SEASON = {
    "Model": ([0.706, 0.759, 0.768, 0.731], BLUE),
    "Minutes + age": ([0.667, 0.694, 0.730, 0.691], SLATE),
    "Market value": ([0.660, 0.689, 0.723, 0.670], "#CBD5E1"),
}


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{label}" font-family="{FONT}">{body}</svg>\n')


def sealed_bars():
    w, h, left, top, bar, gap = 720, 285, 230, 20, 34, 18
    lo, hi = 0.60, 0.78
    sx = lambda v: left + (v - lo) / (hi - lo) * (w - left - 70)  # noqa: E731
    b = []
    for t in [0.60, 0.65, 0.70, 0.75]:
        x = sx(t)
        b.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{top + 4 * (bar + gap)}" '
                 f'stroke="{GRID}"/>')
        b.append(f'<text x="{x:.1f}" y="{top + 4 * (bar + gap) + 16}" font-size="12" '
                 f'fill="{MUTED}" text-anchor="middle" font-family="{MONO}">{t:.2f}</text>')
    for i, (ad, v, c) in enumerate(SEALED):
        y = top + i * (bar + gap)
        b.append(f'<text x="{left - 12}" y="{y + bar / 2 + 5}" font-size="14" fill="{INK}" '
                 f'text-anchor="end">{ad}</text>')
        b.append(f'<rect x="{left}" y="{y}" width="{sx(v) - left:.1f}" height="{bar}" rx="4" fill="{c}"/>')
        b.append(f'<text x="{sx(v) + 8:.1f}" y="{y + bar / 2 + 5}" font-size="14" font-weight="600" '
                 f'fill="{INK}" font-family="{MONO}">{v:.3f}</text>')
    b.append(f'<text x="{left}" y="{h - 6}" font-size="12" fill="{MUTED}">'
             'Within-league ROC AUC · axis starts at 0.60</text>')
    return svg(w, h, "".join(b), "Sealed test AUC: model vs baselines")


def season_lines():
    w, h, l, r, t, bt = 720, 300, 60, 150, 20, 40
    lo, hi = 0.64, 0.78
    sx = lambda i: l + i * (w - l - r) / (len(SEASONS) - 1)  # noqa: E731
    sy = lambda v: t + (hi - v) / (hi - lo) * (h - t - bt)  # noqa: E731
    b = []
    for v in [0.66, 0.70, 0.74, 0.78]:
        b.append(f'<line x1="{l}" y1="{sy(v):.1f}" x2="{w - r}" y2="{sy(v):.1f}" stroke="{GRID}"/>')
        b.append(f'<text x="{l - 10}" y="{sy(v) + 4:.1f}" font-size="12" fill="{MUTED}" '
                 f'text-anchor="end" font-family="{MONO}">{v:.2f}</text>')
    for i, s in enumerate(SEASONS):
        b.append(f'<text x="{sx(i):.1f}" y="{h - 14}" font-size="12" fill="{MUTED}" '
                 f'text-anchor="middle" font-family="{MONO}">{s}</text>')
    for ad, (vals, c) in BY_SEASON.items():
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
        wdt = 3 if ad == "Model" else 2
        b.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="{wdt}" '
                 'stroke-linejoin="round"/>')
        for i, v in enumerate(vals):
            b.append(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="4" fill="{c}"/>')
        b.append(f'<text x="{sx(3) + 12:.1f}" y="{sy(vals[-1]) + 4:.1f}" font-size="13" '
                 f'fill="{INK}">{ad}</text>')
    return svg(w, h, "".join(b), "Sealed test AUC by season")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sealed-test.svg").write_text(sealed_bars(), encoding="utf-8")
    (OUT / "sealed-seasons.svg").write_text(season_lines(), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
