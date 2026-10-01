"""Esleştirilmis kontrol grubu testleri (FAZ 6.4)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.kontrol import eslestir, fark_tablosu, kume_bootstrap


def _df(n=200, seed=1):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "player_id": np.arange(n),
        "mevki": rng.choice(["D", "M"], n),
        "yas": rng.uniform(18, 22, n),
        "dk": rng.uniform(500, 3000, n),
        "sonuc": rng.normal(0, 1, n),
    })


def test_kesin_esitlik_zorunlu():
    h = _df()
    t = h.iloc[:20]
    e = eslestir(t, h, ["yas", "dk"], kesin=["mevki"], k=5)
    for ix, kont in e.items():
        assert (h.loc[kont, "mevki"] == h.loc[ix, "mevki"]).all()


def test_kendisi_ve_ayni_oyuncu_kontrol_olamaz():
    h = _df()
    t = h.iloc[:30]
    e = eslestir(t, h, ["yas", "dk"], k=5)
    for ix, kont in e.items():
        assert ix not in kont
        assert (h.loc[kont, "player_id"] != h.loc[ix, "player_id"]).all()


def test_ayni_oyuncunun_baska_satiri_kontrol_olamaz():
    """Ayni oyuncu iki sezonda: birinin kontrolu digeri olamaz."""
    h = _df(50)
    ikinci = h.iloc[[0]].copy()
    ikinci.index = [999]
    h = pd.concat([h, ikinci])
    e = eslestir(h.loc[[0]], h, ["yas", "dk"], k=5)
    assert 999 not in e[0]


def test_en_yakin_gercekten_en_yakin():
    h = _df(300, seed=3)
    h.loc[0, ["yas", "dk"]] = [20.0, 1500.0]
    h.loc[1, ["yas", "dk"]] = [20.0, 1501.0]        # neredeyse ozdes
    e = eslestir(h.loc[[0]], h, ["yas", "dk"], k=1)
    assert e[0][0] == 1


def test_yetersiz_aday_zorlama_eslesme_yok():
    h = _df(6)
    e = eslestir(h.iloc[:1], h, ["yas"], kesin=["player_id"], k=5, asgari=2)
    assert e == {}


def test_fark_nan_sifir_sayilmaz():
    """Kontrolde sonuc yoksa fark NaN olmali, 0 degil."""
    h = pd.DataFrame({"player_id": [1, 2, 3], "x": [1.0, np.nan, np.nan]})
    f = fark_tablosu(h.loc[[0]], h, {0: np.array([1, 2])}, ["x"])
    assert np.isnan(f.x.iloc[0])


def test_fark_kontrol_ortalamasi():
    h = pd.DataFrame({"player_id": [1, 2, 3], "x": [10.0, 2.0, 4.0]})
    f = fark_tablosu(h.loc[[0]], h, {0: np.array([1, 2])}, ["x"])
    assert f.x.iloc[0] == pytest.approx(10.0 - 3.0)


def test_bootstrap_sifir_etkide_araligi_sifiri_kapsar():
    rng = np.random.default_rng(0)
    f = pd.DataFrame({"player_id": np.arange(400),
                      "x": rng.normal(0, 1, 400)})
    o, lo, hi, n = kume_bootstrap(f, "x", B=500, rng=rng)
    assert lo < 0 < hi and n == 400


def test_bootstrap_gercek_etkiyi_yakalar():
    rng = np.random.default_rng(1)
    f = pd.DataFrame({"player_id": np.arange(400),
                      "x": rng.normal(0.5, 1, 400)})
    o, lo, hi, n = kume_bootstrap(f, "x", B=500, rng=rng)
    assert lo > 0


def test_bootstrap_oyuncu_bazli_araligi_genisletir():
    """Ayni oyuncunun tekrarli satirlari GA'yi yapay daraltmamali."""
    rng = np.random.default_rng(2)
    deger = rng.normal(0, 1, 40)
    tek = pd.DataFrame({"player_id": np.arange(40), "x": deger})
    tekrar = pd.DataFrame({"player_id": np.repeat(np.arange(40), 5),
                           "x": np.repeat(deger, 5)})
    _, lo1, hi1, _ = kume_bootstrap(tek, "x", B=1000, rng=np.random.default_rng(3))
    _, lo2, hi2, _ = kume_bootstrap(tekrar, "x", B=1000, rng=np.random.default_rng(3))
    # kumelenmis bootstrap: 5x tekrar GA'yi belirgin daraltmamali
    assert (hi2 - lo2) > 0.7 * (hi1 - lo1)


def test_bootstrap_az_ornekte_nan():
    f = pd.DataFrame({"player_id": [1, 2], "x": [1.0, 2.0]})
    assert np.isnan(kume_bootstrap(f, "x")[0])
