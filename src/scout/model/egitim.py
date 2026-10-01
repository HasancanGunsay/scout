"""Model egitim yardimcilari - tum modeller (API, TM) AYNI hatti kullanir.

FAZ 7.2'de scripts/train_model.py'den tasindi: TM tarihsel modeli de ayni
egitim, eksik-doldurma ve lig-disi CV kurallarini kullanmali, ve src/
scripts/'ten ice aktarma yapmamali. train_model bu adlari yeniden disa
aktarir; mevcut cagrilar degismez.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


_UYARILDI: set[str] = set()


def _hazirla(df: pd.DataFrame, kolonlar: list[str], ref: pd.DataFrame | None = None):
    """Eksikleri EGITIM medyaniyla doldur.

    ref: medyanin hesaplanacagi EGITIM kumesi. Verilmezse df'in kendisi.

    HATA (30 Eyl 2026'da bulundu): onceki surum eksikleri df'in KENDI
    medyaniyla dolduruyordu. Test kumesi icin bu, test dagilimindan bilgi
    sizdirir (kucuk ama gercek) ve daha kotusu TEK SATIRLIK tahminde
    medyan o satirin kendisi olur: eksik deger NaN kalir -> 0.0'a duser.
    score_age icin ham 0 cok uc bir degerdir. Toplu degerlendirmede etkisi
    ihmal edilebilir; tek oyunculuk siralamada (Scout dosyasi) ciddi olurdu.
    """
    X = df[kolonlar].apply(pd.to_numeric, errors="coerce")
    R = X if ref is None else ref[kolonlar].apply(pd.to_numeric, errors="coerce")
    for c in [c for c in kolonlar if R[c].isna().all()]:
        if c not in _UYARILDI:
            print(f"  ! ozellik EGITIMDE TAMAMEN BOS, katkisi olmayacak: {c}")
            _UYARILDI.add(c)
    med = R.median().fillna(0.0)
    return X.fillna(med).to_numpy(float)


def egit(Xtr, ytr, Xte, C=1.0):
    """L2 duzenlilestirilmis lojistik. Standartlastirma iceride."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    m = make_pipeline(StandardScaler(),
                      LogisticRegression(C=C, max_iter=2000))
    m.fit(Xtr, ytr)
    return m, m.predict_proba(Xte)[:, 1]


def lolo_cv(df: pd.DataFrame, kolonlar: list[str], C: float) -> pd.Series:
    """Lig-disarida-birak: her lig bir kez test, hep digerleriyle egitilir.

    Sezon bazli bolmek yetmez - ayni ligin baska sezonu modele o ligin
    tuhafliklarini ogretir. Genelleme sorusunun dogru kurulusu 'hic
    gormedigi ligde ne yapiyor'.
    """
    tah = pd.Series(np.nan, index=df.index)
    for lig in df.league_id.unique():
        te = df.league_id == lig
        tr = ~te
        if ytr_yetersiz(df.loc[tr, "y"]) or te.sum() < 10:
            continue
        _, p = egit(_hazirla(df[tr], kolonlar), df.loc[tr, "y"].to_numpy(),
                    _hazirla(df[te], kolonlar, ref=df[tr]), C)
        tah[te] = p
    return tah


def ytr_yetersiz(y: pd.Series) -> bool:
    return y.nunique() < 2 or y.sum() < 20
