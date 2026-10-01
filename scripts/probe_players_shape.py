"""Faz 1b / Adim 2: /players yanitinin GERCEK icerigini gor.

Kapsam bayraklari yalan soyleyebilir. Bu script bir T1 ligden (tam veri iddiasi)
ve bir T2 ligden (sinirli veri iddiasi) birer sayfa cekip yanitin icinde
GERCEKTEN hangi metrikler var, doluluk ne kadar - onu olcer.

Bu, skorlama motorunun (§5) hangi metrikler uzerine kurulacagini belirler.
Istek maliyeti: lig basina 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout.ingest.apifootball import ApiFootball  # noqa: E402

# (etiket, league_id, season)
# NOT: Ucretsiz plan yalnizca 2022-2024 sezonlarina erisiyor (2025+ kapali).
# (etiket, league_id, season, page)
PROBES = [
    ("T1 iddiasi | Brezilya Serie B", 72, 2024, 1),
    ("T2 iddiasi | Italya Serie C Girone A", 138, 2024, 1),
]


def walk(node, prefix="") -> dict:
    """Ic ice sozlugu duz 'a.b.c' anahtarlarina ac."""
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(walk(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = node
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="ham ornek kaydi da yazdir")
    ap.add_argument(
        "--probes",
        help="ozel probe listesi: 'etiket:lig:sezon:sayfa' virgulle ayrilmis",
    )
    args = ap.parse_args()

    probes = PROBES
    if args.probes:
        probes = []
        for spec in args.probes.split(","):
            lbl, lid, ss, pg = spec.split(":")
            probes.append((lbl, int(lid), int(ss), int(pg)))

    with ApiFootball() as api:
        print(f"[kota] baslangic {api.used_today}/{api.daily_limit}\n")

        for label, lid, season, page in probes:
            print("=" * 78)
            print(f"{label}   (league={lid}, season={season}, page={page})")
            print("=" * 78)
            try:
                p = api.get("players", {"league": lid, "season": season, "page": page})
            except Exception as exc:  # noqa: BLE001
                print(f"  !! {type(exc).__name__}: {exc}\n")
                continue

            paging = p.get("paging", {})
            resp = p.get("response", [])
            print(f"  sayfa {paging.get('current')}/{paging.get('total')} | "
                  f"bu sayfada {len(resp)} oyuncu")
            print(f"  -> tahmini toplam oyuncu: ~{paging.get('total', 0) * len(resp)}")
            print(f"  -> tum ligi cekmek {paging.get('total')} istek eder\n")

            if not resp:
                print("  BOS YANIT\n")
                continue

            # Tum sayfadaki kayitlar uzerinden alan doluluk orani
            flat_all = []
            for rec in resp:
                base = walk(rec.get("player", {}), "player")
                stats = rec.get("statistics") or [{}]
                base.update(walk(stats[0], "stats"))
                flat_all.append(base)

            keys = sorted({k for f in flat_all for k in f})
            print(f"  {len(keys)} alan bulundu. Doluluk (bos olmayan / {len(flat_all)}):\n")
            for k in keys:
                vals = [f.get(k) for f in flat_all]
                filled = sum(1 for v in vals if v not in (None, "", [], {}))
                pct = 100 * filled / len(vals)
                bar = "#" * int(pct / 5)
                mark = "  " if pct > 50 else "!!"
                sample = next((v for v in vals if v not in (None, "", [], {})), "")
                print(f"   {mark} {k:42} {pct:5.0f}% {bar:20} ornek={str(sample)[:22]}")
            print()

            if args.dump:
                print("  --- ham ornek kayit ---")
                print(json.dumps(resp[0], indent=1, ensure_ascii=False)[:2500])
                print()

        print(f"[kota] bitis {api.used_today}/{api.daily_limit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
