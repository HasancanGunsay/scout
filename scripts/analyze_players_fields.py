"""Faz 1b / Adim 3: /players yanitindaki metriklerin GERCEK dolulugu.

Onemli incelik: bir oyuncunun 'statistics' dizisinde BIRDEN FAZLA giris olabilir
(sezon ici kulup degisimi, ayni sezonda farkli musabakalar) ve bazi girisler
tamamen bos stub kayitlardir. statistics[0]'a bakmak yaniltir.

Dogru yontem: ilgili LIGE ait ve dakikasi olan girisleri al, doluluk oranini
onlar uzerinden hesapla.

Bu script YALNIZCA ONBELLEKTEN okur - hicbir API istegi atmaz.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "apifootball" / "players"

# Skorlama motoru icin aday metrikler (§4)
METRICS = [
    "games.appearences", "games.lineups", "games.minutes", "games.rating",
    "goals.total", "goals.assists", "goals.conceded", "goals.saves",
    "shots.total", "shots.on",
    "passes.total", "passes.key", "passes.accuracy",
    "tackles.total", "tackles.blocks", "tackles.interceptions",
    "duels.total", "duels.won",
    "dribbles.attempts", "dribbles.success", "dribbles.past",
    "fouls.drawn", "fouls.committed",
    "cards.yellow", "cards.red",
    "penalty.scored", "penalty.missed", "penalty.won",
    "substitutes.in", "substitutes.out", "substitutes.bench",
]


def dig(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def main() -> int:
    if not CACHE.exists():
        raise SystemExit(f"Onbellek yok: {CACHE}")

    pd.set_option("display.width", 200)
    rows = []

    for f in sorted(CACHE.glob("*.json")):
        payload = json.loads(f.read_text(encoding="utf-8"))
        # dosya adindan hedef ligi cikar: league-<id>_page-...
        target_lid = int(f.name.split("league-")[1].split("_")[0])

        entries = []
        for rec in payload.get("response", []):
            for s in rec.get("statistics", []):
                if (s.get("league") or {}).get("id") != target_lid:
                    continue  # baska musabakadaki kayit
                if not (s.get("games") or {}).get("minutes"):
                    continue  # oynamamis / bos stub
                entries.append(s)

        n_players = len(payload.get("response", []))
        if not entries:
            rows.append({"kaynak": f.name[:34], "oyuncu": n_players, "oynayan": 0})
            continue

        row = {"kaynak": f.name[:34], "oyuncu": n_players, "oynayan": len(entries)}
        for m in METRICS:
            filled = sum(1 for e in entries if dig(e, m) is not None)
            row[m] = round(100 * filled / len(entries))
        rows.append(row)

    df = pd.DataFrame(rows).set_index("kaynak")

    print("=" * 78)
    print("METRIK DOLULUK ORANI (%) - lige ait, dakikasi olan kayitlar uzerinden")
    print("=" * 78)
    print(df[["oyuncu", "oynayan"]].to_string())

    metric_cols = [c for c in df.columns if c in METRICS]
    print("\n--- metrik bazinda ---")
    print(df[metric_cols].T.to_string())

    print("\n--- OZET: her kaynakta %80+ dolu metrik sayisi ---")
    for idx, r in df.iterrows():
        if r.get("oynayan", 0) == 0:
            print(f"  {idx:36} VERI YOK")
            continue
        good = [m for m in metric_cols if r.get(m, 0) >= 80]
        print(f"  {idx:36} {len(good):2}/{len(metric_cols)} metrik")
    return 0


if __name__ == "__main__":
    sys.exit(main())
