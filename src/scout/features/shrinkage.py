"""Empirical Bayes shrinkage - §1.2'nin cozumu.

PROBLEM: 6 macta 4 gol atan 18 yasindaki cocuk, 34 macta 12 gol atandan
"daha iyi" gorunur. Az dakikada per-90 degerleri gurultuden ibarettir.
Sistem bu cocugu listenin tepesine koyarsa sana bosuna 90 dakika izletir.

COZUM: Her oyuncunun gozlenen orani, kendi kohortunun ortalamasina dogru
cekilir. Ne kadar cekilecegi kanitin gucune baglidir:
  - cok dakika / cok mucadele -> az cekilir (kendi verisine guvenilir)
  - az dakika  / az mucadele  -> cok cekilir (ortalamaya yakinsar)

Iki model, iki metrik ailesi icin (bkz. metrics.py):

  SAYIM  -> Poisson-Gamma
     Oran x = sayi/90'lik. Poisson varyansi: Var(x) = mu / n
     Cekme agirligi:  w = tau^2 / (tau^2 + mu/n)
     tau^2 = oyuncular ARASI gercek yetenek varyansi (moment yontemiyle)

  ORAN   -> Beta-Binom
     alpha, beta kohorttan moment yontemiyle kestirilir
     Cekilmis oran = (basari + alpha) / (deneme + alpha + beta)
     alpha+beta, "kac deneme kadar on bilgi" anlamina gelir

Her iki durumda da bir GUVEN ARALIGI uretilir - arayuz bunu gosterir ki
scout, skorun ne kadar saglam oldugunu gorsun.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import betaln, gammaln


def _fit_gamma_poisson(c: np.ndarray, n: np.ndarray) -> tuple[float, float]:
    """Gamma onselini marjinal negatif-binom olabilirligiyle kestir.

    NEDEN MOMENT YONTEMI DEGIL: moment yontemi (var_total - var_sampling)
    kohortta cok sayida dusuk dakikali oyuncu varken NEGATIF tau^2 uretiyor
    ve herkes ortalamaya cokuyor. Olculdu: Serie B forvetlerinde
    tau^2 = -0.002 cikti, sinyal tamamen yok oldu.

    Maksimum olabilirlik her zaman gecerli bir onsel verir ve dusuk
    maruziyeti dogru agirliklandirir.

    Model:  theta_i ~ Gamma(alpha, beta),  c_i ~ Poisson(theta_i * n_i)
    Marjinal: c_i ~ NegBin(alpha, beta/(beta+n_i))

    Returns (alpha, beta);  ortalama = alpha/beta,  varyans = alpha/beta^2
    """
    def nll(params: np.ndarray) -> float:
        # Nelder-Mead parametre uzayini tararken np.exp TASAR; bu beklenen
        # ve zararsizdir - hemen altindaki isfinite kontrolu yakalar ve
        # optimizer geri ceker. Uyariyi bastirmasak log'a binlerce satir
        # yaziyor ve GERCEK bir uyariyi gozden kacirmamiza yol aciyordu.
        with np.errstate(over="ignore", invalid="ignore"):
            a, b = np.exp(params)
            if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
                return 1e12
            # p -> 1 oldugunda log1p(-p) = -inf; c=0 iken 0*(-inf) = nan olur.
            # Bu yuzden p'yi kirp ve c=0 terimlerini ayri ele al.
            p = np.clip(b / (b + n), 1e-12, 1 - 1e-12)
            ll = (
                gammaln(c + a) - gammaln(a) - gammaln(c + 1)
                + a * np.log(p)
                + np.where(c > 0, c * np.log1p(-p), 0.0)
            )
            if not np.all(np.isfinite(ll)):
                return 1e12
            return -float(np.sum(ll))

    # Baslangic: moment yontemi (negatifse makul bir varsayilan)
    mu0 = max(c.sum() / n.sum(), 1e-6)
    rates = c / n
    var0 = max(float(np.var(rates)) - mu0 * float(np.mean(1.0 / n)), mu0 * mu0 * 0.25)
    b0 = max(mu0 / var0, 1e-3)
    a0 = max(mu0 * b0, 1e-3)

    res = minimize(nll, np.log([a0, b0]), method="Nelder-Mead",
                   options={"maxiter": 800, "xatol": 1e-6, "fatol": 1e-6})
    if not res.success and not np.isfinite(res.fun):
        return a0, b0
    a, b = np.exp(res.x)
    return float(a), float(b)


def poisson_gamma_shrink(
    counts: pd.Series,
    exposure: pd.Series,
    *,
    min_exposure: float = 0.5,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Sayim metrigi icin EB shrinkage (Gamma-Poisson, maksimum olabilirlik).

    Parameters
    ----------
    counts   : ham sayim (gol, sut, top calma...)
    exposure : maruziyet - burada 90'lik sayisi

    Returns
    -------
    (cekilmis_oran, cekme_agirligi, standart_hata)
    """
    c = pd.to_numeric(counts, errors="coerce")
    n = pd.to_numeric(exposure, errors="coerce")
    ok = c.notna() & n.notna() & (n >= min_exposure)

    if ok.sum() < 10:
        # Kohort cok kucuk - kestirim yapmak yerine ham degeri dondur
        rate = c / n.replace(0, np.nan)
        return rate, pd.Series(1.0, index=c.index), pd.Series(np.nan, index=c.index)

    alpha, beta = _fit_gamma_poisson(c[ok].to_numpy(float), n[ok].to_numpy(float))

    # Sonsal ortalama: (alpha + c) / (beta + n)
    denom = beta + n
    shrunk = (alpha + c) / denom
    weight = (n / denom).clip(0, 1)          # kanitin agirligi
    se = np.sqrt(alpha + c) / denom          # sonsal standart sapma

    return shrunk.astype(float), weight.astype(float), se.astype(float)


def beta_binomial_shrink(
    successes: pd.Series,
    trials: pd.Series,
    *,
    min_trials: float = 1.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Oran metrigi icin EB shrinkage (ikili mucadele %, dribbling % ...).

    Returns
    -------
    (cekilmis_oran, cekme_agirligi, standart_hata)
    """
    s = pd.to_numeric(successes, errors="coerce")
    t = pd.to_numeric(trials, errors="coerce")
    ok = s.notna() & t.notna() & (t >= min_trials)

    if ok.sum() < 10:
        rate = s / t.replace(0, np.nan)
        return rate, pd.Series(1.0, index=s.index), pd.Series(np.nan, index=s.index)

    ss = s[ok].to_numpy(float)
    tt = t[ok].to_numpy(float)

    # Beta onselini marjinal beta-binom olabilirligiyle kestir
    # (sayim tarafiyla ayni gerekce - moment yontemi kararsiz)
    def nll(params: np.ndarray) -> float:
        # Sayim tarafiyla ayni gerekce: tasma beklenen, isfinite yakaliyor.
        with np.errstate(over="ignore", invalid="ignore"):
            a, b = np.exp(params)
            if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
                return 1e12
            return -float(np.sum(betaln(ss + a, tt - ss + b) - betaln(a, b)))

    mu0 = float(np.clip(ss.sum() / tt.sum(), 1e-6, 1 - 1e-6))
    rates = ss / tt
    var0 = max(float(np.var(rates)) - mu0 * (1 - mu0) * float(np.mean(1.0 / tt)),
               mu0 * (1 - mu0) * 0.05)
    conc0 = max(mu0 * (1 - mu0) / var0 - 1.0, 1e-3)
    a0, b0 = max(mu0 * conc0, 1e-3), max((1 - mu0) * conc0, 1e-3)

    res = minimize(nll, np.log([a0, b0]), method="Nelder-Mead",
                   options={"maxiter": 800, "xatol": 1e-6, "fatol": 1e-6})
    alpha, beta = (np.exp(res.x) if np.isfinite(res.fun) else (a0, b0))

    denom = t + alpha + beta
    shrunk = (s + alpha) / denom
    weight = (t / denom).clip(0, 1)
    se = np.sqrt(shrunk * (1 - shrunk) / denom)

    return shrunk.astype(float), weight.astype(float), se.astype(float)


def shrink_by_cohort(
    df: pd.DataFrame,
    *,
    cohort: list[str],
    count_specs: dict[str, tuple[str, str]] | None = None,
    rate_specs: dict[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Kohort bazinda (ornegin lig+sezon+mevki grubu) shrinkage uygula.

    Kohort secimi onemli: bir stoperi forvetlerle ayni havuzda cekmek
    sacma olur. Ayni sekilde ligler arasi karsilastirma lig gucu
    duzeltmesinden ONCE yapilamaz (§5.2).
    """
    out = df.copy()
    count_specs = count_specs or {}
    rate_specs = rate_specs or {}

    for name, (cnt_col, exp_col) in count_specs.items():
        sh = pd.Series(np.nan, index=out.index, dtype=float)
        wt = pd.Series(np.nan, index=out.index, dtype=float)
        se = pd.Series(np.nan, index=out.index, dtype=float)
        for _, idx in out.groupby(cohort, dropna=False).groups.items():
            g = out.loc[idx]
            a, b, c = poisson_gamma_shrink(g[cnt_col], g[exp_col])
            sh.loc[idx], wt.loc[idx], se.loc[idx] = a, b, c
        out[f"{name}_sh"] = sh
        out[f"{name}_w"] = wt
        out[f"{name}_se"] = se

    for name, (num_col, den_col) in rate_specs.items():
        sh = pd.Series(np.nan, index=out.index, dtype=float)
        wt = pd.Series(np.nan, index=out.index, dtype=float)
        se = pd.Series(np.nan, index=out.index, dtype=float)
        for _, idx in out.groupby(cohort, dropna=False).groups.items():
            g = out.loc[idx]
            a, b, c = beta_binomial_shrink(g[num_col], g[den_col])
            sh.loc[idx], wt.loc[idx], se.loc[idx] = a, b, c
        out[f"{name}_sh"] = sh
        out[f"{name}_w"] = wt
        out[f"{name}_se"] = se

    return out
