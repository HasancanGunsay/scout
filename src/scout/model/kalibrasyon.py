"""Grup-kosullu Platt kalibrasyonu (FAZ 6.6).

SORUN
Model tek bir havuzda egitiliyor ve 'kapsam' (izlenen lig mi, yalniz sicrama
mi gorunur) bir ozellik DEGIL. Iki grubun taban orani cok farkli (~%59 vs
~%12). Lig-disi tahminde model bu farki kismen kaciriyor: izlenen liglerde
kotumser, dusuk gorunurlukte iyimser.

YONTEM
logit(p_kal) = a_g + b_g * logit(p_ham)     g = grup (or. kapsam)

Ranking'i GRUP ICINDE degistirmez (b_g > 0 oldugu surece monoton). Gruplar
arasi siralamayi degistirir - karisik listelerde bu bilerek istenen etki.

Kucuk grupta (asgari_n / asgari_olumlu alti) global kalibratore duser.
Grup bilinmiyorsa (egitimde gorulmemis) yine global.

METIN URETMEZ.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

EPS = 1e-6
GLOBAL = "__global__"


def _logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def platt_fit(p, y) -> tuple[float, float]:
    """(a, b): logit(p_kal) = a + b*logit(p). Hafif L2 (C=100) - sayisal
    kararlilik icin; pratikte duzenlemesiz."""
    x = _logit(p).reshape(-1, 1)
    y = np.asarray(y, int)
    m = LogisticRegression(C=100.0, max_iter=1000).fit(x, y)
    return float(m.intercept_[0]), float(m.coef_[0, 0])


def platt_uygula(p, ab: tuple[float, float]) -> np.ndarray:
    a, b = ab
    return 1.0 / (1.0 + np.exp(-(a + b * _logit(p))))


def grup_fit(p, y, grup, asgari_n: int = 200, asgari_olumlu: int = 20
             ) -> dict:
    """Grup basina Platt; yetersiz grup global'e duser."""
    p = np.asarray(p, float)
    y = np.asarray(y, int)
    grup = np.asarray(grup, object)
    par = {GLOBAL: platt_fit(p, y)}
    for g in pd.unique(grup):
        m = grup == g
        if m.sum() >= asgari_n and asgari_olumlu <= y[m].sum() <= m.sum() - asgari_olumlu:
            par[g] = platt_fit(p[m], y[m])
    return par


def grup_uygula(p, grup, par: dict) -> np.ndarray:
    p = np.asarray(p, float)
    grup = np.asarray(grup, object)
    out = np.empty_like(p)
    for g in pd.unique(grup):
        m = grup == g
        out[m] = platt_uygula(p[m], par.get(g, par[GLOBAL]))
    return out


def ece(p, y, kova: int = 10) -> float:
    """Beklenen kalibrasyon hatasi: esit-sayili kovalarda |ort tahmin - oran|,
    n agirlikli."""
    d = pd.DataFrame({"p": np.asarray(p, float), "y": np.asarray(y, float)})
    if len(d) < kova * 5:
        return float("nan")
    d["k"] = pd.qcut(d.p.rank(method="first"), kova, labels=False)
    t = d.groupby("k").agg(n=("y", "size"), p=("p", "mean"), y=("y", "mean"))
    return float((t.p - t.y).abs().mul(t.n).sum() / t.n.sum())


def kosullu_ece(p, y, grup, kova: int = 10) -> float:
    """Grup-ici ECE'lerin n-agirlikli ortalamasi.

    Genel ECE, gruplarin zit yonlu hatalarini ayni kovada birbirine
    goturebilir (bir grup kotumser, digeri iyimser). Kosullu ECE bunu gizlemez.
    """
    d = pd.DataFrame({"p": np.asarray(p, float), "y": np.asarray(y, float),
                      "g": np.asarray(grup, object)})
    top, n = 0.0, 0
    for _, s in d.groupby("g"):
        e = ece(s.p, s.y, kova)
        if not np.isnan(e):
            top += e * len(s)
            n += len(s)
    return top / n if n else float("nan")


def brier(p, y) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def logloss(p, y) -> float:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def lolo_kalibre(df: pd.DataFrame, p_kol: str, grup_kol: str | None,
                 lig_kol: str = "league_id", y_kol: str = "y") -> pd.Series:
    """Lig-disarida-birak kalibrasyon: her lig icin kalibrator YALNIZ diger
    liglerin (disaridan) tahminleri + sonuclariyla kurulur.

    grup_kol=None -> tek global Platt.
    """
    out = pd.Series(np.nan, index=df.index)
    grup = (df[grup_kol].astype(str) if grup_kol else
            pd.Series(GLOBAL, index=df.index))
    for lig in df[lig_kol].unique():
        te = (df[lig_kol] == lig).to_numpy()
        tr = ~te
        par = grup_fit(df.loc[tr, p_kol], df.loc[tr, y_kol], grup[tr])
        out[te] = grup_uygula(df.loc[te, p_kol], grup[te], par)
    return out
