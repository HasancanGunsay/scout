"""Havuz ekrani testleri (FAZ 8.1, 1 Eki 2026).

Sinanan iddialar:
  - havuz puani GRUP ICI yuzdelik: her grubun tepesi ~100, gruplar bagimsiz
  - "Ilk %X" tam olarak grubun X'ini alir
  - degeri bilinmeyen oyuncu fiyat tavanina takilmaz (0 EUR degil, §56.4)
  - karma listede dusuk gorunurluk payi KORUNUR (olasilikla siralamada
    izlenen ligler %86-91'e cikiyordu, §50)
  - sayfa iki kaynakta ve her istatistik gorunumunde acilir, ham kolon adi
    arayuze sizmaz
  - kart (?oyuncu=) acilir; gosterilen olasilik player_tahmin ile ayni
  - (Oyuncu sayfasi parametre testi: test_oyuncu_sayfasi.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
HAVUZ = ROOT / "app" / "views" / "Havuz.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"
sys.path.insert(0, str(ROOT / "app"))

import _havuz as HV  # noqa: E402
import _metrikler as MK  # noqa: E402

veri_var = pytest.mark.skipif(not (DB.exists() or SNAP.exists()),
                              reason="veritabani yok")


def _ornek(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "season": 2024, "pos_group": "Attacker",
        "kapsam": ["tam"] * (n // 2) + ["sicrama_only"] * (n - n // 2),
        "model_olasilik": rng.uniform(size=n),
    })


# ------------------------------------------------------------------ birim
def test_havuz_puani_grup_ici_ve_bagimsiz():
    d = _ornek()
    # izlenen ligleri yapay olarak cok yuksek olasiliga it: grup ici
    # yuzdelik bundan ETKILENMEMELI
    d.loc[d.kapsam == "tam", "model_olasilik"] += 10
    d["havuz_puani"] = HV.havuz_puani(d, HV.GRUP[HV.KAYNAK_API])
    for _, g in d.groupby("kapsam"):
        assert g.havuz_puani.max() == pytest.approx(100.0)
        sira = g.sort_values("model_olasilik").havuz_puani
        assert sira.is_monotonic_increasing
    assert (d[d.kapsam == "sicrama_only"].havuz_puani.max()
            == d[d.kapsam == "tam"].havuz_puani.max())


def test_ilk_yuzde_x_tam_olarak_x_alir():
    d = pd.DataFrame({"season": 2024, "kapsam": "tam", "pos_group": "Defender",
                      "model_olasilik": np.linspace(0, 1, 100)})
    p = HV.havuz_puani(d, HV.GRUP[HV.KAYNAK_API])
    assert HV.dilim_icinde(p, 10).sum() == 10
    assert HV.dilim_icinde(p, 25).sum() == 25
    assert HV.dilim_icinde(p, 100).sum() == 100


def _filtre_ornek() -> pd.DataFrame:
    return pd.DataFrame({
        "oyuncu": ["Rúben Dias", "Kenan Yıldız", "İsmail Yüksek", "Bilinmez"],
        "havuz_puani": [95.0, 90.0, 80.0, 99.0],
        "pos_group": ["Defender", "Attacker", "Midfielder", "Attacker"],
        "lig": ["a", "b", "b", "c"], "kapsam": "tam",
        "yas": [21.0, 20.0, 22.5, 19.0], "dk": [2000, 1500, 900, 1200],
        "deger": [8e6, 3e6, 1e6, np.nan], "deger_var": [1, 1, 1, 0],
    })


def test_degeri_bilinmeyen_fiyat_tavanina_takilmaz():
    d = _filtre_ornek()
    s = HV.filtrele(d, fiyat_tavani=5e6)
    assert "Bilinmez" in s.oyuncu.tolist(), "deger yok != 0 EUR, elenmemeli"
    assert "Rúben Dias" not in s.oyuncu.tolist()
    s = HV.filtrele(d, fiyat_tavani=5e6, degersiz_dahil=False)
    assert "Bilinmez" not in s.oyuncu.tolist()


def test_isim_aramasi_aksan_ve_turkce_harf_duyarsiz():
    d = _filtre_ornek()
    assert HV.filtrele(d, ara="ruben").oyuncu.tolist() == ["Rúben Dias"]
    assert HV.filtrele(d, ara="yildiz").oyuncu.tolist() == ["Kenan Yıldız"]
    assert HV.filtrele(d, ara="ismail").oyuncu.tolist() == ["İsmail Yüksek"]


def test_filtre_puani_degistirmez_bos_liste_hepsi():
    d = _filtre_ornek()
    s = HV.filtrele(d, mevkiler=[], ligler=[], yas_max=21.5)
    assert s.havuz_puani.tolist() == [95.0, 90.0, 99.0]
    assert len(HV.filtrele(d)) == len(d)


def test_sofascore_baglantisi_ad_kulup_kodlu():
    """8.3: Sofascore'un arama adresi yok; DuckDuckGo '!ducky' + site:."""
    from urllib.parse import parse_qs, urlparse
    u = HV.sofascore_url("Kenan Yıldız", "Juventus FC")
    q = parse_qs(urlparse(u).query)["q"][0]
    assert u.startswith("https://duckduckgo.com/?q=")
    assert q == "!ducky site:sofascore.com Kenan Yıldız Juventus FC"
    assert parse_qs(urlparse(HV.sofascore_url("A B")).query)["q"][0] \
        == "!ducky site:sofascore.com A B"


def test_tm_baglantisi_profil_yoksa_arama():
    prof = "https://www.transfermarkt.co.uk/x/profil/spieler/1"
    assert HV.tm_url(prof, "X") == prof
    for yok in (None, float("nan"), ""):
        assert "schnellsuche" in HV.tm_url(yok, "T. Abed")


def test_arama_adi_kisaltma_degil_tam_ad():
    """'T. Abed' gibi kisa ad aramayi bozar: TM adi > API ad+soyad > kisa ad."""
    r = pd.DataFrame({
        "player_id": [1, 2, 3], "league_id": 9, "season": 2024,
        "player_name": ["P. Esposito", "T. Abed", "Zeca"],
        "tm_ad": ["Pio Esposito", None, None],
        "firstname": ["Francesco Pio", "Tarik", None],
        "lastname": ["Esposito", "Abed", None],
        "team_name": ["Spezia", "Jong PSV", "X"],
        "simdi_kulup": ["Inter Milan", None, None],
        "country": "Italy", "league_name": "Serie B", "kapsam": "tam",
        "pos_group": "Attacker", "age_season_end": 20.0, "minutes": 900,
        "model_olasilik": [0.5, 0.4, 0.3]})
    d = HV.api_hazirla(r)
    assert d.tam_ad.tolist() == ["Pio Esposito", "Tarik Abed", "Zeca"]
    assert d.arama_kulup.tolist() == ["Inter Milan", "Jong PSV", "X"]


def test_tm_katalogu_tutarli():
    adlar = [m.ad for m in HV.TM_TUMU.values()]
    assert len(adlar) == len(set(adlar))
    assert all(k in HV.TM_TUMU for k in HV.TM_PROFIL)
    assert set(HV.MEVKILER) <= set(MK.MEVKI_ADI)


# ------------------------------------------------------------ veriyle
def _con():
    import duckdb
    return duckdb.connect(str(DB if DB.exists() else SNAP), read_only=True)


@veri_var
def test_karma_listede_dusuk_gorunurluk_payi_korunur():
    con = _con()
    try:
        r = con.sql("""SELECT r.*, f.team_name FROM player_ranking r
                       LEFT JOIN player_features f
                       USING (player_id, league_id, season)""").df()
    finally:
        con.close()
    d = HV.api_hazirla(r)
    for sezon, g in d.groupby("season"):
        taban = (g.kapsam == "sicrama_only").mean()
        h = HV.filtrele(g, dilim=25)
        pay = (h.kapsam == "sicrama_only").mean()
        assert abs(pay - taban) < 0.03, (sezon, pay, taban)
        # karsilastirma: olasiliga gore ayni sayida oyuncu secilseydi
        ust = g.nlargest(len(h), "model_olasilik")
        assert (ust.kapsam == "sicrama_only").mean() < pay


pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def _at(**qp) -> AppTest:
    at = AppTest.from_file(str(HAVUZ), default_timeout=180)
    for k, v in qp.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _ham_sizinti(kol: list[str]) -> list[str]:
    ham = set(MK.TUMU) | set(HV.TM_TUMU) | {"havuz_puani", "model_olasilik"}
    return [k for k in kol if k in ham]


def _kaynak(at: AppTest, kaynak: str) -> None:
    [b for b in at.get("button_group") if b.label == "Kaynak"][0] \
        .set_value(kaynak).run()
    assert not at.exception, [str(e.value) for e in at.exception]


@veri_var
def test_sayfa_iki_kaynakta_ve_her_gorunumde_acilir():
    at = _at()
    for kaynak, aileler in [(HV.KAYNAK_API, MK.AILELER),
                            (HV.KAYNAK_TM, HV.TM_AILELER)]:
        _kaynak(at, kaynak)
        for gor in ["Özet"] + list(aileler):
            [s for s in at.selectbox if s.label == "İstatistik görünümü"][0] \
                .set_value(gor).run()
            assert not at.exception, (kaynak, gor,
                                      [str(e.value) for e in at.exception])
            t = at.dataframe[0].value
            assert not _ham_sizinti(list(t.columns)), (kaynak, gor)
            assert t["Havuz puanı"].is_monotonic_decreasing
            n = [m for m in at.metric if m.label == "Havuzda"][0].value
            assert int(n.replace(".", "")) == len(t)
            if gor == "Pas ve oyun kurma":
                assert any("yüzde değil" in i.value for i in at.info)


def _ust_oyuncu(sorgu: str):
    con = _con()
    try:
        return con.sql(sorgu).fetchone()
    finally:
        con.close()


@veri_var
def test_kart_acilir_ve_olasilik_tek_kaynakla_ayni():
    pid, lid, sez, ad, p = _ust_oyuncu("""
        SELECT r.player_id, r.league_id, r.season, r.player_name,
               t.model_olasilik
        FROM player_ranking r JOIN player_tahmin t
             USING (player_id, league_id, season)
        WHERE r.season = (SELECT max(season) FROM player_ranking)
        ORDER BY t.model_olasilik DESC LIMIT 1""")
    at = _at(oyuncu=f"{pid}-{lid}-{sez}")
    assert any(f'class="ad">{ad}<' in m.value for m in at.markdown)
    model = [m for m in at.metric if m.label == "Model"][0].value
    assert model == f"%{100 * p:.0f}"
    assert any(b.label == "Oyuncu sayfasında aç" for b in at.button)
    # 8.3: Sofascore + TM; TM profili yalniz KABUL edilmis eslesmeden (§60)
    lb = {x.proto.label: x.proto.url for x in at.get("link_button")}
    prof = _ust_oyuncu(f"""SELECT p.url FROM player_links l
        JOIN tm_players p ON p.player_id = l.tm_id
        WHERE l.player_id = {pid} AND l.confidence IN ('A','B','M')""")
    assert "sofascore.com" in lb["Sofascore"]
    if prof and prof[0]:
        assert lb["Transfermarkt"] == prof[0]
    # profil: her yüzdeliğin yanında ham değeri var (ilk sürümde katalogda
    # olmayan blocks_padj / duel_win_pct_sh için "—" çıkıyordu)
    import json
    metin = json.loads(at.get("plotly_chart")[0].proto.spec)["data"][0]["text"]
    assert len(metin) >= 4 and not any("—" in m for m in metin), metin


@veri_var
def test_tm_karti_acilir():
    pid, comp, sez, ad = _ust_oyuncu("""
        SELECT player_id, comp, season, player_name FROM tm_iddia_defteri
        ORDER BY model_olasilik DESC LIMIT 1""")
    at = _at(oyuncu=f"{pid}-{comp}-{sez}")
    _kaynak(at, HV.KAYNAK_TM)
    assert any(f'class="ad">{ad}<' in m.value for m in at.markdown)
    assert any("Boy / ayak" in m.value for m in at.markdown)
