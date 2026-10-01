"""Hesap defteri testleri (FAZ 5).

EN KRITIK TEST: retrospektif / prospektif AYRIMI.

2022-2024 sezonlarinin sonucu zaten biliniyor. Bugun bu sezonlar icin acilan
bir kayit "ileriye donuk tahmin" DEGILDIR - model bu veriyle egitildi ya da
uzerinde sinandi. Ikisini karistirmak, geriye donuk testi "sistem su kadar
isabetli" diye sunmak olurdu. Bu proje o hatayi bir kez yapti (§31).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from scout.model.defter import (KAYNAK_OTOMATIK, SUTUNLAR, bolumle,
                                iddia_kaydi, kalibrasyon, kullanici_ortusmesi,
                                nerede_yaniliyor, puanla)


def _iddia(pid=1, lid=10, sez=2022, p=0.7, tarih="2026-08-30"):
    return {"kayit_tarihi": tarih, "player_id": pid, "league_id": lid,
            "season": sez, "player_name": f"o{pid}", "league_name": "L",
            "kapsam": "tam", "model_olasilik": p, "emsal_oran": 0.3,
            "lig_taban": 0.2, "kaynak": KAYNAK_OTOMATIK, "not": ""}


def _sonuc(pid=1, lid=10, sez=2022, bitis="2023-06-15", kademe=3):
    return {"player_id": pid, "league_id": lid, "season": sez,
            "sezon_bitis": bitis, "kademe": kademe, "gozlem_ay": 30.0}


# ------------------------------------------------------------ kayit
def test_iddia_kaydi_tum_sutunlari_uretir():
    r = {"player_id": 5, "league_id": 2, "season": 2024, "player_name": "X",
         "league_name": "L", "kapsam": "tam", "model_olasilik": 0.8,
         "oran": 0.4, "lig_taban": 0.2}
    k = iddia_kaydi(r, tarih=dt.date(2026, 8, 30))
    assert set(k) == set(SUTUNLAR)
    assert k["kayit_tarihi"] == "2026-08-30"
    assert k["model_olasilik"] == 0.8 and k["emsal_oran"] == 0.4


def test_iddia_kaydi_eksik_emsalde_none():
    r = {"player_id": 5, "league_id": 2, "season": 2024, "model_olasilik": 0.8,
         "oran": np.nan, "lig_taban": np.nan}
    k = iddia_kaydi(r)
    assert k["emsal_oran"] is None and k["lig_taban"] is None


# ------------------------------------------- retrospektif / prospektif
def test_pencere_kapaliyken_retrospektif():
    """Sezon 2023-06'da bitti, kayit 2026-08'de acildi -> sonuc BILINIYORDU."""
    d = pd.DataFrame([_iddia(tarih="2026-08-30")])
    s = pd.DataFrame([_sonuc(bitis="2023-06-15")])
    b = bolumle(d, s)
    assert len(b["retrospektif"]) == 1
    assert len(b["prospektif"]) == 0


def test_pencere_acikken_prospektif():
    """Sezon 2026-06'da bitti, kayit 2026-08'de -> sonuc HENUZ YOK."""
    d = pd.DataFrame([_iddia(tarih="2026-08-30")])
    s = pd.DataFrame([_sonuc(bitis="2026-06-15", kademe=None)])
    b = bolumle(d, s)
    assert len(b["prospektif"]) == 1
    assert len(b["retrospektif"]) == 0


def test_tam_bir_yil_sinirinda_retrospektif():
    d = pd.DataFrame([_iddia(tarih="2026-08-30")])
    s = pd.DataFrame([_sonuc(bitis="2025-08-30")])      # tam 365 gun
    assert len(bolumle(d, s)["retrospektif"]) == 1


def test_bir_gun_eksikte_prospektif():
    d = pd.DataFrame([_iddia(tarih="2026-08-30")])
    s = pd.DataFrame([_sonuc(bitis="2025-08-31")])      # 364 gun
    assert len(bolumle(d, s)["prospektif"]) == 1


def test_sonucu_olmayan_iddia_prospektif_sayilir():
    """Sonuc satiri yoksa temkinli taraf: henuz bilinmiyor varsay."""
    d = pd.DataFrame([_iddia(pid=999)])
    s = pd.DataFrame([_sonuc(pid=1)])
    assert len(bolumle(d, s)["prospektif"]) == 1


def test_bos_defter_cokmez():
    b = bolumle(pd.DataFrame(columns=SUTUNLAR), pd.DataFrame())
    assert b["retrospektif"].empty and b["prospektif"].empty


# ----------------------------------------------------------- puanlama
def test_puanla_kademe_3_ve_ustu_basarili():
    d = pd.DataFrame([{"kademe": k, "model_olasilik": 0.5} for k in
                      [0, 1, 2, 3, 4, None]])
    p = puanla(d)
    assert list(p.gerceklesti[:5]) == [0.0, 0.0, 0.0, 1.0, 1.0]
    assert pd.isna(p.gerceklesti.iloc[5])


# -------------------------------------------------------- kalibrasyon
def test_kalibrasyon_az_ornekte_bos():
    d = pd.DataFrame({"model_olasilik": [0.5] * 10, "gerceklesti": [1.0] * 10})
    assert kalibrasyon(d).empty


def test_kalibrasyon_kova_uretir():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 500)
    d = pd.DataFrame({"model_olasilik": p,
                      "gerceklesti": rng.binomial(1, p).astype(float)})
    k = kalibrasyon(d)
    assert len(k) == 5
    # iyi kalibre veri: dedi ~ oldu
    assert (k.dedi - k.oldu).abs().max() < 0.15


# ------------------------------------------------------ nerede yanlis
def test_nerede_yaniliyor_sapma_isareti():
    """sapma > 0 = model FAZLA umutlu."""
    d = pd.DataFrame({"kapsam": ["a"] * 40 + ["b"] * 40,
                      "model_olasilik": [0.9] * 40 + [0.2] * 40,
                      "gerceklesti": [0.0] * 40 + [0.2] * 40})
    n = nerede_yaniliyor(d, "kapsam").set_index("kapsam")
    assert n.loc["a", "sapma"] > 0.5      # cok umutlu
    assert abs(n.loc["b", "sapma"]) < 0.05


def test_nerede_yaniliyor_kucuk_grubu_gostermez():
    """Kucuk kohortta sayi uretmeme kuralinin (§21) aynisi."""
    d = pd.DataFrame({"kapsam": ["a"] * 5, "model_olasilik": [0.5] * 5,
                      "gerceklesti": [1.0] * 5})
    assert nerede_yaniliyor(d, "kapsam", asgari=25).empty


# ------------------------------------------------ kullanici ortusmesi
def test_kullanici_ortusmesi_eslesme_bulur():
    d = pd.DataFrame([
        {"player_id": 1, "league_id": 10, "season": 2022,
         "model_olasilik": 0.9, "gerceklesti": 1.0},
        {"player_id": 2, "league_id": 10, "season": 2022,
         "model_olasilik": 0.3, "gerceklesti": 0.0}])
    o = kullanici_ortusmesi(
        [{"player_id": 1, "league_id": 10, "season": 2022}], d)
    assert o["n"] == 1
    assert o["ort_model"] == pytest.approx(0.9)
    assert o["ort_model_geneli"] == pytest.approx(0.6)


def test_kullanici_ortusmesi_bos_shortlist():
    assert kullanici_ortusmesi([], pd.DataFrame({"a": [1]}))["n"] == 0
