"""Siralama modeli olcum araci testleri (FAZ 2).

Bu dosyanin korudugu sey MODEL degil, MODELI OLCEN ARAC. Yanlis olcen bir
arac, yanlis modeli benimsetir - 29 Agu denetiminde tam bu oldu (esli
olmayan bootstrap gercek farklari 'anlamsiz' gostermisti, §31).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.ranker import (HEDEF_KADEME, _auc, esli_bootstrap, fark_ga,
                                hedef, lig_ici_auc)


def test_hedef_kademe_3_ve_ustu():
    k = pd.Series([0, 1, 2, 3, 4])
    assert list(hedef(k)) == [0, 0, 0, 1, 1]
    assert HEDEF_KADEME == 3


# ------------------------------------------------------------------ AUC
def test_auc_mukemmel_ayrim():
    assert _auc(np.array([0, 0, 1, 1]), np.array([1.0, 2.0, 3.0, 4.0])) == 1.0


def test_auc_ters_ayrim():
    assert _auc(np.array([1, 1, 0, 0]), np.array([1.0, 2.0, 3.0, 4.0])) == 0.0


def test_auc_beraberlik_yarim():
    assert _auc(np.array([0, 1]), np.array([1.0, 1.0])) == 0.5


def test_auc_tek_sinif_nan():
    assert np.isnan(_auc(np.array([1, 1, 1]), np.array([1.0, 2.0, 3.0])))


# --------------------------------------------------------- lig ici AUC
def _iki_lig():
    """Lig A'da yuksek skorlar olumlu, lig B'de de oyle.

    AMA liglerin taban oranlari ve skor olcekleri farkli. Havuzlanmis AUC
    bu farki 'model iyi ayirt ediyor' diye okur; lig ici AUC okumamali.
    """
    a = pd.DataFrame({"league_id": 1, "season": 2022,
                      "player_id": range(100),
                      "skor": np.linspace(0, 1, 100),
                      "y": [0] * 50 + [1] * 50})
    b = pd.DataFrame({"league_id": 2, "season": 2022,
                      "player_id": range(100, 200),
                      "skor": np.linspace(10, 11, 100),   # bambaska olcek
                      "y": [0] * 50 + [1] * 50})
    return pd.concat([a, b], ignore_index=True)


def test_lig_ici_auc_olcek_farkindan_etkilenmez():
    """Lig B'nin skorlari 10 kat buyuk ama ayrim gucu ayni -> AUC 1.0."""
    assert lig_ici_auc(_iki_lig(), "skor") == pytest.approx(1.0)


def test_havuzlanmis_auc_lig_farkini_yetenek_sanir():
    """ASIL TUZAK: taban oranlari farkli iki lig.

    Lig A zayif (%20 olumlu, dusuk skorlar), lig B guclu (%80 olumlu,
    yuksek skorlar). Her ligin ICINDE skorun ayirt etme gucu SIFIR.
    Havuzlanmis AUC yine de yuksek cikar - cunku modelin yaptigi tek sey
    ligi tanimak. Lig ici AUC bu tuzaga dusmemeli (~0,5).
    """
    rng = np.random.default_rng(7)
    a = pd.DataFrame({"league_id": 1, "season": 2022,
                      "player_id": range(300),
                      "skor": rng.uniform(0, 1, 300),
                      "y": rng.binomial(1, 0.2, 300)})
    b = pd.DataFrame({"league_id": 2, "season": 2022,
                      "player_id": range(300, 600),
                      "skor": rng.uniform(10, 11, 300),
                      "y": rng.binomial(1, 0.8, 300)})
    d = pd.concat([a, b], ignore_index=True)

    havuz = _auc(d.y.to_numpy(), d.skor.to_numpy())
    ici = lig_ici_auc(d, "skor")
    assert havuz > 0.70, "kurgu yanlis: havuzlanmis AUC yuksek cikmaliydi"
    assert abs(ici - 0.5) < 0.06, f"lig ici AUC tuzaga dustu: {ici:.3f}"
    assert havuz - ici > 0.20


def test_lig_ici_auc_olumlu_ornekle_agirlikli():
    """3 olumlu ornekli lig, 100 olumlu ornekli ligle esit sayilmamali."""
    kucuk = pd.DataFrame({"league_id": 1, "season": 2022,
                          "player_id": range(6),
                          "skor": [1.0, 2, 3, 4, 5, 6],
                          "y": [1, 1, 1, 0, 0, 0]})       # TERS: AUC 0
    buyuk = pd.DataFrame({"league_id": 2, "season": 2022,
                          "player_id": range(6, 206),
                          "skor": np.linspace(0, 1, 200),
                          "y": [0] * 100 + [1] * 100})     # AUC 1
    d = pd.concat([kucuk, buyuk], ignore_index=True)
    # agirliksiz olsaydi (0 + 1) / 2 = 0.50; agirlikli olmali -> 1'e yakin
    assert lig_ici_auc(d, "skor") > 0.95


# ------------------------------------------------------------ bootstrap
def test_bootstrap_esli_ayni_kolonlar():
    d = _iki_lig()
    d["skor2"] = d.skor
    bs = esli_bootstrap(d, ["skor", "skor2"], B=30)
    assert set(bs.columns) == {"skor", "skor2"}
    # ayni kolonun kendisiyle farki tam sifir olmali - esli oldugunun kaniti
    o, lo, hi = fark_ga(bs, "skor", "skor2")
    assert o == pytest.approx(0.0, abs=1e-9)
    assert lo == pytest.approx(0.0, abs=1e-9)
    assert hi == pytest.approx(0.0, abs=1e-9)


def test_bootstrap_oyuncu_bazli():
    """Ayni oyuncunun iki sezonu birlikte secilmeli.

    Satir bazli ornekleme guven araligini yapay olarak daraltir - ayni
    oyuncunun iki satiri bagimsiz gozlem degil.
    """
    rng = np.random.default_rng(0)
    d = pd.DataFrame({
        "league_id": 1,
        "season": np.tile([2022, 2023], 50),      # her oyuncu iki sezon
        "player_id": np.repeat(np.arange(50), 2),
        "skor": rng.normal(size=100),
        # y sezon icinde DEGISMELI - yoksa grup tek sinifli olur ve
        # AUC tanimsiz doner (ilk fiksturde tam bu olmustu)
        "y": rng.binomial(1, 0.5, 100)})
    bs = esli_bootstrap(d, ["skor"], B=20)
    assert len(bs) == 20
    assert bs.skor.notna().any()


def test_fark_ga_az_ornekte_nan():
    bs = pd.DataFrame({"a": [0.1, 0.2], "b": [0.05, 0.1]})
    o, lo, hi = fark_ga(bs, "a", "b")
    assert np.isnan(o) and np.isnan(lo) and np.isnan(hi)
