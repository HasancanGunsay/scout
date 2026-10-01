"""Zaman icinde kalibrasyon kurallari testleri (FAZ 7.3)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.kalibrasyon import kesisim_fit, platt_uygula
from scout.model.zaman_kalibrasyon import KURALLAR, kalibre


def _gecmis(seed=0):
    rng = np.random.default_rng(seed)
    parca = []
    for s, kayma in [(2014, -0.5), (2015, 0.0), (2016, 0.8)]:
        p = rng.uniform(0.05, 0.95, 3000)
        gercek = 1 / (1 + np.exp(-(np.log(p / (1 - p)) + kayma)))
        parca.append(pd.DataFrame({"season": s, "p": p,
                                   "y": (rng.uniform(size=p.size) < gercek).astype(int)}))
    return pd.concat(parca, ignore_index=True)


@pytest.mark.parametrize("kural", KURALLAR)
def test_gelecegi_gormez(kural):
    """Hedef sezon ve sonrasinin verisi sonucu DEGISTIRMEMELI."""
    g = _gecmis()
    p = np.linspace(0.1, 0.9, 9)
    a = kalibre(g, p, 2016, kural)
    bozuk = g.copy()
    bozuk.loc[bozuk.season >= 2016, "y"] = 1 - bozuk.loc[bozuk.season >= 2016, "y"]
    gelecek = pd.DataFrame({"season": 2017, "p": [0.5] * 50, "y": [1] * 50})
    b = kalibre(pd.concat([bozuk, gelecek]), p, 2016, kural)
    assert np.allclose(a, b)


def test_ham_kimlik_ve_gecmis_yoksa_dokunmaz():
    p = np.array([0.2, 0.7])
    assert np.allclose(kalibre(_gecmis(), p, 2016, "ham"), p)
    assert np.allclose(kalibre(_gecmis(), p, 2014, "tum_gecmis"), p)


def test_kesisim_ortalamayi_tutturur():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.1, 0.9, 5000)
    y = (rng.uniform(size=p.size) < 0.7).astype(int)
    a, b = kesisim_fit(p, y)
    assert b == 1.0
    assert platt_uygula(p, (a, b)).mean() == pytest.approx(y.mean(), abs=1e-4)


def test_son1_yalniz_son_sezona_bakar_agirlikli_ise_karisik():
    """2016'yi tahmin ederken son sezon 2015 (kayma 0): son1 ~ kimlik;
    tum_gecmis 2014'un -0,5 kaymasini da tasir."""
    g = _gecmis()
    p = np.array([0.5])
    assert kalibre(g, p, 2016, "son1")[0] == pytest.approx(0.5, abs=0.03)
    assert kalibre(g, p, 2016, "tum_gecmis")[0] < kalibre(g, p, 2016, "son1")[0]
    ag = kalibre(g, p, 2016, "agirlikli")[0]
    assert kalibre(g, p, 2016, "tum_gecmis")[0] < ag


def test_bilinmeyen_kural():
    with pytest.raises(ValueError):
        kalibre(_gecmis(), [0.5], 2016, "yok_boyle")
