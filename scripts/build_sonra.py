"""FAZ 6.4a: "sonra ne yapti" tablosu (player_sonra).

    python scripts/build_sonra.py

Her (oyuncu, lig, sezon) icin sezon bitisinden sonraki 12 ay:
  mac_lig / ilk11_lig / dk_lig / gol_lig / asist_lig  (birinci lig, TM)
  mac_tum / ilk11_tum / dk_tum                          (kupa + Avrupa dahil)
  ga90                                                   ((gol+asist)/dk*90, dk>=450)
  deger_bas / deger_son / deger_degisim / deger_oran     (TM degerleme yorungesi)
  kulup_degisti (mac kaydindan) / bilinen_bedel (KISMI)

DURUSTLUK NOTLARI (arayuzde de gosterilir)
1) RATING YOK. API rating'i yalniz 2022-2024 sezonlarinda; sonraki donem icin
   yok. "Kac puanla oynadi" OLCULEMEZ; yerine dakika, ilk 11, gol+asist,
   deger degisimi.
2) TM birinci ligleri yalniz 14 lig. Izlenmeyen ligde oynamaya devam eden
   oyuncu "mac yok" gorunur - basarisizlik DEGIL. mac_* NULL'u 0'dan AYRI
   tutulur ('kayit yok' != '0 mac').
3) Deger yorungesi tum kulupleri kapsar (izlenmeyen ligler dahil): izlenen
   ligde %78, izlenmeyende %33 oraninda sonrasi icin degerleme var. Degerleme
   yoksa deger_degisim NULL - 0 degil.
4) transfers tablosu EKSIK (izlenen ligde kulup degistiren 350 oyuncunun
   yalniz %9'u kayitli) ve 2030'a kadar tarihli kayit iceriyor. Bu yuzden
   'transfer oldu mu' mac kayitlarindan turetilir (kulup_degisti); tablodan
   yalniz 'bilinen_bedel' alinir ve KISMI oldugu belirtilir. Veri tarihiyle
   kirpilir.
5) Pencere sansuru: gozlem_ay < 12 ise pencere_tam=False.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.kaynaklar import db_yolu, tm_db_yolu  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
TM = tm_db_yolu()  # config/kaynaklar.yaml (FAZ 9.1)
BASLANGIC = "2022-01-01"


def lineups_al(con) -> None:
    con.execute(f"ATTACH '{TM}' AS tm (READ_ONLY)")
    con.execute(f"""
        CREATE OR REPLACE TABLE tm_lineups AS
        SELECT player_id, game_id, date, type
        FROM tm.game_lineups WHERE date >= DATE '{BASLANGIC}'""")
    n = con.sql("SELECT count(*) FROM tm_lineups").fetchone()[0]
    con.execute("DETACH tm")
    print(f"[1] tm_lineups {n:,}")


def uret(con) -> pd.DataFrame:
    veri_sonu = con.sql("SELECT max(date) FROM tm_appearances").fetchone()[0]
    con.execute("""
        CREATE OR REPLACE TEMP TABLE b AS
        SELECT o.player_id, o.league_id, o.season, l.tm_id,
               CAST(o.sezon_bitis AS DATE) AS bitis, o.gozlem_ay
        FROM player_outcome o JOIN player_links l USING (player_id)""")

    K = ["player_id", "league_id", "season"]

    mac = con.sql("""
        SELECT b.player_id, b.league_id, b.season,
               count(*) FILTER (WHERE c.type='domestic_league') AS mac_lig,
               count(*) AS mac_tum,
               sum(a.minutes_played) FILTER (WHERE c.type='domestic_league') AS dk_lig,
               sum(a.goals)   FILTER (WHERE c.type='domestic_league') AS gol_lig,
               sum(a.assists) FILTER (WHERE c.type='domestic_league') AS asist_lig,
               sum(a.minutes_played) AS dk_tum
        FROM b JOIN tm_appearances a
          ON a.player_id=b.tm_id AND a.date > b.bitis
         AND a.date <= b.bitis + INTERVAL 12 MONTH
        JOIN tm_competitions_full c ON c.competition_id=a.competition_id
        GROUP BY 1,2,3""").df()

    ilk11 = con.sql("""
        SELECT b.player_id, b.league_id, b.season,
               count(*) FILTER (WHERE g.type='starting_lineup'
                                AND c.type='domestic_league') AS ilk11_lig,
               count(*) FILTER (WHERE g.type='starting_lineup') AS ilk11_tum
        FROM b JOIN tm_lineups g
          ON g.player_id=b.tm_id AND g.date > b.bitis
         AND g.date <= b.bitis + INTERVAL 12 MONTH
        JOIN tm_games gm ON gm.game_id=g.game_id
        JOIN tm_competitions_full c ON c.competition_id=gm.competition_id
        GROUP BY 1,2,3""").df()

    dbas = con.sql("""
        SELECT b.player_id, b.league_id, b.season,
               max_by(v.market_value_in_eur, v.date) AS deger_bas
        FROM b JOIN tm_player_valuations v
          ON v.player_id=b.tm_id AND v.date <= b.bitis
        GROUP BY 1,2,3""").df()
    dson = con.sql("""
        SELECT b.player_id, b.league_id, b.season,
               max_by(v.market_value_in_eur, v.date) AS deger_son
        FROM b JOIN tm_player_valuations v
          ON v.player_id=b.tm_id AND v.date > b.bitis
         AND v.date <= b.bitis + INTERVAL 12 MONTH
        GROUP BY 1,2,3""").df()

    # KULUP DEGISIMI mac kayitlarindan turetilir. tm_transfers TABLOSU EKSIK:
    # olculdu (30 Eyl 2026) - izlenen ligdeki U23'lerde mac kayitlarina gore
    # kulup degistiren 350 oyuncunun yalniz 32'si (%9) transfers tablosunda.
    # 'transfer_var' bu yuzden "transfer olmadi" diye YANLIS bilgi verirdi.
    kul = con.sql("""
        WITH once AS (
          SELECT b.player_id, b.league_id, b.season,
                 max_by(a.player_club_id, a.date) AS kulup_once
          FROM b JOIN tm_appearances a
            ON a.player_id=b.tm_id AND a.date <= b.bitis
           AND a.date > b.bitis - INTERVAL 12 MONTH
          GROUP BY 1,2,3),
        sonra AS (
          SELECT b.player_id, b.league_id, b.season,
                 min_by(a.player_club_id, a.date) AS kulup_sonra
          FROM b JOIN tm_appearances a
            ON a.player_id=b.tm_id AND a.date > b.bitis
           AND a.date <= b.bitis + INTERVAL 12 MONTH
          GROUP BY 1,2,3)
        SELECT player_id, league_id, season,
               kulup_once <> kulup_sonra AS kulup_degisti
        FROM once JOIN sonra USING (player_id, league_id, season)""").df()

    # Bilinen bedel: KISMI. Yalniz tm_transfers'ta kayitli olanlar; bos = "bilinmiyor".
    # Veri tarihiyle kirpilir (dosya 2030'a kadar tarihli kayit iceriyor).
    tr = con.sql(f"""
        SELECT b.player_id, b.league_id, b.season,
               max(t.transfer_fee) AS bilinen_bedel
        FROM b JOIN tm_transfers t
          ON t.player_id=b.tm_id AND t.transfer_date > b.bitis
         AND t.transfer_date <= b.bitis + INTERVAL 12 MONTH
         AND t.transfer_date <= DATE '{str(veri_sonu)[:10]}'
        GROUP BY 1,2,3""").df()

    out = con.sql("SELECT player_id, league_id, season, tm_id, bitis, gozlem_ay "
                  "FROM b").df()
    for t in (mac, ilk11, dbas, dson, kul, tr):
        out = out.merge(t, on=K, how="left")

    out["pencere_tam"] = out.gozlem_ay >= 12
    # 'kayit yok' (NaN) 0 DEGIL: yalniz oynamis olanlarin sayaclari dolu;
    # oynamayanlarda NULL kalir ve arayuz 'iz yok' der.
    out["ga90"] = ((out.gol_lig.fillna(0) + out.asist_lig.fillna(0))
                   / out.dk_lig * 90).where(out.dk_lig >= 450)
    out["deger_degisim"] = out.deger_son - out.deger_bas
    out["deger_oran"] = (out.deger_son / out.deger_bas - 1).where(
        out.deger_bas > 0)
    return out


def main() -> int:
    con = duckdb.connect(str(DB))
    lineups_al(con)
    d = uret(con)
    con.register("d", d)
    con.execute("CREATE OR REPLACE TABLE player_sonra AS SELECT * FROM d")
    print(f"[2] player_sonra: {len(d):,} satir")

    print("\n--- kapsam (U23 orijinler, pencere tam) ---")
    x = con.sql("""
        SELECT o.kapsam, count(*) n,
               round(100.0*avg(CASE WHEN s.mac_lig>0 THEN 1 ELSE 0 END),1) mac_var_pct,
               round(100.0*avg(CASE WHEN s.ilk11_lig>0 THEN 1 ELSE 0 END),1) ilk11_var_pct,
               round(100.0*avg(CASE WHEN s.deger_son IS NOT NULL THEN 1 ELSE 0 END),1) deger_son_var_pct,
               round(100.0*avg(CASE WHEN s.kulup_degisti THEN 1 ELSE 0 END),1) kulup_degisti_pct
        FROM player_outcome o JOIN player_sonra s USING (player_id, league_id, season)
        WHERE o.age_season_end<23 AND o.minutes>=450 AND s.pencere_tam
        GROUP BY 1""").df()
    print(x.to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
