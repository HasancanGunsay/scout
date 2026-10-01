"""Scout dosyasi testleri (FAZ 4).

EN KRITIK TEST: src/ METIN URETMEZ. Bu ayrim bir kez ihlal edildi ve
sayfada Turkce arayuzun ortasinda ASCII cumleler goruldu (§35.6).
test_metin_uretmez bunu kilitliyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.dosya import (ASGARI_SEZON, DAKIKA_GUVENSIZ, DEGER_YOK,
                                  EKSIK_METRIK, KAPSAM_ESIGI, KUCUK_ORNEKLEM,
                                  LIG_BOZUK, SONUC_GORUNMEZ, TEK_SEZON,
                                  YAS_SINIR, YAS_SINIRDA, GENEL_KOR,
                                  MEVKIYE_KOR, kademe_kodu, katki_tablosu,
                                  kor_noktalar, riskler)

TEMIZ = dict(minutes=2500, coverage=1.0, lig_bozuk=False, kapsam="tam",
             deger_var=1, n_sezon=3, yas=19.0)


def _kodlar(r):
    return [k for k, _ in riskler(r)]


# ------------------------------------------------------- metin ayrimi
def test_metin_uretmez():
    """src/ dilden bagimsiz kalmali - Turkce cumleyi arayuz kuruyor.

    riskler() metin degil KOD dondurmeli; kod adlari ASCII olmali.
    """
    r = dict(TEMIZ, minutes=100, kapsam="sicrama_only", deger_var=0)
    for kod, baglam in riskler(r):
        assert kod.isascii() and " " not in kod, f"metin sizmis: {kod}"
        assert isinstance(baglam, dict)
    for kod in kor_noktalar("Attacker"):
        assert kod.isascii() and " " not in kod


# ------------------------------------------------------------ riskler
def test_temiz_oyuncuda_bayrak_yok():
    assert riskler(TEMIZ) == []


def test_kucuk_orneklem():
    kod = _kodlar(dict(TEMIZ, minutes=DAKIKA_GUVENSIZ - 1))
    assert KUCUK_ORNEKLEM in kod
    _, b = [x for x in riskler(dict(TEMIZ, minutes=500))
            if x[0] == KUCUK_ORNEKLEM][0]
    assert b["dakika"] == 500 and b["esik"] == DAKIKA_GUVENSIZ


def test_kucuk_orneklem_sinirda_yanmaz():
    assert KUCUK_ORNEKLEM not in _kodlar(dict(TEMIZ, minutes=DAKIKA_GUVENSIZ))


def test_eksik_metrik():
    assert EKSIK_METRIK in _kodlar(dict(TEMIZ, coverage=KAPSAM_ESIGI - 0.01))
    assert EKSIK_METRIK not in _kodlar(dict(TEMIZ, coverage=KAPSAM_ESIGI))


def test_bozuk_lig():
    assert LIG_BOZUK in _kodlar(dict(TEMIZ, lig_bozuk=True))


def test_sonuc_gorunmez_dusuk_gorunurlukte():
    """En onemli uyari: kademe 0 'basarisiz' demek DEGIL (§38.4)."""
    assert SONUC_GORUNMEZ in _kodlar(dict(TEMIZ, kapsam="sicrama_only"))
    assert SONUC_GORUNMEZ not in _kodlar(dict(TEMIZ, kapsam="tam"))


def test_deger_yok_bayragi():
    """deger_var modelin EN GUCLU degiskeni (+1,44). Yoksa skor asagi
    cekiliyor ve bu kalitesizlik degil GORUNMEZLIK olabilir (§39.4)."""
    assert DEGER_YOK in _kodlar(dict(TEMIZ, deger_var=0))
    assert DEGER_YOK not in _kodlar(dict(TEMIZ, deger_var=1))


def test_tek_sezon():
    assert TEK_SEZON in _kodlar(dict(TEMIZ, n_sezon=1))
    assert TEK_SEZON not in _kodlar(dict(TEMIZ, n_sezon=ASGARI_SEZON))


def test_yas_sinirda():
    assert YAS_SINIR in _kodlar(dict(TEMIZ, yas=YAS_SINIRDA))
    assert YAS_SINIR not in _kodlar(dict(TEMIZ, yas=YAS_SINIRDA - 0.1))


def test_eksik_alanlarda_cokmez():
    assert isinstance(riskler({}), list)
    assert isinstance(riskler({"minutes": np.nan, "yas": np.nan}), list)


def test_bos_liste_risk_yok_demek_degil():
    """Belgeleme testi: TEMIZ profilde bayrak yok ama bu 'risksiz' demek
    degil - arayuz bunu aciktan yaziyor."""
    assert riskler(TEMIZ) == []


# -------------------------------------------------------- kor noktalar
@pytest.mark.parametrize("pg", ["Goalkeeper", "Defender", "Midfielder",
                                "Attacker"])
def test_her_mevkinin_ozgu_kor_noktasi_var(pg):
    k = kor_noktalar(pg)
    assert set(MEVKIYE_KOR[pg]) <= set(k)
    assert set(GENEL_KOR) <= set(k)


def test_bilinmeyen_mevkide_genel_kalir():
    assert kor_noktalar("Unknown") == GENEL_KOR


# ------------------------------------------------------------- katki
def test_katki_tablosu_mutlak_degere_gore_siralar():
    d = katki_tablosu({"a": 2.0, "b": -9.0, "c": 5.0}, n=2)
    assert list(d.metrik) == ["b", "c"]


def test_katki_bos_sozlukte_bos_tablo():
    assert katki_tablosu({}).empty
    assert katki_tablosu(None).empty


# ------------------------------------------------------------ kademe
def test_kademe_kodu():
    assert kademe_kodu(3) == 3
    assert kademe_kodu(None) is None
    assert kademe_kodu(np.nan) is None
    assert kademe_kodu(4.0) == 4
