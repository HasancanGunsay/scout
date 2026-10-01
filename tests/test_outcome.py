"""Gercek sonuc tablosu testleri (FAZ 1).

Bu dosya iki TUZAGI kilitliyor. Ikisi de sessizdi - sonuc tablosu her iki
durumda da makul gorunuyordu:

  1) TM'nin sezon etiketi takvim yili liglerinde BIR YIL kayik
     (BRA1 season=2024 -> maclar 2025-03..2025-12)
  2) competitions 31 birinci lig diyor ama appearances 14'unde veri var
     (BRA1/ARG1/SE1/NO1 -> mac var, oyuncu kaydi YOK)

Ucuncusu sansurleme: 12 aylik pencere her sezonda tam, 24 aylik degil.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from scout.features.outcome import (ILK_BES, KAPSAM_SICRAMA, KAPSAM_TAM,
                                    PENCERE_AY, TM_KARSILIGI, gozlem_ay,
                                    izlenen_ligler, kademe, kapsam,
                                    pencere_tam, sezon_bitis)


# ------------------------------------------------------- sezon takvimi
def test_takvim_yili_ligi_aralikta_biter():
    """Brezilya 2024 sezonu takvim 2024 -> aralik 2024'te biter."""
    assert sezon_bitis("Brazil", 2024) == dt.date(2024, 12, 15)
    assert sezon_bitis("Sweden", 2022) == dt.date(2022, 12, 15)


def test_sonbahar_ligi_ertesi_yil_biter():
    """Hollanda 2024 sezonu 2024/25 -> haziran 2025'te biter."""
    assert sezon_bitis("Netherlands", 2024) == dt.date(2025, 6, 15)
    assert sezon_bitis("Spain", 2022) == dt.date(2023, 6, 15)


def test_iki_takvim_karismaz():
    """Ayni sezon numarasi iki ulkede FARKLI tarihe denk gelmeli.

    Bu testin korudugu sey: TM'nin `season` alanini kullanmaya geri
    donulurse Brezilya/Arjantin/Iskandinavya bir yil kayar ve kimse
    fark etmez.
    """
    assert sezon_bitis("Brazil", 2024) != sezon_bitis("Spain", 2024)
    assert sezon_bitis("Brazil", 2024) < sezon_bitis("Spain", 2024)


# ------------------------------------------------------------- kademe
@pytest.mark.parametrize("dk,ilk_bes,bek", [
    (0, False, 0), (None, False, 0),
    (1, False, 1), (449, False, 1),
    (450, False, 2), (899, False, 2),
    (900, False, 3), (3000, False, 3),
    (900, True, 4), (899, True, 2),      # ilk-5 ama yeterli dakika yok
])
def test_kademe_esikleri(dk, ilk_bes, bek):
    assert kademe(dk if dk is not None else float("nan"), ilk_bes) == bek


def test_ilk_bes_listesi():
    assert ILK_BES == {"ES1", "GB1", "IT1", "L1", "FR1"}


# --------------------------------------------------------- sansurleme
def test_gozlem_ay_hesabi():
    a = gozlem_ay(dt.date(2025, 6, 15), dt.date(2026, 6, 28))
    assert 12 < a < 13


def test_2024_sezonunda_12_ay_tam_24_ay_degil():
    """Sansurlemenin ta kendisi.

    max(y1, y2) kullanilsaydi 2022 satirlarina IKI sans, 2024 satirlarina
    BIR sans verilirdi ve model 'eski sezonlar daha basarili' diye
    ogrenirdi - tamamen olcum artefakti.
    """
    veri_sonu = dt.date(2026, 6, 28)
    b2024 = sezon_bitis("Netherlands", 2024)
    b2022 = sezon_bitis("Netherlands", 2022)
    assert pencere_tam(b2024, veri_sonu, 12)
    assert not pencere_tam(b2024, veri_sonu, 24)
    assert pencere_tam(b2022, veri_sonu, 24)


def test_birincil_pencere_12_ay():
    assert PENCERE_AY == 12


# ------------------------------------------------ izlenen lig turetimi
def _sahte(comp_ids_with_counts):
    app = pd.DataFrame({"competition_id":
                        sum(([k] * v for k, v in comp_ids_with_counts.items()), [])})
    comp = pd.DataFrame({
        "competition_id": list(comp_ids_with_counts),
        "type": ["domestic_league"] * len(comp_ids_with_counts)})
    return app, comp


def test_izlenen_lig_veriden_turetilir():
    app, comp = _sahte({"ES1": 6000, "BRA1": 0, "XX1": 10})
    izlenen = izlenen_ligler(app, comp, asgari_satir=5000)
    assert izlenen == {"ES1"}


def test_mac_var_oyuncu_kaydi_yok_ligi_izlenmez():
    """BRA1/ARG1/SE1/NO1 vakasi: games'te mac var, appearances'ta yok.

    Bunlari izleniyor saymak, Brezilya Serie A'da kalmaya devam eden
    oyuncuyu 'iz yok' yapardi ve model 'Brezilya Serie A basarisiz'
    diye ogrenirdi. Olculdu: yanlislikla izleniyor sayilinca ortalama
    kademeleri 0,22-0,34 cikiyordu - Ligue 2'nin (0,75) altinda.
    """
    for lig in ("BRA1", "ARG1", "SE1", "NO1"):
        app, comp = _sahte({lig: 0, "ES1": 6000})
        assert lig not in izlenen_ligler(app, comp)


def test_izlenmeyen_ligler_haritada_none():
    """Guney Amerika / Iskandinavya birinci ligleri None olmali."""
    for lid in (71, 128, 113, 103):        # BRA SerieA, ARG, SWE, NOR
        assert TM_KARSILIGI[lid] is None


def test_izlenen_ligler_haritada_dolu():
    for lid in (39, 78, 135, 140, 61, 88, 144, 119, 94):
        assert TM_KARSILIGI[lid] is not None


# ------------------------------------------------------------- kapsam
def test_kapsam_ayrimi():
    assert kapsam(88) == KAPSAM_TAM            # Eredivisie izleniyor
    assert kapsam(72) == KAPSAM_SICRAMA        # Brezilya Serie B
    assert kapsam(71) == KAPSAM_SICRAMA        # Brezilya Serie A - kayit yok


def test_bilinmeyen_lig_sicrama_sayilir():
    """Tanimadigimiz lig icin temkinli taraf: kalmak gorunmez varsay."""
    assert kapsam(999999) == KAPSAM_SICRAMA
