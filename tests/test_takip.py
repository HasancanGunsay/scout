"""Takip listesi testleri (FAZ 8.2, 1 Eki 2026).

Hepsi GECICI dizinde (SCOUT_TAKIP_DIZIN): kullanicinin gercek listesine ve
gunlugune asla dokunulmaz.

Sinanan iddialar:
  - ayni kisi iki kez eklenmez; ilk iddia (secim anindaki sistem) degismez
  - gunluk APPEND-ONLY: silme dahil hicbir islem eski satiri degistirmez
  - bozuk dosya sessizce bos liste sayilmaz (sayilsa ilk kayit listeyi silerdi)
  - kisi anahtari iki modulde ayni bicim (havuz <-> takip)
  - Havuz kartindan takibe alma: API satiri goz testi SAYILMAZ (sonuc
    belli), TM 2025/26 satiri SAYILIR
  - ayni kisi API ve TM havuzunda tek kayit, havuz gecmisi ikisini gosterir
  - Takip sayfasi: not ve durum kaydi; Hesap defteri iki kutuyu ayirir
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import _havuz as HV  # noqa: E402
from scout import takip as TK  # noqa: E402

DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"
veri_var = pytest.mark.skipif(not (DB.exists() or SNAP.exists()),
                              reason="veritabani yok")


@pytest.fixture
def dizin(tmp_path, monkeypatch):
    monkeypatch.setenv("SCOUT_TAKIP_DIZIN", str(tmp_path))
    return tmp_path


def _ekle(kisi="tm:1", ad="A", gorunur=False, **kw):
    return TK.ekle(kisi, ad, kaynak="tm", anahtar="1-NL1-2025",
                   sonuc_gorunur=gorunur, model_olasilik=0.6,
                   havuz_puani=91.0, deger=1e6, zaman="2026-10-01T10:00:00",
                   **kw)


# ------------------------------------------------------------------ modül
def test_ortam_degiskeni_iki_dosyayi_da_yonlendirir(dizin):
    d, g = TK.yollar()
    assert d.parent == dizin and g.parent == dizin


def test_ayni_kisi_iki_kez_eklenmez_ilk_iddia_degismez(dizin):
    _ekle()
    TK.ekle("tm:1", "A", kaynak="api", anahtar="x", sonuc_gorunur=True,
            model_olasilik=0.1)
    k = TK.yukle()["oyuncular"]["tm:1"]
    assert k["ilk"]["model_olasilik"] == 0.6 and k["kaynak"] == "tm"
    assert len(TK.gunluk_oku()) == 1


def test_gunluk_append_only_silme_dahil(dizin):
    _ekle()
    gunluk = TK.yollar()[1]
    once = gunluk.read_bytes()
    TK.durum_degistir("tm:1", "oncelikli")
    TK.durum_degistir("tm:1", "oncelikli")          # degisiklik yok -> satir yok
    TK.not_ekle("tm:1", "  Ajax maçı: çok iyi  ")
    TK.rapor_ekle("tm:1", {"karar": "İlgilen", "teknik": 4})
    TK.sil("tm:1")
    sonra = gunluk.read_bytes()
    assert sonra.startswith(once), "eski satirlar degisti"
    g = TK.gunluk_oku()
    assert g.olay.tolist() == ["ekle", "durum", "not", "rapor", "sil"]
    assert g.metin.iloc[2] == "Ajax maçı: çok iyi"
    assert not TK.takipte(TK.yukle(), "tm:1")
    # silinen kisinin secim anindaki iddiasi gunlukte duruyor
    assert g.model_olasilik.iloc[-1] == pytest.approx(0.6)


def test_gecersiz_islemler_yuksek_sesle_durur(dizin):
    _ekle()
    with pytest.raises(ValueError):
        TK.durum_degistir("tm:1", "belki")
    with pytest.raises(ValueError):
        TK.not_ekle("tm:1", "   ")
    with pytest.raises(KeyError):
        TK.not_ekle("tm:999", "x")


def test_bozuk_dosya_bos_liste_sayilmaz(dizin):
    TK.yollar()[0].write_text("{bozuk", encoding="utf-8")
    with pytest.raises(RuntimeError):
        TK.yukle()
    with pytest.raises(RuntimeError):
        _ekle()                                      # listeyi ezmemeli
    assert TK.yollar()[0].read_text(encoding="utf-8") == "{bozuk"


def test_atomik_yazim_artik_birakmaz(dizin):
    _ekle()
    TK.not_ekle("tm:1", "x")
    assert sorted(p.name for p in dizin.iterdir()) == ["takip.json",
                                                       "takip_gunlugu.csv"]
    json.loads(TK.yollar()[0].read_text(encoding="utf-8"))


def test_kisi_anahtari_havuzla_ayni_bicim():
    assert TK.kisi_anahtari(123, 9) == HV.kisi(123, 9) == "tm:123"
    assert TK.kisi_anahtari(None, 9) == HV.kisi(None, 9) == "api:9"
    assert TK.kisi_anahtari(float("nan"), 9) == HV.kisi(float("nan"), 9)


def test_api_secimleri_yalniz_api_satirindan(dizin):
    _ekle()
    TK.ekle("tm:2", "B", kaynak="api", anahtar="5-88-2024",
            sonuc_gorunur=True, api=(5, 88, 2024))
    assert TK.api_secimleri(TK.yukle()) == [
        {"player_id": 5, "league_id": 88, "season": 2024, "player_name": "B"}]


# ------------------------------------------------------------ sayfalar
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

HAVUZ = ROOT / "app" / "views" / "Havuz.py"
TAKIP = ROOT / "app" / "views" / "Takip.py"
DEFTER = ROOT / "app" / "views" / "Hesap_Defteri.py"


def _calis(sayfa, **qp) -> AppTest:
    at = AppTest.from_file(str(sayfa), default_timeout=180)
    for k, v in qp.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _sorgu(q):
    import duckdb
    con = duckdb.connect(str(DB if DB.exists() else SNAP), read_only=True)
    try:
        return con.sql(q).fetchone()
    finally:
        con.close()


def _iki_havuzdaki_kisi():
    """Hem API 2024 hem TM 2025/26 havuzunda olan biri."""
    return _sorgu("""
        SELECT r.player_id, r.league_id, r.season, d.player_id AS tm_id,
               d.comp, d.season AS tm_sezon, r.player_name
        FROM player_ranking r
        JOIN player_links l USING (player_id)
        JOIN tm_iddia_defteri d ON d.player_id = l.tm_id
        WHERE r.season = 2024 ORDER BY d.model_olasilik DESC LIMIT 1""")


def _tikla(at, etiket):
    [b for b in at.button if b.label == etiket][0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]


@veri_var
def test_takip_sayfasi_bosken_yol_gosterir(dizin):
    at = _calis(TAKIP)
    assert any(b.label == "Havuza git" for b in at.button)


@veri_var
def test_havuz_kartindan_takibe_alma_ve_goz_testi_ayrimi(dizin):
    pid, lid, sez, tm_id, comp, tsez, ad = _iki_havuzdaki_kisi()
    # API satiri: sonuc belli -> goz testi sayilmaz
    at = _calis(HAVUZ, oyuncu=f"{pid}-{lid}-{sez}")
    _tikla(at, "Takibe al")
    k = TK.yukle()["oyuncular"][f"tm:{tm_id}"]
    assert k["ilk"]["sonuc_gorunur"] is True and k["api"] == [pid, lid, sez]
    assert any("★ Takipte" in m.value for m in at.markdown)
    # ayni kisi TM havuzunda: ikinci kayit ACILMAZ
    at = _calis(HAVUZ, oyuncu=f"{tm_id}-{comp}-{tsez}")
    assert not any(b.label == "Takibe al" for b in at.button)
    assert len(TK.yukle()["oyuncular"]) == 1


@veri_var
def test_tm_satiri_goz_testi_sayilir_ve_yildiz_sutunu(dizin):
    tm_id, comp, sez = _sorgu("""SELECT player_id, comp, season
        FROM tm_iddia_defteri ORDER BY model_olasilik DESC LIMIT 1""")
    at = _calis(HAVUZ, oyuncu=f"{tm_id}-{comp}-{sez}")
    _tikla(at, "Takibe al")
    k = TK.yukle()["oyuncular"][f"tm:{tm_id}"]
    assert k["ilk"]["sonuc_gorunur"] is False, "2027-06-15 oncesi"
    t = at.dataframe[0].value
    assert (t["Takip"] == "★").sum() == 1


@veri_var
def test_takip_sayfasi_not_durum_ve_havuz_gecmisi(dizin):
    pid, lid, sez, tm_id, comp, tsez, ad = _iki_havuzdaki_kisi()
    at = _calis(HAVUZ, oyuncu=f"{pid}-{lid}-{sez}")
    _tikla(at, "Takibe al")
    kisi = f"tm:{tm_id}"

    at = _calis(TAKIP, kisi=kisi)
    assert len(at.dataframe[0].value) == 1
    gecmis = at.dataframe[1].value
    assert len(gecmis) >= 2, "API 2024 + TM 2025/26 birlikte gorunmeli"
    [x for x in at.text_input if x.label == "Not ekle"][0] \
        .set_value("Ajax maçı: baskı altında soğukkanlı").run()
    _tikla(at, "Kaydet")
    k = TK.yukle()["oyuncular"][kisi]
    assert [n["metin"] for n in k["notlar"]] == ["Ajax maçı: baskı altında soğukkanlı"]
    [b for b in at.get("button_group") if b.label == "Durum"][0] \
        .set_value("oncelikli").run()
    assert TK.yukle()["oyuncular"][kisi]["durum"] == "oncelikli"
    assert TK.gunluk_oku().olay.tolist() == ["ekle", "not", "durum"]


@veri_var
def test_hesap_defteri_iki_kutuyu_ayirir(dizin):
    pid, lid, sez, tm_id, comp, tsez, ad = _iki_havuzdaki_kisi()
    TK.ekle(f"tm:{tm_id}", ad, kaynak="api", anahtar=f"{pid}-{lid}-{sez}",
            sonuc_gorunur=True, model_olasilik=0.5, api=(pid, lid, sez))
    TK.ekle("tm:1", "Gelecek", kaynak="tm", anahtar="1-NL1-2025",
            sonuc_gorunur=False, model_olasilik=0.4)
    at = _calis(DEFTER)
    secim = [m for m in at.metric if m.label == "Seçimin"]
    assert secim and secim[0].value == "1"
    assert any("göz testi değil" in m.value for m in at.markdown)
    assert any("gözünü değil" in c.value for c in at.caption)
