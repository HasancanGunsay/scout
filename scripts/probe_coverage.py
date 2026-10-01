"""Faz 0 / Adim 2: VERI KAPSAM MATRISI.

Her hedef lig icin FBref'ten bir sezonluk 'standard' oyuncu istatistigi ceker
ve sunlari olcer:
  - oyuncu sayisi
  - gelismis metrikler (xG, npxG, xAG, PrgC, PrgP) MEVCUT MU
  - mevcutsa dolulук orani (bazi liglerde sutun var ama tamamen bos)
  - yas/dogum yili verisi var mi (U21 taramasi icin sart)

'standard' tablosu tek istekte hepsini soyledigi icin lig basina 1 istek yeter.

Dayanikli: her ligden sonra CSV'ye yazar, tekrar calistirilinca kaldigi
yerden devam eder (--restart ile sifirdan).

Cikti: data/raw/coverage_matrix.csv
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LEAGUE_DICT_SRC = ROOT / "config" / "fbref_league_dict.json"
OUT = ROOT / "data" / "raw" / "coverage_matrix.csv"

# Bir ligin "scoutlanabilir" sayilmasi icin aranan cekirdek gelismis metrikler
ADVANCED = ["xG", "npxG", "xAG", "PrgC", "PrgP"]


def install_league_dict() -> dict:
    """Ozel lig sozlugunu soccerdata'nin config dizinine kopyala.

    soccerdata import edilmeden ONCE calismali - LEAGUE_DICT import aninda okunuyor.
    """
    cfg_dir = Path.home() / "soccerdata" / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    dst = cfg_dir / "league_dict.json"
    shutil.copyfile(LEAGUE_DICT_SRC, dst)
    print(f"[cfg]   lig sozlugu kuruldu -> {dst}")
    return json.loads(LEAGUE_DICT_SRC.read_text(encoding="utf-8"))


def pick_season(meta: dict) -> str:
    """Kapsam testi icin TAMAMLANMIS bir sezon sec."""
    return "2025" if meta.get("season_code") == "single-year" else "2024-2025"


def flatten(cols) -> list[str]:
    """FBref cok seviyeli sutunlarini tek isme indir (son seviye yeterli)."""
    out = []
    for c in cols:
        out.append(c[-1] if isinstance(c, tuple) else str(c))
    return out


def probe_one(sd, league: str, season: str) -> dict:
    fb = sd.FBref(leagues=league, seasons=season)
    df = fb.read_player_season_stats(stat_type="standard")

    df = df.copy()
    df.columns = flatten(df.columns)
    cols = set(df.columns)

    row: dict = {
        "league": league,
        "season": season,
        "status": "ok",
        "n_players": len(df),
        "n_teams": df.index.get_level_values("team").nunique()
        if "team" in df.index.names
        else None,
        "has_age": "age" in cols,
        "has_born": "born" in cols,
        "has_minutes": "Min" in cols,
    }

    # yas dagilimi - U21 avi icin gercekten kullanilabilir mi?
    if "born" in cols:
        born = pd.to_numeric(df["born"], errors="coerce")
        row["born_fill_pct"] = round(100 * born.notna().mean(), 1)
        row["n_u21"] = int((born >= int(season[:4]) - 21).sum())
    else:
        row["born_fill_pct"] = 0.0
        row["n_u21"] = 0

    # gelismis metrikler
    present = 0
    for m in ADVANCED:
        if m in cols:
            v = pd.to_numeric(df[m], errors="coerce")
            fill = round(100 * v.notna().mean(), 1)
            row[f"{m}_pct"] = fill
            if fill > 50:
                present += 1
        else:
            row[f"{m}_pct"] = None
    row["n_advanced"] = present
    row["tier"] = "T1" if present >= 4 else ("T2" if present >= 1 else "T3")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart", action="store_true", help="mevcut sonuclari yoksay")
    ap.add_argument("--only", help="virgulle ayrilmis lig anahtarlari")
    args = ap.parse_args()

    leagues_meta = install_league_dict()
    import soccerdata as sd  # noqa: E402  (lig sozlugu kurulduktan SONRA)

    targets = list(leagues_meta)
    if args.only:
        targets = [t.strip() for t in args.only.split(",")]

    done: dict[str, dict] = {}
    if OUT.exists() and not args.restart:
        prev = pd.read_csv(OUT)
        done = {r["league"]: r for r in prev.to_dict("records")}
        print(f"[resume] {len(done)} lig zaten olculmus, atlaniyor")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = len(targets)

    for i, league in enumerate(targets, 1):
        if league in done:
            continue
        season = pick_season(leagues_meta[league])
        print(f"\n[{i}/{total}] {league} ({season}) ...", flush=True)
        try:
            row = probe_one(sd, league, season)
            print(
                f"    -> {row['tier']}  oyuncu={row['n_players']}  "
                f"U21={row['n_u21']}  gelismis={row['n_advanced']}/{len(ADVANCED)}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - her lig bagimsiz, biri patlarsa devam
            print(f"    !! HATA: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc(limit=1)
            row = {
                "league": league,
                "season": season,
                "status": f"{type(exc).__name__}: {str(exc)[:160]}",
                "tier": "ERR",
            }

        done[league] = row
        # her ligden sonra kaydet - uzun sureli is, yarida kesilirse kayip olmasin
        pd.DataFrame(list(done.values())).to_csv(OUT, index=False, encoding="utf-8")

    df = pd.DataFrame(list(done.values()))
    print(f"\n\n===== VERI KAPSAM MATRISI ({len(df)} lig) -> {OUT} =====")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 100)
    show = [
        c
        for c in ["league", "tier", "n_players", "n_u21", "n_advanced", "born_fill_pct", "status"]
        if c in df.columns
    ]
    print(df.sort_values("tier")[show].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
