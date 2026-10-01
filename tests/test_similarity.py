"""Benzer oyuncu arama testleri.

Kritik ayrim: benzerlik STIL olcmeli, KALITE degil. "Iyi oyuncular
birbirine benzer" sonucu ise yaramaz - scout zaten begendigi oyuncunun
ULASILABILIR benzerini ariyor.

Gercek veride olculdu: stil komsularinin skor farki 15,3; rastgele
oyuncularin 17,5. Yakin olmalari benzerligin kalite vekili OLMADIGINI
gosteriyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scout.features.similarity import STIL_METRIKLERI, benzerler, clr


def _df(n=60, seed=5):
    rng = np.random.default_rng(seed)
    d = {"player_id": range(n),
         "player_name": [f"P{i}" for i in range(n)],
         "minutes": np.full(n, 1500.0),
         "pos_group": ["Attacker"] * (n // 2) + ["Defender"] * (n - n // 2)}
    for m in STIL_METRIKLERI:
        d[m] = rng.uniform(0.2, 6.0, n)
    return pd.DataFrame(d)


class TestCLR:
    def test_olcek_degisimine_duyarsiz(self):
        """CLR olcege duyarsiz olmali.

        Bu OZELLIK onemli: bazi liglerde sayimlar eksik (Segunda Liga
        medyanin %15'i - §21.3). Tum metrikler ayni oranda eksikse
        log-oranlar DEGISMEZ, yani stil vektoru bozulmaz.
        """
        x = np.array([[1.0, 2.0, 4.0], [3.0, 1.0, 2.0]])
        assert np.allclose(clr(x), clr(x * 7.3))

    def test_satir_toplami_sifir(self):
        x = np.array([[1.0, 2.0, 4.0], [3.0, 1.0, 2.0]])
        assert np.allclose(clr(x).sum(axis=1), 0.0, atol=1e-9)


class TestBenzerler:
    def test_ayni_stil_en_yakin(self):
        d = _df()
        # 1 numarayi 0'in tam kopyasi yap
        for m in STIL_METRIKLERI:
            d.loc[1, m] = d.loc[0, m]
        b = benzerler(d, 0, n=3)
        assert b.index[0] == 1
        assert b.iloc[0].benzerlik > 95

    def test_mevki_grubu_disina_cikmaz(self):
        d = _df()
        b = benzerler(d, 0, n=10)
        assert (b.pos_group == d.loc[0, "pos_group"]).all()

    def test_kendisi_sonucta_yok(self):
        d = _df()
        assert 0 not in set(benzerler(d, 0, n=10).index)

    def test_dakika_esigi(self):
        d = _df()
        d.loc[d.index[1:5], "minutes"] = 100.0
        b = benzerler(d, 0, n=20, min_dakika=450)
        assert not set(b.index) & {1, 2, 3, 4}

    def test_olcek_degisimi_komsulari_degistirmez(self):
        """Bir oyuncunun tum metrikleri ayni oranda buyurse stili degismez."""
        d = _df()
        once = list(benzerler(d, 0, n=5).index)
        d2 = d.copy()
        for m in STIL_METRIKLERI:
            d2.loc[0, m] = d2.loc[0, m] * 3.0
        assert list(benzerler(d2, 0, n=5).index) == once
