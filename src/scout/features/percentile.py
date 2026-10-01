"""Percentile donusumu - metrikleri ortak bir 0-100 skalasina tasir.

Neden gerekli: "1.4 top calma/90" ile "0.31 gol/90" toplanamaz. Once her
metrik kendi kohortu icinde siraya sokulup 0-100'e cevrilir, sonra
agirliklandirilabilir.

Kohort = (lig, sezon, mevki grubu). Bir stoperin top calma sayisi sadece
diger stoperlerle kiyaslanir.

DIKKAT: Ligler arasi percentile karsilastirmasi lig gucu duzeltmesinden
(§5.2) ONCE anlamsizdir. Serie B'de 90. percentile ile Ligue 1'de 90.
percentile ayni sey degildir. Bu modul kohort ICI siralama uretir;
ligler arasi birlestirme lig gucu katsayisi uygulandiktan sonra yapilir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def percentile_in_cohort(
    df: pd.DataFrame,
    cols: list[str],
    *,
    cohort: list[str],
    min_size: int = 12,
    suffix: str = "_pct",
) -> pd.DataFrame:
    """Her metrigi kendi kohortu icinde 0-100 percentile'a cevir.

    min_size : bu sayidan kucuk kohortlarda percentile uretilmez (NaN).
               8 kisilik bir havuzda "85. percentile" demek anlamsiz.
    """
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            continue
        res = pd.Series(np.nan, index=out.index, dtype=float)
        for _, idx in out.groupby(cohort, dropna=False).groups.items():
            vals = out.loc[idx, c]
            if vals.notna().sum() < min_size:
                continue
            # average: esit degerler ayni percentile alir
            res.loc[idx] = vals.rank(pct=True, method="average") * 100.0
        out[f"{c}{suffix}"] = res
    return out


def invert(df: pd.DataFrame, cols: dict[str, str], suffix: str = "_pct") -> pd.DataFrame:
    """Dusuk olmasi iyi olan metrikleri ters cevir (faul, kart, yenilen gol).

    Boylece TUM percentile'larda 'yuksek = iyi' kurali gecerli olur ve
    agirlikli toplam anlamli hale gelir.

    cols : {sablon_anahtari: sutun_tabani}
           ornegin {"fouls_made": "fouls_made_p90_sh"}

    NEDEN SOZLUK: cevrilen her metrik icin '<sablon_anahtari>_inverted'
    isaret sutunu birakiyoruz. scoring/engine.py bu isarete bakip ikinci kez
    cevirmiyor. Isaret yokken CIFT TERS CEVIRME oluyordu: percentile.invert
    bir kez, engine bir kez daha cevirince "cok faul = iyi" haline geliyordu
    ve savunma sablonlarinda agirligin %8'i ters isliyordu (§16).
    """
    out = df.copy()
    for key, base in cols.items():
        col = f"{base}{suffix}"
        if col in out.columns:
            out[col] = 100.0 - out[col]
            out[f"{key}_inverted"] = True
    return out


def cohort_sizes(df: pd.DataFrame, cohort: list[str]) -> pd.DataFrame:
    """Kohort buyuklukleri - percentile'lara guvenilir mi diye bakmak icin."""
    return (
        df.groupby(cohort, dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
    )
