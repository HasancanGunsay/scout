"""Faz 1b / Adim 1: API-Football VERI KAPSAM MATRISI.

/leagues endpoint'i TEK ISTEKTE tum ligleri, tum sezonlariyla ve sezon basina
'coverage' bayraklariyla dondurur. 100 istek/gun kotasindan 1 tane harcayip
hangi ligde neyin oldugunu kesin ogreniyoruz.

Bizim icin kritik bayraklar:
  players                       -> oyuncu profilleri var mi
  fixtures.statistics_players   -> MAC BAZINDA OYUNCU ISTATISTIGI var mi  <-- en onemlisi
  fixtures.lineups              -> kadro/dakika bilgisi
  top_scorers / top_assists     -> zayif liglerde en azindan bu

Ciktilar:
  data/raw/coverage_api_all.csv     - butun ligler (referans)
  data/raw/coverage_api_targets.csv - hedef liglerimiz
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout.ingest.apifootball import ApiFootball  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_ALL = ROOT / "data" / "raw" / "coverage_api_all.csv"
OUT_TGT = ROOT / "data" / "raw" / "coverage_api_targets.csv"

# Wonderkid avi odakli hedef ulkeler
TARGET_COUNTRIES = {
    "Brazil", "Argentina", "Uruguay", "Colombia", "Ecuador", "Chile", "Paraguay", "Peru",
    "France", "Italy", "Netherlands", "Portugal", "Belgium", "Spain", "Germany", "England",
    "Denmark", "Norway", "Sweden", "Finland", "Iceland",
    "Austria", "Switzerland", "Croatia", "Serbia", "Poland", "Czech-Republic", "Turkey",
    "Japan", "Mexico", "USA",
}


def flatten(payload: dict) -> pd.DataFrame:
    rows = []
    for item in payload.get("response", []):
        lg = item.get("league", {}) or {}
        ctry = item.get("country", {}) or {}
        for s in item.get("seasons", []) or []:
            cov = s.get("coverage", {}) or {}
            fx = cov.get("fixtures", {}) or {}
            rows.append(
                {
                    "league_id": lg.get("id"),
                    "league": lg.get("name"),
                    "type": lg.get("type"),
                    "country": ctry.get("name"),
                    "season": s.get("year"),
                    "current": s.get("current"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "players": bool(cov.get("players")),
                    "stats_players": bool(fx.get("statistics_players")),
                    "stats_fixtures": bool(fx.get("statistics_fixtures")),
                    "lineups": bool(fx.get("lineups")),
                    "events": bool(fx.get("events")),
                    "standings": bool(cov.get("standings")),
                    "top_scorers": bool(cov.get("top_scorers")),
                    "injuries": bool(cov.get("injuries")),
                }
            )
    return pd.DataFrame(rows)


def tier(row) -> str:
    """Skorlama seviyesi: T1 tam, T2 sinirli, T3 sadece radar."""
    if row["stats_players"] and row["lineups"] and row["players"]:
        return "T1"
    if row["players"] and (row["lineups"] or row["top_scorers"]):
        return "T2"
    return "T3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="onbellegi yoksay, yeniden cek")
    args = ap.parse_args()

    with ApiFootball() as api:
        print(f"[kota]  baslangic {api.used_today}/{api.daily_limit}")
        payload = api.get("leagues", force=args.force)
        print(f"[kota]  bitis     {api.used_today}/{api.daily_limit}")

    df = flatten(payload)
    if df.empty:
        raise SystemExit("Bos yanit - API anahtarini ve kotayi kontrol et.")

    df["tier"] = df.apply(tier, axis=1)
    OUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_ALL, index=False, encoding="utf-8")

    n_leagues = df["league_id"].nunique()
    print(f"\n[ok]    {n_leagues} lig / {len(df)} lig-sezon -> {OUT_ALL}")

    # Son 3 sezona odaklan, sadece lig tipi (kupa degil), hedef ulkeler
    recent = df[
        (df["season"] >= 2023)
        & (df["type"] == "League")
        & (df["country"].isin(TARGET_COUNTRIES))
    ]
    # DIKKAT: son sezona bakmak yaniltici. Avrupa liglerinde "2026" = 2026/27,
    # henuz baslamadigi icin tum bayraklar False. Bu yuzden son 3 sezonda
    # BIR KEZ BILE True olmus mu diye bakiyoruz (max = herhangi biri True).
    tgt = (
        recent.groupby(["country", "league_id", "league"], as_index=False)
        .agg(
            seasons=("season", lambda s: f"{s.min()}-{s.max()}"),
            players=("players", "max"),
            stats_players=("stats_players", "max"),
            lineups=("lineups", "max"),
            top_scorers=("top_scorers", "max"),
        )
    )
    tgt["tier"] = tgt.apply(tier, axis=1)
    tgt.to_csv(OUT_TGT, index=False, encoding="utf-8")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 400)

    print(f"\n===== HEDEF ULKELERDEKI LIGLER ({len(tgt)}) -> {OUT_TGT} =====")
    t1 = tgt[tgt["tier"] == "T1"].sort_values(["country", "league"])
    print(f"\n--- T1: TAM SKORLANABILIR ({len(t1)} lig) ---")
    print(t1[["country", "league_id", "league", "seasons"]].to_string(index=False))

    t2 = tgt[tgt["tier"] == "T2"]
    print(f"\n--- T2: SINIRLI ({len(t2)} lig) --- (yalnizca kadro/gol seviyesi)")
    print(
        t2[t2["lineups"]][["country", "league_id", "league", "seasons"]]
        .sort_values(["country", "league"])
        .to_string(index=False)
    )
    print(f"\n--- T3: kapsam disi ({len(tgt[tgt['tier'] == 'T3'])} lig) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
