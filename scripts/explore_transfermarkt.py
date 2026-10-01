"""Faz 1a / Adim 1: Transfermarkt CC0 veri setini kesfet.

Ne var, ne kadar var, hedef liglerimizi kapsiyor mu, lig gucu modeli (§5.2)
icin yeterli transfer ornegi var mi - hepsini olcer.

Salt okunur acar, veri setini degistirmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "raw" / "transfermarkt" / "2026-07-11" / "transfermarkt-datasets.duckdb"


def hr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> int:
    if not DB.exists():
        raise SystemExit(f"Veri seti yok: {DB}")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 120)
    pd.set_option("display.max_colwidth", 42)

    con = duckdb.connect(str(DB), read_only=True)

    hr("1. TABLOLAR")
    tables = con.sql("SHOW TABLES").df()["name"].tolist()
    rows = []
    for t in tables:
        n = con.sql(f'SELECT count(*) c FROM "{t}"').fetchone()[0]
        rows.append({"tablo": t, "satir": n})
    print(pd.DataFrame(rows).sort_values("satir", ascending=False).to_string(index=False))

    hr("2. SUTUNLAR (scout icin kritik tablolar)")
    for t in ["players", "competitions", "transfers", "player_valuations", "appearances"]:
        if t not in tables:
            print(f"\n-- {t}: TABLO YOK --")
            continue
        cols = con.sql(f'DESCRIBE "{t}"').df()
        print(f"\n-- {t} ({len(cols)} sutun) --")
        print(", ".join(cols["column_name"].tolist()))

    hr("3. MUSABAKA KAPSAMI")
    print(
        con.sql("""
        SELECT country_name AS ulke, competition_id, name AS lig, type, sub_type
        FROM competitions
        ORDER BY country_name, type, name
    """).df().to_string(index=False)
    )

    hr("4. OYUNCU KAPSAMI - yas dagilimi (wonderkid avi icin kritik)")
    print(
        con.sql("""
        SELECT
          count(*)                                              AS toplam_oyuncu,
          count(date_of_birth)                                  AS dogum_tarihi_var,
          round(100.0*count(date_of_birth)/count(*), 1)         AS dolu_pct,
          count(*) FILTER (WHERE date_of_birth >= DATE '2003-01-01') AS u23_dogumlu,
          count(*) FILTER (WHERE date_of_birth >= DATE '2005-01-01') AS u21_dogumlu,
          count(*) FILTER (WHERE market_value_in_eur IS NOT NULL)    AS piyasa_degeri_var,
          count(*) FILTER (WHERE contract_expiration_date IS NOT NULL) AS sozlesme_var
        FROM players
    """).df().to_string(index=False)
    )

    hr("5. LIG GUCU MODELI YAKITI - lig degistiren oyuncular (§5.2)")
    print(
        con.sql("""
        SELECT
          count(*)                          AS toplam_transfer,
          count(DISTINCT player_id)         AS tekil_oyuncu,
          min(transfer_date)                AS en_eski,
          max(transfer_date)                AS en_yeni
        FROM transfers
    """).df().to_string(index=False)
    )

    hr("6. APPEARANCES - performans verisi derinligi")
    if "appearances" in tables:
        print(
            con.sql("""
            SELECT
              count(*) AS satir,
              count(DISTINCT player_id) AS oyuncu,
              count(DISTINCT competition_id) AS musabaka,
              min(date) AS ilk, max(date) AS son
            FROM appearances
        """).df().to_string(index=False)
        )
        print("\n-- appearances ornek satir --")
        print(con.sql("SELECT * FROM appearances LIMIT 3").df().to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
