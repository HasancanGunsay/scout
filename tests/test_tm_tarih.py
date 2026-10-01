"""TM tarihsel veri testleri (FAZ 7.1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scout.features.tm_tarih import (API_DONEMI, BOLUM, GELISTIRME,
                                     ILERIYE_DONUK, MUHURLU_TEST, SAHADA_YOK,
                                     bolum, mevki, sahada_mi)

DB = Path(__file__).resolve().parents[1] / "data" / "scout.duckdb"


# ------------------------------------------------------------------ muhur
def test_muhur_degismedi():
    """7.2'nin temiz sinavi ONCEDEN konuldu; sessizce kaydirilamaz."""
    assert MUHURLU_TEST == (2018, 2019, 2020, 2021)
    assert GELISTIRME == (2013, 2014, 2015, 2016, 2017)


def test_bolumler_ayrik_ve_eksiksiz():
    gruplar = [GELISTIRME, MUHURLU_TEST, API_DONEMI, ILERIYE_DONUK, (2012,)]
    hepsi = [s for g in gruplar for s in g]
    assert len(hepsi) == len(set(hepsi))
    assert set(hepsi) == set(range(2012, 2026)) == set(BOLUM)
    assert bolum(2019) == "muhurlu_test" and bolum(1999) is None


# ------------------------------------------------------------------ mevki
def test_mevki_kadrodan():
    assert mevki("Centre-Back", "Attack") == ("Stoper", "Defender", "kadro")
    assert mevki("Left-Back", None) == ("Sol bek", "Defender", "kadro")
    assert mevki("Defensive Midfield", None)[:2] == ("On libero", "Midfielder")


def test_mevki_kadro_yoksa_guncele_duser_ve_isaretler():
    assert mevki(None, "Defender") == (None, "Defender", "guncel")
    assert mevki("bilinmeyen", "Midfield") == (None, "Midfielder", "guncel")
    assert mevki(None, None) == (None, None, "yok")


# --------------------------------------------------------------- sahada_mi
def test_sahada_araligi_sinirlari():
    assert sahada_mi(1, 0, SAHADA_YOK)          # ilk 11, 1. dakika golu
    assert sahada_mi(0, 0, SAHADA_YOK)          # 0. dakika -> 1 sayilir
    assert not sahada_mi(60, 60, SAHADA_YOK)    # 60'ta girdi: o dakikadaki gol once
    assert sahada_mi(60, 0, 60)                 # 60'ta cikti: o dakikadaki gol sayilir
    assert not sahada_mi(61, 0, 60)
    assert sahada_mi(95, 0, SAHADA_YOK)         # uzatma golu


# ------------------------------------------------------- tablo butunlugu
@pytest.fixture(scope="module")
def tablo():
    if not DB.exists():
        pytest.skip("veritabani yok")
    import duckdb
    con = duckdb.connect(str(DB), read_only=True)
    try:
        d = con.sql("SELECT * FROM tm_oyuncu_sezon").df()
    except duckdb.CatalogException:
        pytest.skip("tm_oyuncu_sezon yok - build_tm_tarih calistir")
    finally:
        con.close()
    return d


def test_anahtar_tekil(tablo):
    assert not tablo.duplicated(["player_id", "comp", "season"]).any()


def test_acik_pencerede_sonuc_uretilmez(tablo):
    """Sansur (§outcome): 2025 penceresi acik - sonuc NULL olmali, 0 degil."""
    a = tablo[tablo.season == 2025]
    assert len(a) and a.kademe.isna().all() and (~a.pencere_tam).all()
    k = tablo[tablo.season.isin(GELISTIRME + MUHURLU_TEST)]
    assert k.pencere_tam.all() and k.kademe.between(0, 4).all()


def test_oranlar_makul(tablo):
    t = tablo.dropna(subset=["dakika_payi"])
    assert (t.dakika_payi >= 0).all() and (t.dakika_payi <= 1.05).all()
    assert (tablo[["gf_on", "ga_on"]].fillna(0) >= 0).all().all()
    assert (tablo.ilk11 <= tablo.mac).all()
