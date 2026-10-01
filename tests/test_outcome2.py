"""Ikinci sonuc (kendi verimizden ust lige gecis) testleri - FAZ 6.2b.

Bu testler 6.1'deki SANSUR dersini kilitler: sabit pencere, tarih temelli
(etiket temelli degil), gozlenemeyen orijinler SIFIR sayilmaz DISLANIR.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from scout.features.outcome2 import ASGARI_DAKIKA, SEVIYE, seviye, ust_gecis

VS = dt.date(2025, 6, 15)          # veri sonu (Avrupa 2024/25 bitisi)


def _o(pid, lig, sez, ulke):
    return pd.DataFrame([dict(player_id=pid, league_id=lig, season=sez,
                              country=ulke)])


def _h(pid, lig, sez, ulke, dk):
    return dict(player_id=pid, league_id=lig, season=sez, country=ulke,
                minutes=dk)


def test_seviye_tanimli_ve_kaba():
    assert seviye(39) == 1 and seviye(72) == 3 and seviye(242) == 4
    assert seviye(999999) is None
    assert set(SEVIYE.values()) == {1, 2, 3, 4}


def test_yukari_gecis_sayilir():
    """Ligue 2 (T3) 2022 -> Ligue 1 (T1) 2023/24, 900 dk."""
    o = _o(1, 62, 2022, "France")
    h = pd.DataFrame([_h(1, 61, 2023, "France", 900)])
    r = ust_gecis(o, h, VS)
    assert r.y2.iloc[0] == 1 and r.hedef_lig.iloc[0] == 61


def test_takvim_yili_ligi_tarihle_eslesir():
    """Brezilya B 2022 (biter 2022-12) -> Portekiz 2022/23: AYNI ETIKETLI
    sezon ama tarihce SONRA. Etiket temelli kural bunu kacirirdi."""
    o = _o(1, 72, 2022, "Brazil")
    h = pd.DataFrame([_h(1, 94, 2022, "Portugal", 900)])
    assert ust_gecis(o, h, VS).y2.iloc[0] == 1


def test_ayni_sezon_kis_transferi_sayilmaz():
    """Ayni sezonun baska liginde oynamak (bitis tarihi ayni) 'sonraki sezon'
    degildir."""
    o = _o(1, 62, 2022, "France")
    h = pd.DataFrame([_h(1, 61, 2022, "France", 900)])
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0


def test_asagi_gecis_sayilmaz():
    o = _o(1, 61, 2022, "France")                     # T1
    h = pd.DataFrame([_h(1, 62, 2023, "France", 900)])  # T3
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0


def test_ayni_seviye_sayilmaz():
    o = _o(1, 62, 2022, "France")                     # T3
    h = pd.DataFrame([_h(1, 136, 2023, "Italy", 900)])  # T3
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0


def test_yetersiz_dakika_sayilmaz():
    o = _o(1, 62, 2022, "France")
    h = pd.DataFrame([_h(1, 61, 2023, "France", ASGARI_DAKIKA - 1)])
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0


def test_pencere_uzunlugu_sabit_iki_sezon_sonrasi_sayilmaz():
    """Sansur dersi (§38.3): pencere herkese ayni uzunlukta olmali; 2022
    orijinine iki sans vermek, 2023'e bir sans vermek olcum artefakti."""
    o = _o(1, 62, 2022, "France")
    h = pd.DataFrame([_h(1, 61, 2024, "France", 900)])   # 2024/25: +24 ay
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0


def test_gozlenemeyen_orijin_sifir_degil_dislanir():
    """2024 orijini: sonraki sezon (2025/26) veride yok -> gozlenebilir=False."""
    o = _o(1, 62, 2024, "France")
    h = pd.DataFrame([_h(1, 62, 2024, "France", 900)])
    r = ust_gecis(o, h, VS)
    assert bool(r.gozlenebilir.iloc[0]) is False


def test_gozlenebilir_orijin_isaretli():
    o = _o(1, 62, 2023, "France")
    h = pd.DataFrame([_h(1, 62, 2024, "France", 900)])
    assert bool(ust_gecis(o, h, VS).gozlenebilir.iloc[0]) is True


def test_t1_orijin_yukari_cikamaz():
    o = _o(1, 39, 2022, "England")
    h = pd.DataFrame([_h(1, 140, 2023, "Spain", 900)])   # T1 -> T1
    assert ust_gecis(o, h, VS).y2.iloc[0] == 0
