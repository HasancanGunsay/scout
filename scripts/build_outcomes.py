"""FAZ 1: gercek sonuc tablosu - skorladigimiz oyuncuya SONRADAN ne oldu.

    python scripts/build_outcomes.py

Iki is yapar:
  1) Transfermarkt mac verisini (appearances, games) ana veritabanina alir
     - 2022'den itibaren, ~651 bin satir
  2) player_outcome tablosunu uretir: her (oyuncu, lig, sezon) icin
     sezon bitisinden sonraki 12 ve 24 aylik dilimlerde ne oldugu

Ayrintili gerekce: src/scout/features/outcome.py ve PLAN §37.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.kaynaklar import db_yolu, tm_db_yolu  # noqa: E402

from scout.features.outcome import (ILK_BES, KADEME_ADI, TM_KARSILIGI,  # noqa: E402
                                    gozlem_ay, izlenen_ligler, kademe,
                                    kapsam, sezon_bitis)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
TM = tm_db_yolu()  # config/kaynaklar.yaml (FAZ 9.1)
BASLANGIC = "2022-01-01"


def mac_verisini_al(con) -> None:
    """appearances + games + competitions -> ana veritabani."""
    con.execute(f"ATTACH '{TM}' AS tm (READ_ONLY)")

    con.execute(f"""
        CREATE OR REPLACE TABLE tm_appearances AS
        SELECT a.player_id, a.game_id, a.player_club_id, a.date,
               a.competition_id, a.minutes_played, a.goals, a.assists,
               a.yellow_cards, a.red_cards
        FROM tm.appearances a
        WHERE a.date >= DATE '{BASLANGIC}'
    """)
    n_app = con.sql("SELECT count(*) n FROM tm_appearances").df().n[0]

    con.execute(f"""
        CREATE OR REPLACE TABLE tm_games AS
        SELECT game_id, competition_id, season, round, date,
               home_club_id, away_club_id, home_club_goals, away_club_goals
        FROM tm.games WHERE date >= DATE '{BASLANGIC}'
    """)
    n_gm = con.sql("SELECT count(*) n FROM tm_games").df().n[0]

    con.execute("""
        CREATE OR REPLACE TABLE tm_competitions_full AS
        SELECT competition_id, name, type, sub_type, country_name
        FROM tm.competitions
    """)
    con.execute("DETACH tm")
    print(f"[1]    tm_appearances {n_app:,} · tm_games {n_gm:,}")


def sonuclari_uret(con) -> pd.DataFrame:
    """Her (oyuncu, lig, sezon) icin sonraki 24 ayda ne oldu."""
    # Skorladigimiz oyuncu-sezonlar (TM kimligi eslesmis olanlar)
    baz = con.sql("""
        SELECT DISTINCT n.player_id, n.league_id, n.season, n.country,
               n.league_name, n.player_name, n.age_season_end, n.minutes,
               n.score, l.tm_id
        FROM player_natural_role n
        JOIN player_links l USING (player_id)
        WHERE l.tm_id IS NOT NULL
    """).df()
    print(f"[2]    {len(baz):,} oyuncu-sezon (TM kimligi eslesmis)")

    # Sezon bitis tarihi - TM'nin sezon etiketi KULLANILMIYOR (bkz. outcome.py)
    baz["sezon_bitis"] = [sezon_bitis(c, s)
                          for c, s in zip(baz.country, baz.season)]
    con.register("baz", baz)

    # Yalnizca BIRINCI LIG dakikalari seviye olcusune girer.
    # Kupa ve Avrupa dakikalari ayri tutulur: guclu bir isaret ama
    # "yer edindi" sorusunun cevabi degil.
    con.execute("""
        CREATE OR REPLACE TEMP TABLE gorunum AS
        SELECT b.player_id, b.league_id, b.season,
               a.competition_id, a.minutes_played, a.goals, a.assists,
               c.type AS comp_type,
               CASE WHEN a.date <= b.sezon_bitis + INTERVAL 12 MONTH THEN 1
                    ELSE 2 END AS dilim
        FROM baz b
        JOIN tm_appearances a ON a.player_id = b.tm_id
        JOIN tm_competitions_full c ON c.competition_id = a.competition_id
        WHERE a.date > b.sezon_bitis
          AND a.date <= b.sezon_bitis + INTERVAL 24 MONTH
    """)

    ozet = con.sql("""
        SELECT player_id, league_id, season, dilim, competition_id,
               sum(minutes_played) dk, sum(goals) gol, sum(assists) asist
        FROM gorunum WHERE comp_type = 'domestic_league'
        GROUP BY 1,2,3,4,5
    """).df()

    kupa = con.sql("""
        SELECT player_id, league_id, season,
               sum(minutes_played) kupa_dk
        FROM gorunum WHERE comp_type <> 'domestic_league'
        GROUP BY 1,2,3
    """).df()

    # Her dilimde EN COK oynadigi birinci lig - kademe ondan hesaplanir
    if len(ozet):
        # Esitlik kurali ACIK (30 Eki 2026): yalniz "dk" ile siralama esit
        # dakikada ligi rastgele seciyordu - ayni veriden 4 calistirmanin
        # birinde oyuncu 503702'nin ligi FR1/BE1 arasinda degisti. Lig ilk-5
        # mi degil mi kademeyi (3/4) belirledigi icin bu yalniz etiket degil.
        # Sira: cok dakika > guclu lig (ilk-5) > lig kodu.
        ozet = ozet.assign(_ilk5=ozet.competition_id.isin(ILK_BES)).sort_values(
            ["dk", "_ilk5", "competition_id"], ascending=[False, False, True],
            kind="mergesort").drop(columns="_ilk5")
        en_iyi = ozet.drop_duplicates(["player_id", "league_id", "season", "dilim"])
        toplam = (ozet.groupby(["player_id", "league_id", "season", "dilim"],
                               as_index=False)
                      .agg(lig_dk=("dk", "sum"), gol=("gol", "sum"),
                           asist=("asist", "sum")))
        en_iyi = en_iyi[["player_id", "league_id", "season", "dilim",
                         "competition_id"]].merge(
            toplam, on=["player_id", "league_id", "season", "dilim"])
    else:
        en_iyi = pd.DataFrame(columns=["player_id", "league_id", "season",
                                       "dilim", "competition_id", "lig_dk",
                                       "gol", "asist"])

    en_iyi["kademe"] = [kademe(d, c in ILK_BES)
                        for d, c in zip(en_iyi.lig_dk, en_iyi.competition_id)]

    # iki dilimi yan yana koy
    genis = en_iyi.pivot_table(
        index=["player_id", "league_id", "season"], columns="dilim",
        values=["lig_dk", "kademe", "gol"], aggfunc="first")
    genis.columns = [f"{a}_y{int(b)}" for a, b in genis.columns]
    genis = genis.reset_index()

    out = baz.merge(genis, on=["player_id", "league_id", "season"], how="left")
    out = out.merge(kupa, on=["player_id", "league_id", "season"], how="left")

    for c in ["lig_dk_y1", "lig_dk_y2", "gol_y1", "gol_y2", "kupa_dk"]:
        if c not in out.columns:
            out[c] = 0.0
        out[c] = out[c].fillna(0.0)
    for c in ["kademe_y1", "kademe_y2"]:
        if c not in out.columns:
            out[c] = 0
        out[c] = out[c].fillna(0).astype(int)

    # --- SANSURLEME (bkz. outcome.py) ---------------------------------
    # Birincil sonuc 12 AYLIK dilim: her sezon icin tam, kiyaslanabilir.
    # max(y1, y2) kullanmak 2022'ye iki sans, 2024'e bir sans verirdi ve
    # model bundan "eski sezonlar daha basarili" diye ogrenirdi.
    veri_sonu = con.sql("SELECT max(date) d FROM tm_appearances").df().d[0].date()
    out["gozlem_ay"] = [round(gozlem_ay(b, veri_sonu), 1) for b in out.sezon_bitis]
    out["y2_tam"] = out.gozlem_ay >= 24

    out["kademe"] = out.kademe_y1                      # BIRINCIL
    out["kademe_24ay"] = out[["kademe_y1", "kademe_y2"]].max(axis=1)
    out.loc[~out.y2_tam, "kademe_24ay"] = None         # sansurluyse URETME
    eksik = int((~out.y2_tam).sum())
    print(f"[2b]   {eksik:,} satirda 24 aylik pencere tamamlanmamis - "
          f"kademe_24ay NULL birakildi (birincil sonuc 12 aylik)")
    # Esitlik kurali ACIK (30 Eki 2026): yalniz "kademe"ye gore siralamak
    # esitlikleri kararsiz biraktigi icin ayni veriden iki calistirmada 3
    # oyuncunun en_iyi_lig etiketi degisti (kademe degil, yalniz etiket).
    # Sira: yuksek kademe > ilk 12 ay > cok dakika > lig kodu.
    out["en_iyi_lig"] = en_iyi.sort_values(
        ["kademe", "dilim", "lig_dk", "competition_id"],
        ascending=[False, True, False, True], kind="mergesort") \
        .drop_duplicates(["player_id", "league_id", "season"]) \
        .set_index(["player_id", "league_id", "season"]).competition_id \
        .reindex(pd.MultiIndex.from_frame(
            out[["player_id", "league_id", "season"]])).values

    # Mensei TM'nin GERCEKTEN oyuncu kaydi tuttugu bir lig mi?
    out["mense_tm_ligi"] = out.league_id.map(TM_KARSILIGI)
    out["kapsam"] = out.league_id.map(kapsam)
    out["izlenmeyen_ligden"] = out.mense_tm_ligi.isna()

    # Sabit listeyi veriyle KARSILASTIR - veri seti guncellenince liste
    # bayatlayabilir ve bunu kimse fark etmez.
    app = con.sql("SELECT competition_id FROM tm_appearances").df()
    comp = con.sql("SELECT competition_id, type FROM tm_competitions_full").df()
    gercek = izlenen_ligler(app, comp)
    beklenen = {v for v in TM_KARSILIGI.values() if v}
    if not beklenen <= gercek:
        print(f"  ! UYARI: TM_KARSILIGI'nda izlenen sayilan ama veride "
              f"olmayan lig var: {sorted(beklenen - gercek)}")
    print(f"[2c]   veride oyuncu kaydi olan birinci lig: {len(gercek)} "
          f"({', '.join(sorted(gercek))})")
    return out


def main() -> int:
    con = duckdb.connect(str(DB))
    mac_verisini_al(con)
    out = sonuclari_uret(con)

    con.execute("CREATE OR REPLACE TABLE player_outcome AS SELECT * FROM out")
    print(f"[3]    player_outcome: {len(out):,} satir\n")

    pd.set_option("display.width", 215)

    print("--- kademe dagilimi ---")
    d = out.kademe.value_counts().sort_index().rename("n").reset_index()
    d.columns = ["kademe", "n"]
    d["ad"] = d.kademe.map(KADEME_ADI)
    d["pay"] = (100 * d.n / len(out)).round(1)
    print(d.to_string(index=False))

    print("\n--- gozlem penceresi (sansurleme) ---")
    print(out.groupby("season").agg(
        n=("player_id", "size"), ort_gozlem_ay=("gozlem_ay", "mean"),
        y2_tam=("y2_tam", "sum")).round(1).to_string())

    print("\n=== KAPSAM 'TAM': mensei izlenen lig, KALMAK da gorunur ===")
    tam = out[(out.kapsam == "tam") & (out.minutes >= 450)]
    tt = (tam.groupby(["league_id", "league_name"])
             .agg(n=("player_id", "size"), ort_kademe=("kademe", "mean"),
                  yer_edindi_pct=("kademe", lambda s: 100 * (s >= 3).mean()))
             .round(2).reset_index())
    print(tt.sort_values("ort_kademe", ascending=False).to_string(index=False))

    print("\n=== KAPSAM 'SICRAMA_ONLY': yalnizca 14 izlenen lige gecen gorunur ===")
    print("    DIKKAT: kademe 0 'basarisiz' DEMEK DEGIL. Brezilya Serie B'den")
    print("    Brezilya Serie A'ya cikmak gercek bir sicramadir ama TM'de")
    print("    oyuncu kaydi olmadigi icin GORUNMEZ (bkz. outcome.py).")
    alt = out[(out.kapsam == "sicrama_only") & (out.minutes >= 450)]
    t = (alt.groupby(["league_id", "league_name"])
            .agg(n=("player_id", "size"), ort_kademe=("kademe", "mean"),
                 sicrama_pct=("kademe", lambda s: 100 * (s >= 3).mean()))
            .round(2).reset_index())
    print(t.sort_values("sicrama_pct", ascending=False).to_string(index=False))

    print("\n--- sicrayanlar nereye gitti? ---")
    print(alt[alt.kademe >= 3].en_iyi_lig.value_counts().head(12).to_string())

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
