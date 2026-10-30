"""Faz 1a / Adim 2: Transfermarkt veri setinin GERCEK kullanilabilirligi.

Uc soru:
  A) transfers tablosu lig gucu modeline (§5.2) yetecek mi?
  B) appearances hangi ligleri, hangi derinlikte kapsiyor?
  C) API-Football hic gelmese bu veriyle NE yapabiliriz?
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import tm_db_yolu  # noqa: E402
DB = tm_db_yolu()  # config/kaynaklar.yaml (FAZ 9.1)


def hr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def main() -> int:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 80)
    con = duckdb.connect(str(DB), read_only=True)

    hr("A1. transfers - sezona gore dagilim (neden sadece 4.345 tekil oyuncu?)")
    print(con.sql("""
        SELECT transfer_season AS sezon, count(*) AS transfer,
               count(DISTINCT player_id) AS oyuncu
        FROM transfers GROUP BY 1 ORDER BY 1 DESC LIMIT 15
    """).df().to_string(index=False))

    hr("A2. transfers - LIG DEGISTIREN transfer sayisi (modelin gercek yakiti)")
    print(con.sql("""
        WITH t AS (
          SELECT tr.player_id, tr.transfer_date,
                 cf.domestic_competition_id AS from_lig,
                 ct.domestic_competition_id AS to_lig
          FROM transfers tr
          LEFT JOIN clubs cf ON cf.club_id = tr.from_club_id
          LEFT JOIN clubs ct ON ct.club_id = tr.to_club_id
        )
        SELECT
          count(*) FILTER (WHERE from_lig IS NOT NULL AND to_lig IS NOT NULL) AS iki_lig_bilinen,
          count(*) FILTER (WHERE from_lig IS NOT NULL AND to_lig IS NOT NULL
                             AND from_lig <> to_lig)                          AS lig_degistiren,
          count(DISTINCT player_id) FILTER (WHERE from_lig IS NOT NULL AND to_lig IS NOT NULL
                             AND from_lig <> to_lig)                          AS tekil_oyuncu
        FROM t
    """).df().to_string(index=False))

    hr("B1. appearances - musabaka bazinda derinlik (son 3 sezon)")
    print(con.sql("""
        SELECT a.competition_id,
               coalesce(c.name, '(competitions tablosunda yok)') AS lig,
               coalesce(c.country_name, '-')                     AS ulke,
               count(*)                     AS katilim,
               count(DISTINCT a.player_id)  AS oyuncu,
               min(a.date) AS ilk, max(a.date) AS son
        FROM appearances a
        LEFT JOIN competitions c ON c.competition_id = a.competition_id
        WHERE a.date >= DATE '2023-07-01'
        GROUP BY 1,2,3 ORDER BY katilim DESC
    """).df().to_string(index=False))

    hr("C. 2025/26 sezonunda U21 oyuncu havuzu - LIG BAZINDA (sistemin ham maddesi)")
    print(con.sql("""
        SELECT c.country_name AS ulke, c.name AS lig,
               count(DISTINCT a.player_id) AS u21_oyuncu,
               round(sum(a.minutes_played)/60.0, 0) AS toplam_saat
        FROM appearances a
        JOIN players p     ON p.player_id = a.player_id
        JOIN competitions c ON c.competition_id = a.competition_id
        WHERE a.date >= DATE '2025-07-01'
          AND c.type = 'domestic_league'
          AND p.date_of_birth >= DATE '2004-07-01'
        GROUP BY 1,2 HAVING count(DISTINCT a.player_id) >= 5
        ORDER BY u21_oyuncu DESC
    """).df().to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
