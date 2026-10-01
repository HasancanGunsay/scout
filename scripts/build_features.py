"""Faz 3: Ozellik muhendisligi - player_season -> player_features

Hat:
  ham sayimlar
    -> per-90 + oran metrikleri            (features/metrics.py)
    -> empirical Bayes shrinkage           (features/shrinkage.py)   §1.2
    -> kohort ici percentile (0-100)       (features/percentile.py)
    -> yas egrisi + yas bandi              (features/age.py)         §1.3

Henuz YAPILMAYAN (Faz 4-5):
  - lig gucu duzeltmesi (§5.2) -> ligler arasi karsilastirma HENUZ GECERSIZ
  - rol kumeleme (§1.5)        -> simdilik kaba mevki grubu kullaniliyor
  - possession-adjusted        -> takim topa sahip olma verisi gerekiyor (ek API)

Idempotent - her calistirmada bastan kurar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.features import age as age_mod  # noqa: E402
from scout.features import metrics as met  # noqa: E402
from scout.features import percentile as pct  # noqa: E402
from scout.features import position as pos  # noqa: E402
from scout.features import shrinkage as shr  # noqa: E402
from scout.roles import cluster as rc  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DB = ROOT / "data" / "scout.duckdb"

# Kohort: ayni lig, ayni sezon, ayni ROL KUMESI (§1.5).
# 'role_cohort', kume yeterince buyukse rol kumesi, degilse pos_group'a duser.
# Lig gucu duzeltmesi gelene kadar ligler arasi kiyas yapilamaz (§5.2).
COHORT = ["league_id", "season", "role_cohort"]

# Dusuk olmasi iyi olan metrikler - percentile'lari ters cevrilir.
# {sablon_anahtari: sutun_tabani} - anahtar roles.yaml'daki 'invert' listesiyle
# ayni olmali; percentile.invert isaret sutununu bu anahtarla birakiyor.
LOWER_IS_BETTER = {
    "fouls_made": "fouls_made_p90_sh",
    "cards": "cards_p90_sh",
    "goals_conceded": "goals_conceded_p90_sh",   # kaleci: az gol yemek iyi
}

# Shrinkage'a girmeyen, dogrudan percentile'a cevrilen sutunlar.
# scoring/engine.py'deki PLAIN_KEYS ile ayni olmali - 'rating' 13 rol
# sablonunda agirlikli ama 'rating_pct' uretilmedigi icin skorlara HIC
# katkI vermiyordu; xG'siz sistemde tek genel katki gostergemiz oydu (§16).
PLAIN_COLS = ["rating"]

# --- GUVEN SINYALI - skora GIRMEZ, yalnizca gosterilir ------------------
# §18.4: U21'de dakika, olctugumuz her metrikten iyi bir tek basina
# siralayici (%60,0 isabet, sansin %95 esigini gecti). Ama skora KOYMUYORUZ:
#   - dakika hem sebep hem sonuc (iyi oyuncu cok oynar) - dairesel
#   - agirliga konursa listeler "cok oynayan yasli oyuncu"ya kayar,
#     yani wonderkid avinin tam tersine
# Bunun yerine ayri bir sinyal olarak gosteriliyor: skor "ne kadar iyi
# oynadi", bu "kulubu ona ne kadar guvendi" sorusunu cevapliyor.
# NOT: 'reliable' bayragi bundan FARKLI bir sey - o istatistigin orneklem
# yeterliligi, bu kulup guveni. Ikisi karistirilmamali.
GUVEN_COLS = ["minutes"]

# Yas egrisi hangi metrige fit edilecek - genel katki gostergesi
AGE_CURVE_METRIC = "rating"

MIN_MINUTES = 450  # bunun altindakiler tabloya girer ama 'guvenilir' sayilmaz


def main() -> int:
    con = duckdb.connect(str(DB))
    df = con.sql("SELECT * FROM player_season").df()
    print(f"[in]  {len(df):,} oyuncu-lig-sezon")

    # 0) eksik mevkileri cikar (ADIM 1) ------------------------------------
    # Mevkisi olmayan oyuncu kohortsuz kalir ve HIC skor almaz. Cikarim
    # 'position_source' ile GORUNUR, emin olunmayan tahmin KABUL EDILMEZ.
    df, poz_rapor = pos.infer(df)
    if poz_rapor.get("eksik"):
        print(f"[0]   {poz_rapor['eksik']} oyuncuda mevki bos; "
              f"capraz dogrulanmis dogruluk %{poz_rapor.get('cv_dogruluk', 0)*100:.1f} -> "
              f"{poz_rapor.get('kabul', 0)} kabul, {poz_rapor.get('red', 0)} red")
        if "ayrinti" in poz_rapor:
            print(poz_rapor["ayrinti"].to_string(index=False))

    # 1) metrikler ---------------------------------------------------------
    df = met.build(df)
    print(f"[1]   {len(met.COUNT_METRICS)} sayim + {len(met.RATE_METRICS)} oran metrigi")

    # 1b) rol kumeleme -----------------------------------------------------
    # Kumeleme per-90'lardan SONRA, percentile'dan ONCE gelmeli:
    # stil paylarini per-90'lardan hesapliyor, kohortu da o belirliyor.
    df, rep = rc.cluster_all(df)
    n_cl = df.role_cluster.nunique()
    fb = int(df.cohort_fallback.sum())
    print(f"[1b]  {n_cl} rol kumesi bulundu"
          + (f" ({fb} oyuncu kucuk kohort nedeniyle mevki grubuna dustu)" if fb else ""))

    # 2) shrinkage ---------------------------------------------------------
    # possession-adjusted savunma metrikleri de shrinkage/percentile hattina
    # girsin (§32). Olculdu: hepsi ham surumden ANLAMLI biçimde iyi ayirt
    # ediyor (stoperde savunma aksiyonu 0,501 -> 0,534, GA [+0,011,+0,057]).
    padj = [f"{m}_padj" for m in met.PADJ_METRIKLERI]
    count_metrics = list(met.COUNT_METRICS) + list(met.GK_COUNT_METRICS) + padj
    count_specs = {f"{k}_p90": (f"{k}_raw", "nineties") for k in count_metrics}
    rate_specs = {k: (f"{k}_num", f"{k}_den") for k in met.RATE_METRICS}
    df = shr.shrink_by_cohort(df, cohort=COHORT, count_specs=count_specs, rate_specs=rate_specs)
    print(f"[2]   shrinkage uygulandi (kohort: {' x '.join(COHORT)})")

    # 3) percentile --------------------------------------------------------
    sh_cols = [f"{c}_sh" for c in list(count_specs) + list(rate_specs)]
    pct_cols = sh_cols + PLAIN_COLS + GUVEN_COLS
    df = pct.percentile_in_cohort(df, pct_cols, cohort=COHORT)
    df = pct.invert(df, LOWER_IS_BETTER)
    print(f"[3]   {len(pct_cols)} metrik percentile'a cevrildi "
          f"({len(PLAIN_COLS)} shrinkage'siz: {', '.join(PLAIN_COLS)}; "
          f"{len(GUVEN_COLS)} guven sinyali, skora girmez: {', '.join(GUVEN_COLS)})")

    # 4) yas ---------------------------------------------------------------
    df = age_mod.add_age_band(df)
    curve = age_mod.AgeCurve().fit(df, AGE_CURVE_METRIC)
    if curve.informative:
        df["rating_vs_age"] = age_mod.age_adjusted(df, AGE_CURVE_METRIC, curve)
        print(f"[4]   yas egrisi fit edildi ve KULLANILIYOR "
              f"({curve.n_fit_} oyuncu, {curve.n_seasons_} sezon)")
    else:
        df["rating_vs_age"] = pd.NA
        print(f"[4]   yas egrisi KULLANILMIYOR - {curve.n_fit_} oyuncu / "
              f"{curve.n_seasons_} sezon, egri araligi {curve.curve_range_:.3f} "
              f"vs gurultu {curve.resid_sd_:.3f}, "
              f"tepe {curve.peak_age_:.1f} yas (23-32 bekleniyor), "
              f"tepeden dusus {curve.decline_after_peak_:.3f}")
        print("      Sebep: KESITSEL fit hayatta kalma yanliligi tasiyor (§1.11, §19).")
        print("      Coklu sezona sahip olmak yetmiyor - sezonlari havuzlayip fit")
        print("      etmek hala kesitseldir. Gercek cozum BOYLAMSAL fit: ayni")
        print("      oyuncuyu yillar boyunca izlemek. Ayni oyuncunun 2+ sezonu")
        print("      birikince yapilacak.")
        print("      Simdilik yas duzeltmesi YAS BANDI percentile'i ile yapiliyor.")

    # yas bandi ici percentile: "yasitlarina gore" siralama (B yontemi)
    # Burada rol kumesi DEGIL pos_group kullaniliyor - kume x yas bandi
    # kirilimi cok kucuk kohortlar uretiyor.
    df = pct.percentile_in_cohort(
        df, pct_cols, cohort=["league_id", "season", "pos_group", "age_band"],
        min_size=8, suffix="_agepct",
    )
    # _pct ile AYNI yonde olmali: engine isaret sutununu gorup artik kendisi
    # cevirmiyor, dolayisiyla iki percentile ailesi de burada cevrilmis olmali.
    df = pct.invert(df, LOWER_IS_BETTER, suffix="_agepct")
    print("[5]   yas bandi ici percentile eklendi")

    df["reliable"] = df["minutes"] >= MIN_MINUTES

    con.execute("CREATE OR REPLACE TABLE player_features AS SELECT * FROM df")
    if curve.coef_ is not None:
        ct = curve.curve_table()
        ct["informative"] = curve.informative
        con.execute("CREATE OR REPLACE TABLE age_curve AS SELECT * FROM ct")

    print(f"\n[ok]  {len(df):,} satir x {len(df.columns)} sutun -> player_features\n")

    # --- denetim ----------------------------------------------------------
    pd.set_option("display.width", 210)
    print("--- ROL AYRIMI TESTLERI ---")
    print("    Bir ayrim ancak CIFT TEPELILIK kanitlanirsa uygulanir.")
    print("    bimodality > 0.555 ve bic_gain > 0 -> destekleniyor\n")
    tests = rep.get("tests")
    if tests is not None and len(tests):
        print(tests.to_string(index=False))
        used = tests[tests.supported]
        if len(used):
            print(f"\n  UYGULANAN: {', '.join(used.metrik + ' (' + used.mevki + ')')}")
        rejected = tests[~tests.supported]
        if len(rejected):
            print(f"  REDDEDILEN: {len(rejected)} aday - yeterli kanit yok, "
                  "mevki grubu korundu")

    print("\n--- kohort buyuklukleri (percentile guvenilirligi) ---")
    print(pct.cohort_sizes(df, COHORT).head(16).to_string(index=False))

    print("\n--- shrinkage etkisi: np_ga_p90, en az dakikali 8 oyuncu ---")
    cols = ["player_name", "minutes", "np_ga_p90", "np_ga_p90_sh", "np_ga_p90_w"]
    sample = df[df["minutes"] > 0].nsmallest(8, "minutes")[cols]
    sample.columns = ["oyuncu", "dk", "ham", "cekilmis", "agirlik"]
    print(sample.round(3).to_string(index=False))

    print("\n--- shrinkage etkisi: en cok dakikali 5 oyuncu (az cekilmeli) ---")
    sample2 = df.nlargest(5, "minutes")[cols]
    sample2.columns = ["oyuncu", "dk", "ham", "cekilmis", "agirlik"]
    print(sample2.round(3).to_string(index=False))

    print("\n--- metrik sinyal gucu (1800+ dk, tam sezon oynayanlar) ---")
    print("    agirlik = kanitin ne kadarina guvenilebilir; dusukse cogu gurultu")
    sig = con.sql("""
      SELECT 'passes' m, avg(passes_p90_w) w FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'duels', avg(duels_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'dribbles', avg(dribbles_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'key_passes', avg(key_passes_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'tackles', avg(tackles_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'shots', avg(shots_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'np_ga', avg(np_ga_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'goals', avg(goals_p90_w) FROM player_features WHERE minutes>=1800
      UNION ALL SELECT 'assists', avg(assists_p90_w) FROM player_features WHERE minutes>=1800
      ORDER BY w DESC
    """).df()
    print(sig.round(3).to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
