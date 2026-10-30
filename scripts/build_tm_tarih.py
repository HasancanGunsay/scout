"""FAZ 7.1: Transfermarkt tarihsel oyuncu-sezon tablosu (2012-2025).

    python scripts/build_tm_tarih.py            # tabloyu kur + saglama
    python scripts/build_tm_tarih.py --saglama  # yalniz saglama

Cikti: tm_oyuncu_sezon - her (oyuncu, lig, sezon) icin YALNIZ TM verisinden
ozellikler + mevcut sistemle AYNI tanimli sonuc (12 ay, kademe).
Tum yaslar tutulur (kohort yuzdelikleri icin); U23 filtresi modelde.

MUHUR: 2018-2021 sonuclarina bu betik BAKMAZ. Saglama ciktisinda bu
sezonlar icin yalnizca satir sayisi basilir, oran basilmaz (bkz. tm_tarih.py).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.kaynaklar import db_yolu, tm_db_yolu  # noqa: E402

from scout.features.outcome import (ILK_BES, PENCERE_AY, gozlem_ay,  # noqa: E402
                                    izlenen_ligler, kademe, sezon_bitis)
from scout.features.tm_tarih import (INCE_MEVKI, KABA_YEDEK, MUHURLU_TEST,  # noqa: E402
                                     SAHADA_YOK, bolum)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
HAM = tm_db_yolu()  # config/kaynaklar.yaml (FAZ 9.1)
ILK_SEZON, SON_SEZON = 2012, 2025
ANAHTAR = ["player_id", "comp", "season"]


def ligleri_bul(con) -> list[str]:
    """Izlenen ligler sabit liste DEGIL, veriden (outcome.izlenen_ligler)."""
    app = con.sql("SELECT competition_id FROM r.appearances").df()
    comp = con.sql("SELECT competition_id, type FROM r.competitions").df()
    return sorted(izlenen_ligler(app, comp))


def mac_tablolari(con, ligler: list[str]) -> None:
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE m AS
        SELECT CAST(game_id AS INT) game_id, CAST(season AS INT) season,
               competition_id comp, date,
               home_club_id, away_club_id, home_club_goals, away_club_goals
        FROM r.games
        WHERE competition_id IN ({",".join(f"'{l}'" for l in ligler)})
          AND CAST(season AS INT) BETWEEN {ILK_SEZON} AND {SON_SEZON}""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE ap AS
        SELECT a.player_id, a.game_id, a.player_club_id club_id,
               a.minutes_played dk, a.goals, a.assists, a.yellow_cards,
               a.red_cards, m.season, m.comp
        FROM r.appearances a JOIN m USING (game_id)""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE ilk AS
        SELECT game_id, player_id, any_value(position) pos
        FROM r.game_lineups
        WHERE type = 'starting_lineup' AND game_id IN (SELECT game_id FROM m)
        GROUP BY 1, 2""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE olay AS
        SELECT CAST(game_id AS INT) game_id, type, club_id, player_id,
               player_in_id, greatest(minute, 1) dak, description
        FROM r.game_events
        WHERE TRY_CAST(game_id AS INT) IN (SELECT game_id FROM m)""")


def sure_ve_arti_eksi(con) -> None:
    """Her (mac, oyuncu): sahaya giris/cikis dakikasi ve sahadayken goller.

    giris: ilk 11 ise 0, degilse oyuna girdigi dakika (yoksa NULL = bilinmiyor)
    cikis: oyundan cikis ya da kirmizi kart dakikasi, yoksa SAHADA_YOK
    Gol sayimi tm_tarih.sahada_mi ile ayni kural: giris < dakika <= cikis.
    """
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE sure AS
        SELECT ap.game_id, ap.player_id, ap.club_id,
               i.player_id IS NOT NULL AS basladi,
               CASE WHEN i.player_id IS NOT NULL THEN 0 ELSE gi.dak END AS giris,
               least(coalesce(co.dak, {SAHADA_YOK}),
                     coalesce(k.dak, {SAHADA_YOK})) AS cikis,
               co.dak IS NOT NULL AS oyundan_cikti
        FROM ap
        LEFT JOIN ilk i USING (game_id, player_id)
        LEFT JOIN (SELECT game_id, player_in_id player_id, min(dak) dak
                   FROM olay WHERE type = 'Substitutions' GROUP BY 1, 2) gi
               USING (game_id, player_id)
        LEFT JOIN (SELECT game_id, player_id, min(dak) dak
                   FROM olay WHERE type = 'Substitutions' GROUP BY 1, 2) co
               USING (game_id, player_id)
        LEFT JOIN (SELECT game_id, player_id, min(dak) dak FROM olay
                   WHERE type = 'Cards' AND (description ILIKE '%red card%'
                                             OR description ILIKE '%second yellow%')
                   GROUP BY 1, 2) k
               USING (game_id, player_id)""")
    # club_id = golun LEHINE yazildigi takim (olculdu: %99,9; kendi kalesine
    # gol de lehine yazilan takimda) - isaret cevirmeye gerek yok
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sahada AS
        SELECT s.game_id, s.player_id,
               sum(CASE WHEN g.club_id = s.club_id THEN 1 ELSE 0 END) gf_on,
               sum(CASE WHEN g.club_id <> s.club_id THEN 1 ELSE 0 END) ga_on
        FROM sure s
        JOIN olay g ON g.game_id = s.game_id AND g.type = 'Goals'
                   AND g.dak > s.giris AND g.dak <= s.cikis
        WHERE s.giris IS NOT NULL
        GROUP BY 1, 2""")


def takim_gucu(con) -> None:
    con.execute("""
        CREATE OR REPLACE TEMP TABLE takim AS
        WITH t AS (
            SELECT season, comp, home_club_id club_id, home_club_goals gf,
                   away_club_goals ga FROM m
            UNION ALL
            SELECT season, comp, away_club_id, away_club_goals, home_club_goals
            FROM m)
        SELECT season, comp, club_id, count(*) takim_mac,
               avg(CASE WHEN gf > ga THEN 3 WHEN gf = ga THEN 1 ELSE 0 END) takim_ppg,
               avg(gf) takim_gf90, avg(ga) takim_ga90
        FROM t GROUP BY 1, 2, 3""")


def oyuncu_sezon(con) -> pd.DataFrame:
    mev = pd.DataFrame([(k, v[0]) for k, v in INCE_MEVKI.items()],
                       columns=["pos", "ince"])
    con.register("mev", mev)
    return con.sql(f"""
        WITH mac AS (
            SELECT ap.*, s.basladi, s.giris, s.cikis, s.oyundan_cikti,
                   coalesce(h.gf_on, 0) gf_on, coalesce(h.ga_on, 0) ga_on,
                   i.pos
            FROM ap
            JOIN sure s USING (game_id, player_id)
            LEFT JOIN sahada h USING (game_id, player_id)
            LEFT JOIN ilk i USING (game_id, player_id)),
        kulup AS (       -- oyuncu x kulup: takim gucu dakikayla agirliklanir
            SELECT player_id, comp, season, club_id, sum(dk) dk_k
            FROM mac GROUP BY 1, 2, 3, 4),
        kul AS (
            SELECT k.player_id, k.comp, k.season,
                   sum(t.takim_mac) takim_mac,
                   sum(t.takim_ppg * k.dk_k) / nullif(sum(k.dk_k), 0) takim_ppg,
                   sum(t.takim_gf90 * k.dk_k) / nullif(sum(k.dk_k), 0) takim_gf90,
                   sum(t.takim_ga90 * k.dk_k) / nullif(sum(k.dk_k), 0) takim_ga90,
                   arg_max(k.club_id, k.dk_k) club_id,
                   count(*) kulup_sayisi
            FROM kulup k JOIN takim t USING (season, comp, club_id)
            GROUP BY 1, 2, 3),
        mevki AS (       -- o sezon ILK 11'de en cok oynadigi mevki
            SELECT player_id, comp, season, arg_max(pos, n) pos,
                   max(n) / sum(n) mevki_payi
            FROM (SELECT player_id, comp, season, pos, count(*) n FROM mac
                  WHERE basladi AND pos IS NOT NULL GROUP BY 1, 2, 3, 4)
            GROUP BY 1, 2, 3)
        SELECT mac.player_id, mac.comp, mac.season,
               sum(dk) dk, count(*) mac, sum(basladi::INT) ilk11,
               sum((NOT basladi AND giris IS NOT NULL)::INT) yedek_giris,
               sum((basladi AND oyundan_cikti)::INT) oyundan_cikti,
               sum((basladi AND cikis = {SAHADA_YOK})::INT) tam_mac,
               sum(goals) gol, sum(assists) asist,
               sum(yellow_cards) sari, sum(red_cards) kirmizi,
               sum(CASE WHEN giris IS NOT NULL THEN dk END) dk_pm,
               sum(CASE WHEN giris IS NOT NULL THEN gf_on END) gf_on,
               sum(CASE WHEN giris IS NOT NULL THEN ga_on END) ga_on,
               any_value(kul.takim_mac) takim_mac,
               any_value(kul.takim_ppg) takim_ppg,
               any_value(kul.takim_gf90) takim_gf90,
               any_value(kul.takim_ga90) takim_ga90,
               any_value(kul.club_id) club_id,
               any_value(kul.kulup_sayisi) kulup_sayisi,
               any_value(mevki.pos) lineup_pos,
               any_value(mevki.mevki_payi) mevki_payi
        FROM mac
        LEFT JOIN kul USING (player_id, comp, season)
        LEFT JOIN mevki USING (player_id, comp, season)
        GROUP BY 1, 2, 3""").df()


def oyuncu_bilgisi(con, d: pd.DataFrame) -> pd.DataFrame:
    p = con.sql("""SELECT player_id, name player_name, date_of_birth,
                          position guncel_pos, height_in_cm boy, foot ayak
                   FROM r.players""").df()
    d = d.merge(p, on="player_id", how="left")
    # TM'nin 14 ligi sonbahar-ilkbahar: sezon S, S+1 Haziran'da biter
    d["sezon_bitis"] = [sezon_bitis("England", s) for s in d.season]
    dob = pd.to_datetime(d.date_of_birth)
    d["yas"] = (pd.to_datetime(d.sezon_bitis) - dob).dt.days / 365.25
    d.loc[(d.yas < 14) | (d.yas > 60), "yas"] = np.nan    # imkansiz dogum tarihi
    ince = {k: v[0] for k, v in INCE_MEVKI.items()}
    kaba = {k: v[1] for k, v in INCE_MEVKI.items()}
    d["ince_mevki"] = d.lineup_pos.map(ince)
    d["pos_group"] = d.lineup_pos.map(kaba).fillna(d.guncel_pos.map(KABA_YEDEK))
    d["mevki_kaynagi"] = np.where(d.lineup_pos.map(kaba).notna(), "kadro",
                                  np.where(d.pos_group.notna(), "guncel", "yok"))
    return d.drop(columns=["date_of_birth"])


def piyasa_degeri(con, d: pd.DataFrame) -> pd.DataFrame:
    """Sezon bitisinden 1 ay onceki son deger (mevcut sistemle ayni kural)."""
    k = d[["player_id", "season", "sezon_bitis"]].drop_duplicates(
        ["player_id", "season"])
    con.register("k", k)
    v = con.sql("""
        SELECT k.player_id, k.season,
               max_by(v.market_value_in_eur, v.date) deger
        FROM k JOIN r.player_valuations v
          ON v.player_id = k.player_id
         AND v.date <= k.sezon_bitis - INTERVAL 1 MONTH
        GROUP BY 1, 2""").df()
    d = d.merge(v, on=["player_id", "season"], how="left")
    d["deger_var"] = d.deger.notna().astype(int)
    return d


def onceki_sezon(d: pd.DataFrame) -> pd.DataFrame:
    """Yorunge: bir onceki sezon 14 ligdeki toplam dakika ve dakika payi."""
    t = (d.groupby(["player_id", "season"], as_index=False)
          .agg(dk_t=("dk", "sum"), takim_mac_t=("takim_mac", "sum")))
    t["season"] += 1
    t = t.rename(columns={"dk_t": "dk_onceki", "takim_mac_t": "takim_mac_onceki"})
    d = d.merge(t, on=["player_id", "season"], how="left")
    d["onceki_sezon_var"] = d.dk_onceki.notna().astype(int)
    d["dk_onceki"] = d.dk_onceki.fillna(0.0)
    d["dakika_payi_onceki"] = (d.dk_onceki / (90 * d.takim_mac_onceki)).fillna(0.0)
    d.loc[d.season == ILK_SEZON, ["dk_onceki", "dakika_payi_onceki",
                                  "onceki_sezon_var"]] = np.nan   # bilinmiyor
    return d.drop(columns=["takim_mac_onceki"])


def sonuc(con, d: pd.DataFrame) -> pd.DataFrame:
    """Mevcut sistemle (build_outcomes) AYNI tanim: sezon bitisinden sonraki
    12 ayda 14 ligdeki toplam lig dakikasi; kademe, en cok oynanan lig
    ilk-5 mi diye bakar."""
    k = d[["player_id", "season", "sezon_bitis"]].drop_duplicates(
        ["player_id", "season"])
    con.register("k2", k)
    w = con.sql(f"""
        SELECT k.player_id, k.season, a.competition_id, sum(a.minutes_played) dk
        FROM k2 k
        JOIN r.appearances a ON a.player_id = k.player_id
         AND a.date > k.sezon_bitis
         AND a.date <= k.sezon_bitis + INTERVAL {PENCERE_AY} MONTH
        JOIN r.competitions c ON c.competition_id = a.competition_id
                             AND c.type = 'domestic_league'
        GROUP BY 1, 2, 3""").df()
    w = w.sort_values("dk", ascending=False)
    en_cok = w.drop_duplicates(["player_id", "season"])[
        ["player_id", "season", "competition_id"]]
    top = w.groupby(["player_id", "season"], as_index=False).dk.sum()
    s = top.merge(en_cok, on=["player_id", "season"]).rename(
        columns={"dk": "lig_dk_sonra", "competition_id": "en_iyi_lig"})
    d = d.merge(s, on=["player_id", "season"], how="left")
    d["lig_dk_sonra"] = d.lig_dk_sonra.fillna(0.0)
    d["kademe"] = [kademe(m, c in ILK_BES)
                   for m, c in zip(d.lig_dk_sonra, d.en_iyi_lig)]
    veri_sonu = con.sql("SELECT max(date) FROM r.appearances").fetchone()[0]
    d["gozlem_ay"] = [round(gozlem_ay(b, veri_sonu), 1) for b in d.sezon_bitis]
    d["pencere_tam"] = d.gozlem_ay >= PENCERE_AY
    d.loc[~d.pencere_tam, ["kademe", "lig_dk_sonra", "en_iyi_lig"]] = None
    return d


def turet(d: pd.DataFrame) -> pd.DataFrame:
    """Oranlar - ham sayilar da tablodadir."""
    d["dakika_payi"] = d.dk / (90 * d.takim_mac)
    d["ilk11_payi"] = d.ilk11 / d.takim_mac
    d["tam_mac_payi"] = d.tam_mac / d.ilk11.where(d.ilk11 > 0)
    d["yedek_payi"] = d.yedek_giris / d.mac
    p90 = 90 / d.dk.where(d.dk > 0)
    d["ga_90"] = (d.gol + d.asist) * p90
    d["kart_90"] = (d.sari + 3 * d.kirmizi) * p90
    q90 = 90 / d.dk_pm.where(d.dk_pm > 0)
    d["gf_on90"] = d.gf_on * q90
    d["ga_on90"] = d.ga_on * q90
    d["pm_on90"] = d.gf_on90 - d.ga_on90
    # takima gore: sahadayken takimin sezon ortalamasindan iyi mi
    d["ga_on_goreli"] = d.ga_on90 - d.takim_ga90       # negatif = iyi
    d["pm_on_goreli"] = d.pm_on90 - (d.takim_gf90 - d.takim_ga90)
    d["log_deger"] = np.log1p(d.deger.fillna(0))
    d["ilk_bes"] = d.comp.isin(ILK_BES).astype(int)
    d["bolum"] = [bolum(s) for s in d.season]
    return d


def kaydet(d: pd.DataFrame) -> None:
    con = duckdb.connect(str(DB))
    con.register("d", d)
    con.execute("CREATE OR REPLACE TABLE tm_oyuncu_sezon AS SELECT * FROM d")
    con.close()
    print(f"[kaydet] tm_oyuncu_sezon: {len(d):,} satir")


# ------------------------------------------------------------------ saglama
def saglama(con_ham, d: pd.DataFrame) -> None:
    print(f"\n{'=' * 80}\nSAGLAMA\n{'=' * 80}")

    # 1) arti-eksi: bastan sona oynayan ilk 11'lerde sahadaki gol = mac skoru
    t = con_ham.sql(f"""
        SELECT avg(((h.gf_on IS NULL AND (CASE WHEN s.club_id = m.home_club_id
                     THEN m.home_club_goals ELSE m.away_club_goals END) = 0)
                    OR h.gf_on = (CASE WHEN s.club_id = m.home_club_id
                     THEN m.home_club_goals ELSE m.away_club_goals END))::INT) ok_gf,
               avg(((h.ga_on IS NULL AND (CASE WHEN s.club_id = m.home_club_id
                     THEN m.away_club_goals ELSE m.home_club_goals END) = 0)
                    OR h.ga_on = (CASE WHEN s.club_id = m.home_club_id
                     THEN m.away_club_goals ELSE m.home_club_goals END))::INT) ok_ga,
               count(*) n
        FROM sure s JOIN m USING (game_id)
        LEFT JOIN sahada h USING (game_id, player_id)
        WHERE s.basladi AND s.cikis = {SAHADA_YOK}""").fetchone()
    print(f"[1] tam oynayan ilk 11'de sahadaki gol = mac skoru: atilan "
          f"%{100 * t[0]:.2f}, yenen %{100 * t[1]:.2f} (n={t[2]:,})")

    # 2) mevki kaynagi ve dagilim
    print("\n[2] mevki kaynagi:", d.mevki_kaynagi.value_counts().to_dict())

    # 3) sezon bazinda kapsam. MUHURLU TEST yillarinda SONUC BASILMAZ.
    u = d[(d.yas < 23) & (d.dk >= 450)]
    print(f"\n[3] U23, >=450 dk, sezon bazinda (muhurlu yillarda sonuc gizli):")
    print(f"    {'sezon':>6s} {'bolum':>14s} {'n':>6s} {'deger_var':>10s} "
          f"{'kadro_mevki':>12s} {'yer_edindi':>11s}")
    for s, g in u.groupby("season"):
        if s in MUHURLU_TEST:
            oran = "  (muhurlu)"
        elif g.kademe.notna().any():
            oran = f"{100 * (g.kademe >= 3).mean():10.1f}%"
        else:
            oran = "  (pencere acik)"
        print(f"    {s:>6d} {g.bolum.iloc[0]:>14s} {len(g):6d} "
              f"{100 * g.deger_var.mean():9.1f}% "
              f"{100 * (g.mevki_kaynagi == 'kadro').mean():11.1f}% {oran}")

    # 4) ince mevki (U23, gelistirme yillari)
    print("\n[4] ince mevki dagilimi (U23, >=450 dk, tum yillar):")
    print(u.ince_mevki.value_counts(dropna=False).to_string())


def capraz_saglama(d: pd.DataFrame) -> None:
    """2022-24: mevcut sistemin sonucu (player_outcome, API oyunculari) ile
    bu tablonun sonucu ayni mi? Ayni oyuncu-sezonlarda kademe ESIT olmali."""
    con = duckdb.connect(str(DB), read_only=True)
    o = con.sql("""SELECT o.tm_id player_id, o.season, o.kademe kademe_api,
                          o.minutes dk_api
                   FROM player_outcome o WHERE o.kapsam = 'tam'""").df()
    con.close()
    t = d[d.season.isin([2022, 2023, 2024])].groupby(
        ["player_id", "season"], as_index=False).agg(
        kademe=("kademe", "first"), dk=("dk", "sum"))
    x = o.merge(t, on=["player_id", "season"])
    x = x.dropna(subset=["kademe", "kademe_api"])
    esit = (x.kademe == x.kademe_api).mean()
    print(f"\n[5] CAPRAZ: 2022-24 izlenen liglerde ayni oyuncu-sezon n={len(x):,}")
    print(f"    kademe esitligi: %{100 * esit:.2f}")
    print(f"    sezon dakikasi korelasyonu (TM vs API): "
          f"{np.corrcoef(x.dk, x.dk_api)[0, 1]:.3f}")
    if esit < 0.98:
        print("    ! farkli satirlar:")
        print(x[x.kademe != x.kademe_api].head(10).to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saglama", action="store_true")
    a = ap.parse_args()

    con = duckdb.connect()
    con.execute(f"ATTACH '{HAM.as_posix()}' AS r (READ_ONLY)")
    ligler = ligleri_bul(con)
    print(f"[in] ham: {HAM.parent.name} · izlenen ligler ({len(ligler)}): {ligler}")
    mac_tablolari(con, ligler)
    sure_ve_arti_eksi(con)
    takim_gucu(con)
    d = oyuncu_sezon(con)
    d = oyuncu_bilgisi(con, d)
    d = piyasa_degeri(con, d)
    d = onceki_sezon(d)
    d = sonuc(con, d)
    d = turet(d)
    print(f"[in] {len(d):,} oyuncu-lig-sezon · {d.player_id.nunique():,} oyuncu")
    saglama(con, d)
    capraz_saglama(d)
    con.close()
    if not a.saglama:
        kaydet(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
