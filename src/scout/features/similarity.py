"""Benzer oyuncu arama - "bunun gibi ama daha ucuz" (ADIM 6).

Scout is akisinin merkezindeki soru bu: begendigin oyuncuyu alamiyorsan,
ona benzeyen ve ulasilabilir olani bul.

NE DEMEK "BENZER"?
Iki ayri sey karistirilmamali:
  STIL   - oyuncunun ne YAPTIGI (cok mu calim atiyor, cok mu pas kesiyor)
  KALITE - bunu ne kadar IYI yaptigi

Bu modul STIL benzerligi olcer. Kalite ayri bir eksen: kullanici once
benzer stildekileri bulur, sonra skora/yasa/fiyata gore suzer. Ikisini tek
sayida birlestirmek "iyi oyuncular birbirine benzer" gibi anlamsiz bir
sonuc verir.

NEDEN CLR (centered log-ratio)?
Ham per-90 degerlerde PAS her seyi ezer: bir orta saha 40 pas/90 yaparken
1 sut/90 atar. Duz oran alirsak herkesin vektoru "%95 pas" olur ve
farklar kaybolur. CLR log-oran uzayina tasiyor: onemli olan mutlak hacim
degil, aksiyonlarin BIRBIRINE ORANI. Bu, bilesimsel veri (compositional
data) icin standart donusum.

NEDEN AYNI MEVKI GRUBU SARTI?
Bir stoperle bir forveti stil olarak kiyaslamak anlamsiz - zaten farklilar.
Benzerlik ancak mevki grubu icinde bilgi tasiyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Stil vektorunu olusturan aksiyonlar. Shrinkage uygulanmis per-90'lar
# kullaniliyor - az dakikali oyuncuda ham degerler cok gurultulu.
STIL_METRIKLERI = [
    "shots_p90_sh",
    "key_passes_p90_sh",
    "passes_p90_sh",
    "dribbles_p90_sh",
    "tackles_p90_sh",
    "interceptions_p90_sh",
    "blocks_p90_sh",
    "duels_p90_sh",
    "fouls_drawn_p90_sh",
    "fouls_made_p90_sh",
]

EPS = 1e-4          # sifir log'a girmesin
MIN_DAKIKA = 450    # altinda stil sinyali guvenilmez


def clr(x: np.ndarray) -> np.ndarray:
    """Centered log-ratio. Satir basina: log(x_i) - ortalama(log(x))."""
    lx = np.log(np.clip(x, EPS, None))
    return lx - lx.mean(axis=1, keepdims=True)


def stil_vektorleri(df: pd.DataFrame) -> tuple[np.ndarray, list[str], pd.Index]:
    """CLR stil vektorleri. Donen: (matris, kullanilan metrikler, satir index)."""
    kul = [c for c in STIL_METRIKLERI if c in df.columns]
    if not kul:
        return np.empty((0, 0)), [], df.index[:0]
    alt = df[kul].apply(pd.to_numeric, errors="coerce")
    tam = alt.notna().all(axis=1)
    if not tam.any():
        return np.empty((0, 0)), kul, df.index[:0]
    return clr(alt[tam].to_numpy(float)), kul, alt.index[tam]


def benzerler(
    df: pd.DataFrame,
    hedef_idx,
    *,
    n: int = 10,
    ayni_mevki: bool = True,
    min_dakika: int = MIN_DAKIKA,
) -> pd.DataFrame:
    """hedef_idx'teki oyuncuya stil olarak en yakin n oyuncu.

    'benzerlik' 0-100: 100 = ayni stil. Oklid uzakligindan turetiliyor,
    kohortun kendi olcegine gore normalize ediliyor (uzakligin dagilimi
    mevki grubuna gore degisiyor, sabit bir esik anlamsiz olurdu).
    """
    if hedef_idx not in df.index:
        return pd.DataFrame()

    hedef = df.loc[hedef_idx]
    havuz = df[df["minutes"] >= min_dakika]
    if ayni_mevki and "pos_group" in df.columns:
        havuz = havuz[havuz["pos_group"] == hedef["pos_group"]]
    if hedef_idx not in havuz.index:
        havuz = pd.concat([havuz, df.loc[[hedef_idx]]])

    X, kul, idx = stil_vektorleri(havuz)
    if len(idx) < 3 or hedef_idx not in idx:
        return pd.DataFrame()

    # Metrikleri kohort icinde standartlastir: yoksa varyansi buyuk olan
    # metrik (pas) uzakligi tek basina belirler.
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    Z = X / sd

    hedef_konum = list(idx).index(hedef_idx)
    uzaklik = np.linalg.norm(Z - Z[hedef_konum], axis=1)

    out = havuz.loc[idx].copy()
    out["uzaklik"] = uzaklik
    # 0-100'e cevir: kohortun 95. yuzdeligi "tamamen farkli" kabul edilir
    olcek = np.quantile(uzaklik[uzaklik > 0], 0.95) if (uzaklik > 0).any() else 1.0
    out["benzerlik"] = (100.0 * (1.0 - uzaklik / max(olcek, 1e-9))).clip(0, 100)

    out = out[out.index != hedef_idx]
    return out.nsmallest(n, "uzaklik")
