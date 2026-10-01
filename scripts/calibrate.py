"""ADIM 5 - Agirlik kalibrasyonu (PLAN §17.5)

SORU: Elle verilen futbolca agirliklar yerine veriden ogrenilmis agirliklar
kullanirsak sistem daha iyi tahmin eder mi?

Geriye donuk test (§17) sunu gosterdi: sistem U21'de "dakika" ve "gol" gibi
naif tabanlarin gerisinde. Iki olasilik var ve bu betik ikisini de sinar:
  1) Agirliklar yanlis        -> kalibrasyon duzeltir
  2) Metrik seti eksik        -> dakika bir OZELLIK olarak yok; ekleyelim

YONTEM VE NEDEN BOYLE:

  Model      : L2 cezali lojistik regresyon. Karar agaci / gradient boosting
               daha iyi uyum saglardi ama (a) 95 pozitifle asiri uyar,
               (b) kullanici seffaflik istedi - katsayi = agirlik, dogrudan
               roles.yaml'a yazilabilir bir sey.

  Dogrulama  : LIG-DISARIDA-BIRAK capraz dogrulama. Rastgele k-fold YANLIS
               olurdu: ayni ligin oyunculari hem egitimde hem testte olur,
               model ligin genel seviyesini ezberler ve sonuc sisirilir.
               Her lig sirayla tamamen disarida birakiliyor.

  Olcut      : geriye dönük testin AYNISI - lig ici ilk-N isabet orani.
               Farkli olcut kullanirsak iki sonuc kiyaslanamaz.

  Sinir      : 844 ornek / 95 pozitif. Bu boyutta 17 ozellikli bir model
               kolayca asiri uyar; ceza katsayisi ic capraz dogrulamayla
               secilliyor ve TUM sonuclar fold DISI raporlaniyor.

    python scripts/calibrate.py
    python scripts/calibrate.py --max-age 21 --top 10
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from backtest import TIER, sonuclari_ekle  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DB = ROOT / "data" / "scout.duckdb"
TM = ROOT / "data" / "raw" / "transfermarkt" / "2026-07-11" / "transfermarkt-datasets.duckdb"
RNG = np.random.default_rng(20260811)

# Ozellik seti. Yakin ikizler bilincli olarak DISARIDA:
#   goals/ga/np_goals -> np_ga yeter (korelasyon ~0.9, katsayilari bolusurler)
#   shots_on          -> shots + shot_accuracy ayni bilgiyi tasiyor
#   duels_won         -> duels + duel_win_pct
#   def_actions       -> tackles + interceptions + blocks toplami
OZELLIKLER = [
    "np_ga_p90_sh_pct", "shots_p90_sh_pct", "shot_accuracy_sh_pct",
    "key_passes_p90_sh_pct", "passes_p90_sh_pct",
    "dribbles_p90_sh_pct", "dribble_pct_sh_pct",
    "duels_p90_sh_pct", "duel_win_pct_sh_pct",
    "tackles_p90_sh_pct", "interceptions_p90_sh_pct", "blocks_p90_sh_pct",
    "fouls_drawn_p90_sh_pct",
    "fouls_made_p90_sh_pct", "cards_p90_sh_pct",   # zaten ters cevrilmis
    "rating_pct",
]

# §17.5 hipotezi: gence dakika verilmesi olctugumuz her seyden fazla bilgi
# tasiyor olabilir. Ham dakika lig/takim gucuyle karisir; lig ici percentile
# adil olani.
GUVEN = ["dakika_pct"]


def veri_yukle(min_minutes: int, max_age: float) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    con.execute(f"ATTACH '{TM}' AS tm (READ_ONLY)")
    sec = ", ".join(f"f.{c}" for c in OZELLIKLER)
    df = con.sql(f"""
      WITH t22 AS (
        SELECT s.player_id, s.league_id, s.league_name, s.player_name,
               s.age_season_end AS yas, s.minutes, s.goals,
               f.pos_group, {sec},
               n.score AS sistem_skoru, m.tm_id
        FROM player_season s
        JOIN player_features f
          ON f.player_id=s.player_id AND f.league_id=s.league_id AND f.season=s.season
        JOIN player_natural_role n
          ON n.player_id=s.player_id AND n.league_id=s.league_id AND n.season=s.season
        LEFT JOIN player_meta m ON m.player_id = s.player_id
        WHERE s.season=2022 AND s.minutes>={min_minutes} AND s.age_season_end<={max_age}
      ),
      v0 AS (SELECT player_id tm_id, max(market_value_in_eur) deger_2022
             FROM tm.player_valuations WHERE date BETWEEN '2022-01-01' AND '2022-12-31' GROUP BY 1),
      v1 AS (SELECT player_id tm_id, max(market_value_in_eur) deger_2024
             FROM tm.player_valuations WHERE date BETWEEN '2023-06-01' AND '2024-06-30' GROUP BY 1)
      SELECT t22.*, v0.deger_2022, v1.deger_2024
      FROM t22 LEFT JOIN v0 USING(tm_id) LEFT JOIN v1 USING(tm_id)
    """).df()

    l24 = con.sql("SELECT player_id, league_id FROM player_season WHERE season=2024").df()
    con.close()
    l24["t"] = l24.league_id.map(TIER)
    df["tier_2022"] = df.league_id.map(TIER)
    df["tier_2024"] = df.player_id.map(l24.dropna(subset=["t"]).groupby("player_id").t.min())

    df = sonuclari_ekle(df)
    # dakika percentile'i: lig x mevki icinde
    df["dakika_pct"] = (df.groupby(["league_id", "pos_group"]).minutes
                          .rank(pct=True) * 100)
    return df


def tekil_ayirt_edicilik(df: pd.DataFrame, sonuc: str) -> pd.DataFrame:
    """Her ozellik TEK BASINA sonucu ne kadar ayiriyor? (lig ici AUC)

    Lig ici hesaplaniyor: ligler arasi percentile kiyasi henuz gecersiz (§5.2)
    ve lig seviyesi farki tek basina sahte bir ayirt edicilik uretir.
    """
    satir = []
    for c in OZELLIKLER + GUVEN + ["sistem_skoru", "deger_2022"]:
        auc, agirlik = [], []
        for _, g in df.groupby("league_id"):
            s = g.dropna(subset=[c, sonuc])
            y = s[sonuc].astype(int)
            if y.nunique() < 2 or len(s) < 30:
                continue
            auc.append(roc_auc_score(y, s[c]))
            agirlik.append(len(s))
        if auc:
            satir.append({"ozellik": c,
                          "AUC": float(np.average(auc, weights=agirlik)),
                          "lig": len(auc)})
    r = pd.DataFrame(satir)
    r["ayirt_edicilik"] = (r.AUC - 0.5).abs() * 2   # 0 = bilgi yok, 1 = mukemmel
    return r.sort_values("AUC", ascending=False)


def _fold_ici_secim(egit: pd.DataFrame, sonuc: str, aday: list[str], k: int) -> list[str]:
    """Ozellikleri YALNIZCA egitim fold'una bakarak sec.

    Secimi tum veriye bakarak yapmak klasik bir sizdirma bicimidir: test
    ligindeki oyuncular secimi etkiler ve fold disi sonuc sisirilir. Burada
    secim her fold'un kendi icinde, lig ici AUC'ye gore yapiliyor.
    """
    skor = []
    for c in aday:
        auc, w = [], []
        for _, g in egit.groupby("league_id"):
            t = g.dropna(subset=[c, sonuc])
            y = t[sonuc].astype(int)
            if y.nunique() < 2 or len(t) < 25:
                continue
            auc.append(abs(roc_auc_score(y, t[c]) - 0.5))
            w.append(len(t))
        skor.append((float(np.average(auc, weights=w)) if auc else 0.0, c))
    return [c for _, c in sorted(skor, reverse=True)[:k]]


def fold_disi_tahmin(df: pd.DataFrame, sonuc: str, ozellikler: list[str],
                     k_ozellik: int | None = None) -> pd.Series:
    """Lig-disarida-birak: her oyuncunun tahmini, KENDI ligini hic gormemis
    bir modelden gelir.

    k_ozellik : verilirse her fold'da EGITIM verisine gore en ayirt edici
                k ozellik secilir (sade model - kucuk orneklemde 17 ozellik
                asiri uyuyor).
    """
    s = df.dropna(subset=ozellikler + [sonuc]).copy()
    tahmin = pd.Series(np.nan, index=df.index)
    ligler = s.league_id.unique()
    if len(ligler) < 3:
        return tahmin

    for lig in ligler:
        egit = s[s.league_id != lig]
        test = s[s.league_id == lig]
        if egit[sonuc].nunique() < 2 or len(test) == 0:
            continue
        kul = (_fold_ici_secim(egit, sonuc, ozellikler, k_ozellik)
               if k_ozellik else ozellikler)
        X, y = egit[kul].to_numpy(float), egit[sonuc].astype(int).to_numpy()
        # ceza katsayisi IC capraz dogrulamayla - yine lig bazli gruplama
        gruplar = egit.league_id.to_numpy()
        n_grup = len(np.unique(gruplar))
        boru = Pipeline([("sc", StandardScaler()),
                         ("lr", LogisticRegression(max_iter=2000, penalty="l2"))])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if n_grup >= 3:
                ara = GridSearchCV(boru, {"lr__C": [0.003, 0.01, 0.03, 0.1, 0.3, 1.0]},
                                   cv=GroupKFold(n_splits=min(n_grup, 4)),
                                   scoring="roc_auc")
                ara.fit(X, y, groups=gruplar)
                model = ara.best_estimator_
            else:
                model = boru.set_params(lr__C=0.03).fit(X, y)
            tahmin.loc[test.index] = model.predict_proba(
                test[kul].to_numpy(float))[:, 1]
    return tahmin


def ilk_n_oran(df: pd.DataFrame, kolon: str, sonuc: str, n: int) -> tuple[int, int]:
    h = t = 0
    for _, g in df.groupby("league_id"):
        s = g.dropna(subset=[kolon, sonuc])
        if len(s) < n:
            continue
        h += int(s.nlargest(n, kolon)[sonuc].sum())
        t += n
    return h, t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-minutes", type=int, default=450)
    ap.add_argument("--max-age", type=float, default=99.0)
    ap.add_argument("--sonuc", default="A_sicrama", choices=["A_sicrama", "B_terfi"])
    ap.add_argument("--k", type=int, default=4,
                    help="sade modelde fold ici secilecek ozellik sayisi")
    a = ap.parse_args()

    pd.set_option("display.width", 200)
    df = veri_yukle(a.min_minutes, a.max_age)
    sonuc = a.sonuc

    print("=" * 78)
    print(f"AGIRLIK KALIBRASYONU - sonuc: {sonuc}, U{int(a.max_age)}, ilk {a.top}")
    print("=" * 78)

    alt = df.dropna(subset=[sonuc]).copy()
    print(f"\norneklem {len(alt):,} oyuncu, {int(alt[sonuc].sum())} pozitif "
          f"(taban oran %{alt[sonuc].mean()*100:.1f}), {alt.league_id.nunique()} lig")

    print("\n" + "-" * 78)
    print("1) HER OZELLIK TEK BASINA NE KADAR AYIRT EDIYOR? (lig ici AUC)")
    print("   0.50 = hicbir bilgi yok. Uzaklik iki yone de anlamli.")
    print("-" * 78)
    te = tekil_ayirt_edicilik(alt, sonuc)
    print(te.round(3).to_string(index=False))

    print("\n" + "-" * 78)
    print("2) FOLD DISI KARSILASTIRMA - her model kendi ligini hic gormedi")
    print("-" * 78)

    alt["kalibre"] = fold_disi_tahmin(alt, sonuc, OZELLIKLER)
    alt["kalibre_dk"] = fold_disi_tahmin(alt, sonuc, OZELLIKLER + GUVEN)
    alt["kalibre_sade"] = fold_disi_tahmin(alt, sonuc, OZELLIKLER + GUVEN,
                                           k_ozellik=a.k)

    yontemler = {
        "SISTEM (elle agirlik)": "sistem_skoru",
        "KALIBRE (ogrenilmis)": "kalibre",
        "KALIBRE + dakika": "kalibre_dk",
        f"KALIBRE sade ({a.k} ozellik)": "kalibre_sade",
        "gol": "goals",
        "dakika": "minutes",
        "piyasa degeri (2022)": "deger_2022",
    }
    gerekli = [c for c in yontemler.values() if c in alt.columns]
    havuz = alt.dropna(subset=gerekli + [sonuc])
    print(f"\ntam vaka havuzu: {len(havuz):,} oyuncu "
          f"({int(havuz[sonuc].sum())} pozitif)")

    # rastgele taban
    oranlar = []
    for _ in range(2000):
        h = t = 0
        for _, g in havuz.groupby("league_id"):
            if len(g) < a.top:
                continue
            h += int(g[sonuc].to_numpy()[RNG.choice(len(g), a.top, replace=False)].sum())
            t += a.top
        if t:
            oranlar.append(h / t)
    rast = float(np.mean(oranlar)) if oranlar else np.nan
    esik95 = float(np.quantile(oranlar, 0.95)) if oranlar else np.nan

    satir = []
    for ad, kol in yontemler.items():
        h, t = ilk_n_oran(havuz, kol, sonuc, a.top)
        oran = h / t if t else np.nan
        satir.append({"yontem": ad, "isabet": h, "secilen": t,
                      "oran_%": round(oran * 100, 1),
                      "kat_rastgele": round(oran / rast, 2) if rast else np.nan,
                      "sansi_asti": oran > esik95})
    satir.append({"yontem": "rastgele", "isabet": np.nan, "secilen": np.nan,
                  "oran_%": round(rast * 100, 1), "kat_rastgele": 1.0,
                  "sansi_asti": False})
    print()
    print(pd.DataFrame(satir).sort_values("oran_%", ascending=False).to_string(index=False))

    print("\n" + "-" * 78)
    print("3) OGRENILMIS AGIRLIKLAR (tum veriye fit - yalnizca YORUM icin)")
    print("   Bunlar fold disi degil; buyukluk sirasi ve ISARET icin bakilir.")
    print("-" * 78)
    s = alt.dropna(subset=OZELLIKLER + GUVEN + [sonuc])
    boru = Pipeline([("sc", StandardScaler()),
                     ("lr", LogisticRegression(max_iter=2000, C=0.03))])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        boru.fit(s[OZELLIKLER + GUVEN].to_numpy(float), s[sonuc].astype(int))
    kat = pd.DataFrame({"ozellik": OZELLIKLER + GUVEN,
                        "katsayi": boru.named_steps["lr"].coef_[0]})
    kat["yon"] = np.where(kat.katsayi > 0, "+", "-")
    print(kat.reindex(kat.katsayi.abs().sort_values(ascending=False).index)
             .round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
