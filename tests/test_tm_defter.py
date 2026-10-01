"""TM ileriye donuk defter testleri (FAZ 7.5)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from scout.model.tm_defter import (MODEL_SURUMU, PENCERE_BITIS, SUTUNLAR,
                                   kayit_tablosu, pencere_kapandi_mi, puanla,
                                   yeni_satirlar)


def _h(n=6):
    return pd.DataFrame({
        "player_id": np.arange(n), "player_name": [f"o{i}" for i in range(n)],
        "comp": ["GB1"] * 3 + ["NL1"] * 3, "season": 2025,
        "pos_group": ["Defender", "Defender", "Attacker"] * 2,
        "deger": [1e6, 9e6, np.nan, 2e6, 6e6, 4e6],
        "deger_var": [1, 1, 0, 1, 1, 1],
        "model": [0.9, 0.4, 0.6, 0.2, 0.7, 0.5], "saf": 0.5, "basit": 0.5,
        "piyasa": 0.5,
    })


def test_kayit_sutunlari_ve_surum():
    k = kayit_tablosu(_h(), dt.date(2026, 10, 1), "2026-07-11")
    assert list(k.columns) == SUTUNLAR
    assert (k.model_surumu == MODEL_SURUMU).all()
    assert (k.kayit_tarihi == "2026-10-01").all()
    assert (k.pencere_bitis == PENCERE_BITIS.isoformat()).all()


def test_siralar_lig_mevki_icinde_ve_mevki_genelinde():
    k = kayit_tablosu(_h(), dt.date(2026, 10, 1), "x")
    gb_def = k[(k.comp == "GB1") & (k.pos_group == "Defender")]
    assert dict(zip(gb_def.player_id, gb_def.sira_lig_mevki)) == {0: 1, 1: 2}
    d = k[k.pos_group == "Defender"].sort_values("sira_mevki")
    assert list(d.player_id) == [0, 4, 1, 3]       # 0.9, 0.7, 0.4, 0.2


def test_ucuz_tavan_5m_degersiz_ucuz_SAYILMAZ():
    """2025 TM'de degerleme yoklugu veri boslugu (Wesley/Roma, Bonny/Inter):
    degersiz oyuncu ucuz sayilmaz, 'bilinmiyor' diye ayri isaretlenir."""
    k = kayit_tablosu(_h(), dt.date(2026, 10, 1), "x").set_index("player_id")
    assert k.loc[0, "ucuz"] and not k.loc[1, "ucuz"]
    assert not k.loc[2, "ucuz"] and k.loc[2, "deger_durumu"] == "bilinmiyor"
    assert k.loc[0, "deger_durumu"] == "var"


def test_ekleme_yalniz_ayni_anahtar_ikinci_kez_yazilmaz():
    k = kayit_tablosu(_h(), dt.date(2026, 10, 1), "x")
    assert len(yeni_satirlar(k, k)) == 0
    assert len(yeni_satirlar(k, k.iloc[:2])) == len(k) - 2
    assert len(yeni_satirlar(k, pd.DataFrame())) == len(k)


def test_pencere_ve_sansur():
    assert not pencere_kapandi_mi(dt.date(2027, 6, 14))
    assert pencere_kapandi_mi(PENCERE_BITIS)
    k = kayit_tablosu(_h(), dt.date(2026, 10, 1), "x")
    s = pd.DataFrame({"player_id": [0, 1], "comp": "GB1", "season": 2025,
                      "kademe": [4.0, 0.0], "pencere_tam": [True, False]})
    p = puanla(k, s).set_index("player_id")
    assert p.loc[0, "gerceklesti"] == 1.0
    assert np.isnan(p.loc[1, "gerceklesti"])       # pencere acik: 0 DEGIL
    assert np.isnan(p.loc[5, "gerceklesti"])       # sonuc satiri yok
