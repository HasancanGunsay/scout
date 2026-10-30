"""Akil saglig kontrolu: Brezilya Serie B 2024'te U21 havuzu.

Bu bir skorlama degil - sadece verinin mantikli olup olmadigini gorme testi.
Dogum tarihi ayristi mi, dakikalar makul mu, metrikler tutarli mi?
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)


def main() -> int:
    pd.set_option("display.width", 230)
    pd.set_option("display.max_rows", 60)
    con = duckdb.connect(str(DB), read_only=True)

    print("=" * 90)
    print("BREZILYA SERIE B 2024 - U21 HAVUZU (sezon sonunda 21 yas alti)")
    print("=" * 90)

    q = """
    WITH base AS (
      SELECT *,
             date_diff('year', birth_date, DATE '2024-12-31') AS yas_sezon_sonu,
             coalesce(goals,0)      AS g,
             coalesce(assists,0)    AS a,
             coalesce(shots,0)      AS sh,
             coalesce(key_passes,0) AS kp,
             coalesce(tackles,0)    AS tk,
             coalesce(dribbles_won,0) AS drb
      FROM player_season
      WHERE league_id = 72 AND season = 2024 AND birth_date IS NOT NULL
    )
    SELECT player_name AS oyuncu, yas_sezon_sonu AS yas, position AS mevki,
           team_name AS takim, apps AS mac, minutes AS dk, rating,
           g AS gol, a AS as, round((g+a)/nineties, 2) AS "g+a/90",
           round(sh/nineties, 2) AS "sut/90", round(kp/nineties, 2) AS "kilit/90",
           round(tk/nineties, 2) AS "calma/90", round(drb/nineties, 2) AS "drib/90"
    FROM base
    WHERE yas_sezon_sonu <= 21 AND minutes >= 900
    ORDER BY minutes DESC
    """
    df = con.sql(q).df()
    print(f"\n900+ dakika oynayan U21: {len(df)} oyuncu\n")
    print(df.to_string(index=False))

    print("\n" + "=" * 90)
    print("TUTARLILIK KONTROLLERI")
    print("=" * 90)
    checks = con.sql("""
      SELECT
        count(*)                                          AS satir,
        count(*) FILTER (WHERE birth_date IS NULL)        AS dogum_tarihi_yok,
        count(*) FILTER (WHERE minutes > apps*120)        AS "dk>mac*120 (imkansiz)",
        count(*) FILTER (WHERE starts > apps)             AS "ilk11>mac (imkansiz)",
        count(*) FILTER (WHERE rating < 3 OR rating > 10) AS rating_arali_disi,
        round(min(minutes))                               AS min_dk,
        round(max(minutes))                               AS max_dk,
        round(avg(minutes))                               AS ort_dk
      FROM player_season WHERE league_id = 72 AND season = 2024
    """).df()
    print(checks.T.to_string(header=False))

    print("\n--- yas dagilimi (Serie B 2024, 900+ dk) ---")
    print(con.sql("""
      SELECT date_diff('year', birth_date, DATE '2024-12-31') AS yas, count(*) AS n
      FROM player_season
      WHERE league_id=72 AND season=2024 AND minutes>=900 AND birth_date IS NOT NULL
      GROUP BY 1 ORDER BY 1
    """).df().to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
