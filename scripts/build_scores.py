"""Faz 5: Rol skorlarini uret -> player_scores tablosu

player_features + config/roles.yaml  ->  (oyuncu x rol) skorlari

Iki skor sutunu:
  score      - kendi lig/sezon/mevki havuzunda (SIMDIKI performans)
  score_age  - kendi yas bandinda (YASITLARINA GORE - wonderkid sinyali)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.features.age_long import BoylamsalYasEgrisi  # noqa: E402
from scout.scoring.engine import load_roles, score_all  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DB = ROOT / "data" / "scout.duckdb"
ROLES = ROOT / "config" / "roles.yaml"


def main() -> int:
    roles, thresholds = load_roles(ROLES)
    con = duckdb.connect(str(DB))
    feats = con.sql("SELECT * FROM player_features").df()
    print(f"[in]   {len(feats):,} oyuncu-sezon, {len(roles)} rol sablonu")

    cur = score_all(feats, roles, age_band=False)
    age = score_all(feats, roles, age_band=True)
    print(f"[1]    {len(cur):,} (oyuncu x rol) skoru")

    # Kapsam esigi (§21): agirligin cok azi hesaplanabiliyorsa skor uretme.
    # Kucuk kohortta percentile uretmeme kuralinin esdegeri.
    min_cov = float(thresholds.get("min_coverage", 0.0))
    if min_cov > 0:
        for tbl, s_col, c_col in [(cur, "score", "coverage"),
                                  (age, "score_age", "coverage_age")]:
            dusuk = tbl[c_col] < min_cov
            tbl.loc[dusuk, s_col] = np.nan
            if dusuk.any():
                print(f"[1b]   {int(dusuk.sum()):,} skor BASTIRILDI "
                      f"({c_col} < {min_cov}) - eksik veriden skor uretilmiyor")

    key = ["player_id", "league_id", "season", "role"]
    scores = cur.merge(
        age[key + ["score_age", "coverage_age", "contrib_age"]], on=key, how="left"
    )

    # oyuncu kimlik bilgilerini yanina ekle
    meta_cols = [
        "player_id", "league_id", "season", "player_name", "team_name", "country",
        "league_name", "pos_group", "position", "age_season_end", "age_band",
        "minutes", "apps", "nineties", "rating", "nationality", "birth_date",
        "height_cm", "multi_team", "reliable",
        # guven sinyali (§18.4) - skora GIRMEZ, arayuzde ayri gosterilir.
        # minutes_agepct = "yasitlarina gore ne kadar oynadi" - U21 icin
        # asil anlamli olan bu: 19 yasinda %70 dakika almak dikkate deger,
        # 28 yasinda siradan.
        "minutes_pct", "minutes_agepct",
    ]
    meta = feats[[c for c in meta_cols if c in feats.columns]].drop_duplicates(
        subset=["player_id", "league_id", "season"]
    )
    scores = scores.merge(meta, on=["player_id", "league_id", "season"], how="left")

    # katki sozluklerini JSON metnine cevir (DuckDB'ye yazmak icin)
    for c in ["contrib", "contrib_age"]:
        scores[c] = scores[c].map(lambda d: json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else None)

    con.execute("CREATE OR REPLACE TABLE player_scores AS SELECT * FROM scores")

    # dogal rol tablosu
    nat = con.sql("""
        SELECT * FROM (
          SELECT *, row_number() OVER (
            PARTITION BY player_id, league_id, season ORDER BY score DESC
          ) rn FROM player_scores
        ) WHERE rn = 1
    """).df()
    # SAHTE DOGAL ROL (30 Agu 2026 denetiminde bulundu)
    # Hicbir rolde skor uretilemeyen oyuncuda "ORDER BY score DESC" tum
    # degerler NULL oldugu icin karar veremiyor ve satir sirasina dusuyor -
    # yani kazanan, roles.yaml'de o mevkinin ILK rolu oluyor. Sonuc:
    # 2.002 oyuncu-sezona tamamen uydurma bir "dogal rol" atanmisti
    # (Regista 916, Pres Yapan 743, Kaleci 334, Bek-Hucumcu 9) ve bunlarin
    # 1.289'u 450+ dakika oynamis, yani arayuzde gorunur durumdaydi.
    #
    # Skoru bastirmak (§21) ama etiketi birakmak tutarsizdi: sayiyi
    # uretmeyecek kadar az veri varken rol adini uretmek ayni hata.
    # Satir KALIYOR (oyuncu listeden kaybolmasin), rol etiketi NULL oluyor.
    skorsuz = nat.score.isna()
    if skorsuz.any():
        nat.loc[skorsuz, ["role", "role_name"]] = None
        print(f"[1c]   {int(skorsuz.sum()):,} satirda DOGAL ROL ETIKETI "
              f"kaldirildi - skor uretilemeyen oyuncuya rol atanmiyor")
    con.execute("CREATE OR REPLACE TABLE player_natural_role AS SELECT * FROM nat")

    # --- BOYLAMSAL yas egrisi (ADIM 3, PLAN §26) -------------------------
    # Burada hesaplaniyor cunku "score" gerekiyor; build_features asamasinda
    # skor henuz yok. Ayni oyuncunun ardisik sezonlari arasindaki DEGISIMDEN
    # fit ediliyor, dolayisiyla kesitsel fitin hayatta kalma yanliligini
    # tasimiyor (kesitsel surum bu yuzden iki kez reddedildi - §19).
    egri = BoylamsalYasEgrisi(derece=2).fit(nat, "score", ayni_lig=True)
    if egri.makul:
        ct = egri.egri_.copy()
        ct["tepe_yas"] = egri.tepe_yas_
        ct["n_gecis"] = egri.n_gecis_
        con.execute("CREATE OR REPLACE TABLE age_curve_long AS SELECT * FROM ct")
        seviye = egri.egri_.set_index("yas").seviye
        lo, hi = seviye.index.min(), seviye.index.max()

        # "Yasina gore beklenenin ne kadar ustunde?"
        # DIKKAT: yalnizca GENC kohortta anlamli. Olculdu:
        #   U23  -> ham skordan FARKI AYIRT EDILEMIYOR: +1,6 puan,
        #           %95 GA [-6,7 , +10,0] (29 Agu denetimi, §31). Once
        #           "1,62x vs 1,52x" diye benimsenmisti - o fark gurultuydu.
        #   tum yaslar -> 0,51x FELAKET; egri 25 sonrasi dikce dustugu icin
        #   35 yasindakine devasa bonus veriyor. Arayuz bunu yas filtresi
        #   <=23 iken sunuyor.
        for tbl in ("player_scores", "player_natural_role"):
            df_t = con.sql(f"SELECT * FROM {tbl}").df()
            bek = df_t.age_season_end.round().clip(lo, hi).map(seviye)
            df_t["score_vs_yas"] = df_t.score - bek
            con.execute(f"CREATE OR REPLACE TABLE {tbl} AS SELECT * FROM df_t")

        print(f"[2]    boylamsal yas egrisi: tepe {egri.tepe_yas_:.0f} yas, "
              f"{egri.n_gecis_:,} gecis -> score_vs_yas eklendi")
    else:
        con.execute("DROP TABLE IF EXISTS age_curve_long")
        print(f"[2]    yas egrisi KULLANILMIYOR - tepe {egri.tepe_yas_:.1f} "
              f"(23-32 bekleniyor), dusus {egri.dusus_:.2f}")

    print(f"\n[ok]   player_scores: {len(scores):,} satir")
    print(f"[ok]   player_natural_role: {len(nat):,} oyuncu\n")

    pd.set_option("display.width", 215)

    print("--- rol dagilimi (dogal rol) ---")
    print(con.sql("""
        SELECT role_name, count(*) n, round(avg(score),1) ort_skor
        FROM player_natural_role GROUP BY 1 ORDER BY n DESC
    """).df().to_string(index=False))

    print("\n=== SERIE B 2024 | U21 | YASITLARINA GORE EN IYI 12 ===")
    print(con.sql("""
        SELECT player_name AS oyuncu, round(age_season_end,1) AS yas,
               role_name AS rol, team_name AS takim, cast(minutes AS INT) AS dk,
               round(score,1) AS skor, round(score_age,1) AS yas_skoru,
               round(coverage,2) AS kapsam
        FROM player_natural_role
        WHERE league_id=72 AND season=2024 AND age_season_end < 21.5
          AND minutes >= 450
        ORDER BY score_age DESC NULLS LAST LIMIT 12
    """).df().to_string(index=False))

    print("\n=== SERIE B 2024 | 'PRES YAPAN FORVET' ARANIYOR (rol sabitli) ===")
    print(con.sql("""
        SELECT player_name AS oyuncu, round(age_season_end,1) AS yas,
               team_name AS takim, cast(minutes AS INT) AS dk,
               round(score,1) AS skor
        FROM player_scores
        WHERE league_id=72 AND season=2024 AND role='fw_pressing'
          AND minutes >= 900
        ORDER BY score DESC LIMIT 10
    """).df().to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
