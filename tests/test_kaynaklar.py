"""Kaynak katmani: TM anlik goruntusu sabitleme ve tazelik kurallari (FAZ 9.1)."""
import datetime as dt

import pytest

from scout import kaynaklar as K

BUGUN = dt.date(2026, 10, 30)


def _anlik(tmp_path, *adlar):
    for a in adlar:
        (tmp_path / a).mkdir()
        (tmp_path / a / K.TM_DOSYA).write_bytes(b"")
    (tmp_path / "bos_klasor").mkdir()          # dosyasiz klasor sayilmaz
    return tmp_path


def test_sabitlenen_surum_secilir_en_yeni_degil(tmp_path):
    d = _anlik(tmp_path, "2026-07-11", "2026-09-05")
    ayar = {"transfermarkt": {"anlik_goruntu": "2026-07-11"}}
    assert K.tm_anlik_goruntuler(d) == ["2026-07-11", "2026-09-05"]
    assert K.tm_db_yolu(ayar, d).parent.name == "2026-07-11"


def test_en_yeni_acikca_istenirse(tmp_path):
    d = _anlik(tmp_path, "2026-07-11", "2026-09-05")
    assert K.tm_db_yolu({"transfermarkt": {"anlik_goruntu": "en_yeni"}}, d).parent.name == "2026-09-05"


def test_olmayan_surum_sessizce_degistirilmez(tmp_path):
    d = _anlik(tmp_path, "2026-07-11")
    with pytest.raises(FileNotFoundError):
        K.tm_db_yolu({"transfermarkt": {"anlik_goruntu": "2026-09-05"}}, d)


def test_gercek_ayar_dosyasi_sabit_bir_surum_gosteriyor():
    """'en_yeni' gecisi gorunmez yapar; uretim ayari tarih olmali."""
    a = K.ayarlar()["transfermarkt"]["anlik_goruntu"]
    dt.date.fromisoformat(str(a))


def _tm(son_mac, deger=None, kullanilan="2026-07-11", mevcut=("2026-07-11",)):
    return K.tm_tazelik(kullanilan, list(mevcut), {"mac": son_mac, "deger": deger},
                        BUGUN, bayat_gun=21, karar_tarihi="2027-03-01")


def test_tm_durmus_veri_seti_uyari():
    b = _tm(dt.date(2026, 7, 6))
    assert b[0].sonuc == "UYARI" and "116 gun" in b[0].detay and "2027-03-01" in b[0].detay


def test_tm_taze_gecer():
    assert _tm(dt.date(2026, 10, 25))[0].sonuc == "GECTI"


def test_tm_deger_geride_ve_yeni_surum_bekliyor():
    b = _tm(dt.date(2026, 7, 6), deger=dt.date(2026, 2, 27),
            mevcut=("2026-07-11", "2026-09-05"))
    kontroller = {x.kontrol for x in b}
    assert "TM piyasa degerleri maclardan geride" in kontroller
    assert "Daha yeni TM anlik goruntusu bekliyor" in kontroller


def test_api_sezon_sinamasi_bayat_ve_yeni_sezon():
    eski = {"tarih": "2026-08-30", "acik": []}
    assert K.api_tazelik(eski, BUGUN, 30, None, 100)[0].sonuc == "UYARI"
    yeni = {"tarih": "2026-10-30", "acik": [2025]}
    b = K.api_tazelik(yeni, BUGUN, 30, None, 100)
    assert b[0].sonuc == "GECTI"
    assert any(x.kontrol == "API'de YENI SEZON ACILDI" for x in b)


def test_api_hic_sinanmamis():
    assert K.api_tazelik(None, BUGUN, 30, None, 100)[0].sonuc == "UYARI"
