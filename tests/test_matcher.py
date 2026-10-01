"""Kimlik eslestirme testleri.

NEDEN ONEMLI: ilk surum "blokta tek aday varsa kabul et" diyordu ve
YANLIS eslesmeler uretiyordu - 'Gabriel Silva' -> 'Matheus Teixeira'
(ayni gun dogmus farkli Brezilyalilar). Yanlis piyasa degeri, eksik
piyasa degerinden beterdir.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scout.resolve.matcher import build_links, name_score, normalize, variants


class TestNormalize:
    @pytest.mark.parametrize("raw,beklenen", [
        ("João Pedro", "joao pedro"),
        ("Vinícius Júnior", "vinicius junior"),
        ("  Tárik  ", "tarik"),
        ("B. Borasi", "b borasi"),
        ("Ó. Estupiñán", "o estupinan"),
    ])
    def test_aksan_ve_noktalama(self, raw, beklenen):
        assert normalize(raw) == beklenen

    def test_none_bos_string(self):
        assert normalize(None) == ""


class TestNameScore:
    def test_ayni_isim_tam_puan(self):
        assert name_score(variants("Lucas Ramon"), variants("Lucas Ramon")) == 100

    def test_kisaltma_yakalanir(self):
        s = name_score(variants("A. Franco", "A.", "Franco"),
                       variants("Alan Franco", "Alan", "Franco"))
        assert s >= 85

    def test_alakasiz_isim_dusuk_puan(self):
        s = name_score(variants("Gabriel Silva"), variants("Matheus Teixeira"))
        assert s < 70


def _api(rows):
    return pd.DataFrame(rows, columns=["player_id", "player_name", "firstname",
                                       "lastname", "birth_date", "nationality",
                                       "team_name"])


def _tm(rows):
    return pd.DataFrame(rows, columns=["tm_id", "name", "first_name", "last_name",
                                       "date_of_birth", "country_of_citizenship",
                                       "current_club_name"])


class TestBuildLinks:
    def test_tek_aday_isim_tutuyorsa_kabul(self):
        api = _api([[1, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "Mirassol"]])
        tm = _tm([[10, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "Mirassol"]])
        out = build_links(api, tm)
        assert out.confidence.iloc[0] == "A"
        assert out.tm_id.iloc[0] == 10

    def test_tek_aday_isim_TUTMUYORSA_reddedilir(self):
        """GERCEK HATA BUYDU: ayni gun dogmus baska biri kabul ediliyordu."""
        api = _api([[1, "Gabriel Silva", "Gabriel", "Silva", "1998-06-01", "Brazil", "Goias"]])
        tm = _tm([[10, "Matheus Teixeira", "Matheus", "Teixeira", "1998-06-01",
                   "Brazil", "Palmeiras"]])
        out = build_links(api, tm)
        assert out.confidence.iloc[0] == "D", "yanlis eslesme kabul edilmis!"

    def test_aday_yoksa_isaretlenir(self):
        api = _api([[1, "Kimse", "Kim", "Se", "1999-01-01", "Brazil", "X"]])
        tm = _tm([[10, "Baska", "Bas", "Ka", "1985-05-05", "Spain", "Y"]])
        out = build_links(api, tm)
        assert out.confidence.iloc[0] == "-"

    def test_coklu_adayda_isim_ayirt_eder(self):
        api = _api([[1, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "Mirassol"]])
        tm = _tm([
            [10, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "Mirassol"],
            [11, "Pedro Alves", "Pedro", "Alves", "1996-03-01", "Brazil", "Santos"],
        ])
        out = build_links(api, tm)
        assert out.confidence.iloc[0] in ("A", "B")
        assert out.tm_id.iloc[0] == 10

    def test_bir_tm_kaydina_tek_oyuncu(self):
        """Iki API oyuncusu ayni TM kaydina baglanamaz."""
        api = _api([
            [1, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "A"],
            [2, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "B"],
        ])
        tm = _tm([[10, "Lucas Ramon", "Lucas", "Ramon", "1996-03-01", "Brazil", "A"]])
        out = build_links(api, tm)
        kabul = out[out.confidence.isin(["A", "B"])]
        assert kabul.tm_id.dropna().duplicated().sum() == 0
