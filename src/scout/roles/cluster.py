"""Rol ayrimi - §1.5.

PROBLEM: API yalnizca 4 kaba mevki veriyor. Bir stoper ile bir bek AYNI
havuzda percentile aliyor; bekin cok calim atmasi "iyi", stoperin atmamasi
"kotu" gorunuyor. Kohort yanlissa skor da yanlistir.

===========================================================================
OLCUM SONUCU: SERBEST KUMELEME BU VERIDE CALISMIYOR
===========================================================================
Once GMM ile serbest kumeleme denendi (paylar -> CLR -> PCA -> GMM/BIC).
Sonuc kabul edilemezdi:
  - silhouette 0.13-0.28 (net kume yapisi yok)
  - iki ayri kumeye ayni isim dustu
  - kume profilleri neredeyse ozdes cikti
    (Kanat sut payi 0.050 vs Santrfor 0.053 - ayrim degil bu)

Bunun uzerine dogru soru soruldu: bu veride ayrik rol yapisi GERCEKTEN
var mi? Cift tepelilik testi (bimodality coefficient + 1'e karsi 2
bilesenli GMM, BIC) yapildi. Brezilya A+B 2024, 900+ dakika:

  mevki       metrik          bimodalite  2_bilesen_daha_iyi
  Defender    dribbles/90     0.588  ✓    True   ✓  <-- TEK GERCEK AYRIM
  Defender    key_passes/90   0.487       True
  Defender    blocks/90       0.499       True
  Attacker    shots/90        0.326       False
  Attacker    np_goals/90     0.427       False
  Midfielder  key_passes/90   0.535       True
  Midfielder  tackles/90      0.442       False

Yalnizca STOPER/BEK ayrimi gercek. Orta saha ve forvette dagilimlar TEK
TEPELI - yani ayrik roller degil, surekli bir spektrum var. Bu sasirtici
degil: elimizde mekansal veri yok (pas yonu/uzunlugu, dokunus bolgesi,
ilerletici aksiyon). Onlarsiz bir stoper ile bir on libero birbirine benzer.

===========================================================================
SECILEN YAKLASIM: DOGRULANMIS AYRIM
===========================================================================
Kor kumeleme yerine, her aday ayrim ONCE test edilir; yalnizca cift
tepelilik kanitlanirsa uygulanir. Kanit yoksa mevki grubu korunur.

Avantaji: veri buyudukce (yeni ligler, yeni sezonlar) daha fazla ayrim
istatistiksel destek kazanip KENDILIGINDEN devreye girer. Sistem
olmayan yapiyi uydurmaz, olani kacirmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

MIN_MINUTES_FIT = 900       # stil sinyali icin yeterli dakika
MIN_CLUSTER_MEMBERS = 12    # bundan kucuk kohort anlamli percentile uretmez
MIN_BIMODALITY = 0.555      # ustunde cift tepeli kabul edilir (standart esik)
MIN_GROUP = 60              # test icin gereken asgari oyuncu

# Aday ayrimlar: (ayirt edici metrik, yuksek taraf adi, dusuk taraf adi)
# Futbolca gerekcesi olanlar; her biri veriyle SINANIR, otomatik uygulanmaz.
CANDIDATE_SPLITS: dict[str, list[tuple[str, str, str]]] = {
    "Defender": [
        ("dribbles_p90", "Bek", "Stoper"),
        ("key_passes_p90", "Hücumcu savunmacı", "Saf savunmacı"),
    ],
    "Midfielder": [
        ("key_passes_p90", "Hücumcu orta saha", "Ön libero"),
        ("np_goals_p90", "Gol atan orta saha", "Denge oyuncusu"),
    ],
    "Attacker": [
        ("shots_p90", "Santrfor", "Kanat"),
        ("tackles_p90", "Pres yapan forvet", "Bekleyen forvet"),
    ],
    # Kaleci bolunmez - tek rol.
}


def bimodality(x: pd.Series) -> float:
    """Sarle bimodality coefficient. >0.555 cift tepeli sinyali."""
    s = x.dropna()
    n = len(s)
    if n < 30:
        return 0.0
    skew, kurt = s.skew(), s.kurt()
    denom = kurt + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return float((skew**2 + 1) / denom) if denom else 0.0


def test_split(x: pd.Series) -> dict:
    """Bir metrigin gercekten iki grup olusturup olusturmadigini sina."""
    v = x.dropna().to_numpy().reshape(-1, 1)
    out = {"n": len(v), "bimodality": 0.0, "bic_gain": 0.0, "supported": False,
           "threshold": np.nan}
    if len(v) < MIN_GROUP:
        return out

    bc = bimodality(pd.Series(v.ravel()))
    g1 = GaussianMixture(1, random_state=0).fit(v)
    g2 = GaussianMixture(2, random_state=0, n_init=5).fit(v)
    gain = g1.bic(v) - g2.bic(v)          # pozitif = 2 bilesen daha iyi

    out.update(bimodality=round(bc, 3), bic_gain=round(gain, 1))
    if bc > MIN_BIMODALITY and gain > 0:
        # iki bilesenin ortalamalarinin ortasi = esik
        mu = np.sort(g2.means_.ravel())
        out["threshold"] = float(mu.mean())
        out["supported"] = True
    return out


def split_position(df: pd.DataFrame, pos: str) -> tuple[pd.Series, pd.DataFrame]:
    """Bir mevki grubunu, DOGRULANMIS en iyi ayrima gore bol.

    Returns (etiketler, test_raporu)
    """
    sub = df[df.pos_group == pos]
    labels = pd.Series(pos, index=sub.index, dtype="object")
    rows = []

    fit = sub[sub.minutes >= MIN_MINUTES_FIT]
    if len(fit) < MIN_GROUP:
        fit = sub[sub.minutes >= 450]

    best = None
    for metric, hi_name, lo_name in CANDIDATE_SPLITS.get(pos, []):
        if metric not in sub.columns:
            continue
        r = test_split(fit[metric])
        rows.append({"mevki": pos, "metrik": metric,
                     "yüksek": hi_name, "düşük": lo_name, **r})
        if r["supported"] and (best is None or r["bimodality"] > best[0]["bimodality"]):
            best = (r, metric, hi_name, lo_name)

    if best is not None:
        r, metric, hi_name, lo_name = best
        v = pd.to_numeric(sub[metric], errors="coerce")
        labels = pd.Series(
            np.where(v >= r["threshold"], f"{pos}::{hi_name}", f"{pos}::{lo_name}"),
            index=sub.index, dtype="object",
        )
        labels[v.isna()] = pos

    return labels, pd.DataFrame(rows)


def cluster_all(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, dict]:
    """Tum mevki gruplarina dogrulanmis ayrimlari uygula.

    Ekler:
      role_cluster    - ayrilmis rol etiketi (destek yoksa mevki grubu)
      role_cohort     - percentile kohortu (kucuk kohortta mevki grubuna duser)
      cohort_fallback - kohort kucukluk nedeniyle geri dustu mu
    """
    out = df.copy()
    out["role_cluster"] = out["pos_group"].astype("object")
    reports = []

    for pos in CANDIDATE_SPLITS:
        if (out.pos_group == pos).sum() < MIN_GROUP:
            continue
        labels, rep = split_position(out, pos)
        out.loc[labels.index, "role_cluster"] = labels.values
        if len(rep):
            reports.append(rep)

    # kohort guvenligi: (lig, sezon, rol) 12'den kucukse mevki grubuna don
    grp = out.groupby(["league_id", "season", "role_cluster"])["player_id"].transform("size")
    out["role_cohort"] = out["role_cluster"].where(grp >= MIN_CLUSTER_MEMBERS,
                                                   out["pos_group"])
    out["cohort_fallback"] = grp < MIN_CLUSTER_MEMBERS

    report = pd.concat(reports, ignore_index=True) if reports else pd.DataFrame()
    return out, {"tests": report}
