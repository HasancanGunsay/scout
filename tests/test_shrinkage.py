"""Empirical Bayes shrinkage testleri.

NEDEN ONEMLI: shrinkage'in ILK SURUMU tum sinyali yok ediyordu. Moment
yontemi negatif tau^2 uretiyor, sifira kirpiliyor ve HERKES ortalamaya
cokuyordu - 2390 dakikada 17 gol atan oyuncuyla 37 dakikada 1 gol atan
oyuncu ayni skoru aliyordu. Bunu ancak elle denetleyerek yakaladik.

Bu testler o hatanin sessizce geri gelmesini engeller.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.shrinkage import beta_binomial_shrink, poisson_gamma_shrink


def _cohort(n=200, seed=0):
    """Gercekci kohort: farkli dakika, farkli gercek yetenek."""
    rng = np.random.default_rng(seed)
    nineties = rng.uniform(0.5, 35, n)
    true_rate = rng.gamma(shape=4, scale=0.075, size=n)  # ort ~0.30
    counts = rng.poisson(true_rate * nineties)
    return pd.Series(counts, dtype=float), pd.Series(nineties)


class TestPoissonGamma:
    def test_agirlik_dakikayla_artar(self):
        """Cok oynayan oyuncunun kendi verisine daha cok guvenilmeli."""
        c, n = _cohort()
        _, w, _ = poisson_gamma_shrink(c, n)
        dusuk = w[n < 5].mean()
        yuksek = w[n > 25].mean()
        assert yuksek > dusuk * 3, f"az dakika {dusuk:.3f} vs cok dakika {yuksek:.3f}"

    def test_sinyal_yok_olmuyor(self):
        """ILK SURUMUN HATASI: tum degerler ortalamaya cokuyordu.

        Cekilmis degerlerin varyansi sifira yakin olmamali.
        """
        c, n = _cohort()
        sh, _, _ = poisson_gamma_shrink(c, n)
        yeterli = sh[n > 15]
        assert yeterli.std() > 0.02, (
            f"cekilmis degerlerin std'si {yeterli.std():.4f} - "
            "shrinkage sinyali yok etmis"
        )

    def test_siralama_korunur(self):
        """Ayni dakikada daha cok gol atan, daha yuksek cekilmis deger almali."""
        c = pd.Series([2.0, 10.0, 20.0] + [5.0] * 50)
        n = pd.Series([20.0, 20.0, 20.0] + [20.0] * 50)
        sh, _, _ = poisson_gamma_shrink(c, n)
        assert sh.iloc[0] < sh.iloc[1] < sh.iloc[2]

    def test_agirlik_0_1_araliginda(self):
        c, n = _cohort()
        _, w, _ = poisson_gamma_shrink(c, n)
        assert w.min() >= 0 and w.max() <= 1

    def test_asiri_deger_ortalamaya_cekilir(self):
        """1 dakikada 1 gol = 90 gol/90. Bu ciddiye alinmamali."""
        c, n = _cohort()
        c = pd.concat([c, pd.Series([1.0])], ignore_index=True)
        n = pd.concat([n, pd.Series([0.011])], ignore_index=True)  # ~1 dakika
        sh, w, _ = poisson_gamma_shrink(c, n)
        assert sh.iloc[-1] < 2.0, f"asiri deger {sh.iloc[-1]:.1f} olarak kalmis"
        assert w.iloc[-1] < 0.05

    def test_kucuk_kohort_ham_deger_dondurur(self):
        c = pd.Series([1.0, 2.0, 3.0])
        n = pd.Series([10.0, 10.0, 10.0])
        sh, w, _ = poisson_gamma_shrink(c, n)
        assert (w == 1.0).all()
        assert np.allclose(sh, c / n)

    def test_sifir_maruziyet_cokmez(self):
        c, n = _cohort()
        n.iloc[0] = 0.0
        sh, w, se = poisson_gamma_shrink(c, n)
        assert len(sh) == len(c)


class TestBetaBinomial:
    def test_agirlik_denemeyle_artar(self):
        """Cok mucadeleye giren oyuncunun oranina daha cok guvenilmeli.

        Not: agirlik 1'e doydugu icin 'kat' iddiasi anlamsiz - monotonluk
        ve dusuk tarafta belirgin cekme aranir.
        """
        rng = np.random.default_rng(1)
        t = pd.Series(rng.uniform(5, 400, 200))
        p = rng.beta(6, 6, 200)
        s = pd.Series(rng.binomial(t.astype(int), p), dtype=float)
        _, w, _ = beta_binomial_shrink(s, t)
        yuksek, dusuk = w[t > 300].mean(), w[t < 20].mean()
        assert yuksek > dusuk, f"cok deneme {yuksek:.3f} <= az deneme {dusuk:.3f}"
        assert yuksek > 0.85, "cok denemede kendi verisine guvenilmeli"
        assert dusuk < 0.70, "az denemede belirgin cekme olmali"

    def test_oran_0_1_araliginda(self):
        rng = np.random.default_rng(2)
        t = pd.Series(rng.uniform(5, 200, 150))
        s = pd.Series(rng.binomial(t.astype(int), 0.55), dtype=float)
        sh, _, _ = beta_binomial_shrink(s, t)
        assert sh.min() >= 0 and sh.max() <= 1

    def test_az_denemede_ortalamaya_yakin(self):
        """2 mucadelede 2 kazanma = %100. Bu %100 olarak kalmamali."""
        rng = np.random.default_rng(3)
        t = pd.Series(list(rng.uniform(50, 300, 100)) + [2.0])
        s = pd.Series(list(rng.binomial(t[:100].astype(int), 0.5).astype(float)) + [2.0])
        sh, _, _ = beta_binomial_shrink(s, t)
        assert sh.iloc[-1] < 0.85, f"az deneme %{100*sh.iloc[-1]:.0f} olarak kalmis"
