"""Faz 0 / Adim 1: FBref'in tanidigi TUM musabakalari listele.

Amac: hedef liglerimizin FBref'te hangi ISIM, hangi ID ve hangi SEZON
araligiyla durdugunu tahmin etmeden ogrenmek.

soccerdata'nin kendi indiricisini kullanir (duz httpx 403 yiyor), ham
leagues.html'i onbellekten okuyup FILTRESIZ parse eder.

Cikti: data/raw/fbref_comps.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from lxml import html as lxml_html

import soccerdata as sd
from soccerdata._config import DATA_DIR

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "fbref_comps.csv"
CACHED_HTML = Path(DATA_DIR) / "FBref" / "leagues.html"


def ensure_cache() -> Path:
    """leagues.html onbellekte yoksa soccerdata ile bir kez indir."""
    if CACHED_HTML.exists() and CACHED_HTML.stat().st_size > 10_000:
        print(f"[cache] {CACHED_HTML} ({CACHED_HTML.stat().st_size:,} bayt)")
        return CACHED_HTML

    print("[http]  leagues.html onbellekte yok, soccerdata ile indiriliyor...")
    fb = sd.FBref(leagues="FRA-Ligue 1", seasons="2024-2025")
    fb.read_leagues()  # yan etki: leagues.html'i onbellege yazar
    if not CACHED_HTML.exists():
        raise SystemExit(f"Beklenen onbellek dosyasi olusmadi: {CACHED_HTML}")
    print(f"[ok]    indirildi ({CACHED_HTML.stat().st_size:,} bayt)")
    return CACHED_HTML


def parse(path: Path) -> pd.DataFrame:
    tree = lxml_html.parse(str(path))

    rows = []
    for table in tree.xpath("//table[contains(@id, 'comps')]"):
        table_id = table.get("id", "")
        for tr in table.xpath(".//tbody/tr[not(contains(@class,'thead'))]"):
            cell = {}
            for c in tr.xpath("./th|./td"):
                cell[c.get("data-stat", "")] = " ".join(c.text_content().split())
            name = cell.get("league_name", "")
            if not name:
                continue
            hrefs = tr.xpath(".//th[@data-stat='league_name']/a/@href")
            url = hrefs[0] if hrefs else ""
            rows.append(
                {
                    "fbref_name": name,
                    "comp_id": url.split("/")[3] if url.count("/") >= 3 else "",
                    "url": url,
                    "gender": cell.get("gender", ""),
                    "country": cell.get("country", ""),
                    "tier": cell.get("tier", ""),
                    "governing_body": cell.get("governing_body", ""),
                    "first_season": cell.get("minseason", ""),
                    "last_season": cell.get("maxseason", ""),
                    "table_id": table_id,
                }
            )

    df = pd.DataFrame(rows).drop_duplicates(subset="fbref_name")
    return df.sort_values(["country", "tier", "fbref_name"]).reset_index(drop=True)


def main() -> int:
    df = parse(ensure_cache())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\n[ok]    {len(df)} musabaka -> {OUT}")

    # Kulup ligleri (kupa ve milli takim musabakalarini eliyoruz)
    league = df[
        df["table_id"].str.contains("club_league", na=False) & df["gender"].eq("M")
    ][["fbref_name", "comp_id", "country", "tier", "first_season", "last_season"]]

    pd.set_option("display.max_rows", 300)
    print(f"\n--- FBref'teki tum erkek kulup ligleri ({len(league)}) ---")
    print(league.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
