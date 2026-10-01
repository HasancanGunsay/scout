"""Kadro rol haritasi testleri.

EN KRITIK TEST: tabanin OYUNCU medyani degil TAKIM medyani olmasi.
Oyuncu medyani alsaydik yedekler de sayilirdi, taban asagi cekilirdi ve
neredeyse her takim her rolde "ortalamanin ustunde" cikardi - yani
harita hicbir sey soylemezdi. test_taban_yedekleri_saymaz bunu koruyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.squad import (ESIK, GECMIS_YEDEK_BENZERLIGI, durum,
                                  rol_haritasi, yas_profili,
                                  yedek_benzerligi_notu)


def _veri(n_takim=10, n_oyuncu=8, n_rol=3, seed=1):
    """Her takimda ayni sayida oyuncu, skorlar rastgele."""
    rng = np.random.default_rng(seed)
    kayit = []
    pid = 0
    for t in range(n_takim):
        for o in range(n_oyuncu):
            pid += 1
            for r in range(n_rol):
                kayit.append(dict(
                    player_id=pid, player_name=f"o{pid}",
                    team_name=f"T{t}", role=f"r{r}", role_name=f"Rol {r}",
                    score=float(rng.uniform(20, 90)),
                    minutes=float(rng.integers(500, 2700)),
                    age_season_end=float(rng.uniform(18, 34)),
                ))
    return pd.DataFrame(kayit)


def test_temel_sutunlar():
    h = rol_haritasi(_veri(), "T0")
    assert set(h.columns) >= {"role", "role_name", "player_name", "score",
                              "lig_taban", "fark", "derinlik", "durum"}
    assert len(h) == 3                      # rol basina tek satir
    assert h.durum.isin(["guclu", "ortalama", "bosluk"]).all()


def test_eksik_sutun_hata_verir():
    df = _veri().drop(columns=["role_name"])
    with pytest.raises(KeyError):
        rol_haritasi(df, "T0")


def test_bilinmeyen_takim_bos_doner():
    assert rol_haritasi(_veri(), "YOK").empty


def test_taban_takimlarin_en_iyisinin_medyani():
    """Taban elle hesaplananla ayni olmali."""
    df = _veri()
    h = rol_haritasi(df, "T0")
    for r in h.itertuples():
        bek = (df[df.role == r.role].groupby("team_name").score.max().median())
        assert r.lig_taban == pytest.approx(bek)


def test_taban_yedekleri_saymaz():
    """Taban OYUNCU medyani olsaydi neredeyse herkes ustte cikardi.

    Bu testin korudugu sey: takimlarin yaklasik yarisi tabanin ustunde,
    yarisi altinda olmali. Oyuncu medyani kullanilsaydi bu oran ~%90'a
    cikardi cunku her takimin EN IYISI, ligin ORTALAMA oyuncusundan
    neredeyse her zaman iyidir.
    """
    df = _veri(n_takim=20, n_oyuncu=10, n_rol=4, seed=7)
    ustte = 0
    toplam = 0
    for t in df.team_name.unique():
        h = rol_haritasi(df, t)
        ustte += int((h.fark > 0).sum())
        toplam += len(h)
    oran = ustte / toplam
    assert 0.35 < oran < 0.65, f"takim-taban dengesiz: %{100 * oran:.0f}"

    # Kontrol: oyuncu medyani tabaniyla oran cok daha yuksek olurdu
    oyuncu_medyan = df.groupby("role").score.median()
    en_iyiler = df.groupby(["team_name", "role"]).score.max().reset_index()
    yanlis_oran = (en_iyiler.score
                   > en_iyiler.role.map(oyuncu_medyan)).mean()
    assert yanlis_oran > 0.85


def test_en_iyi_gercekten_en_yuksek_skorlu():
    df = _veri()
    h = rol_haritasi(df, "T3")
    for r in h.itertuples():
        kadro = df[(df.team_name == "T3") & (df.role == r.role)]
        assert r.score == pytest.approx(kadro.score.max())
        assert r.player_name == kadro.loc[kadro.score.idxmax(), "player_name"]


def test_derinlik_sifir_olabilir():
    """En iyimiz bile lig oyuncu medyaninin altindaysa derinlik 0.

    Arayuzde bunun ayrica aciklanmasi gerekiyor - 'derinlik 0' ilk bakista
    'veri yok' gibi okunuyor, oysa 'o rolde kimse yok' demek.
    """
    df = _veri(n_takim=6, n_oyuncu=4, n_rol=1, seed=2)
    df.loc[df.team_name == "T0", "score"] = 5.0     # herkesten kotu
    h = rol_haritasi(df, "T0")
    assert int(h.derinlik.iloc[0]) == 0
    assert h.durum.iloc[0] == "bosluk"


def test_nan_skorlar_elenir():
    df = _veri()
    df.loc[df.team_name == "T0", "score"] = np.nan
    assert rol_haritasi(df, "T0").empty


def test_esik_durumu_belirler():
    assert durum(ESIK + 0.1) == "guclu"
    assert durum(-ESIK - 0.1) == "bosluk"
    assert durum(0.0) == "ortalama"
    assert durum(float("nan")) == "ortalama"


def test_yas_sutunu_zorunlu_degil():
    df = _veri().drop(columns=["age_season_end"])
    h = rol_haritasi(df, "T0")
    assert not h.empty
    assert "age_season_end" not in h.columns


# ------------------------------------------------------------ yas profili
def test_yas_profili_dakika_agirlikli():
    """Oyuncu SAYISI degil DAKIKA payi olculmeli.

    Iki genc oyuncu 100'er dakika, bir yasli 3000 dakika oynadiysa kadro
    'genc' degildir. Sayi saysaydik %67 genc cikardi.
    """
    df = pd.DataFrame({
        "player_id": [1, 2, 3],
        "age_season_end": [19.0, 20.0, 33.0],
        "minutes": [100.0, 100.0, 3000.0],
    })
    o = yas_profili(df).set_index("bant").pay
    assert o["U21"] == pytest.approx(200 / 3200 * 100)
    assert o["31+"] == pytest.approx(3000 / 3200 * 100)


def test_yas_profili_paylar_yuze_toplanir():
    o = yas_profili(_veri(n_takim=1, n_oyuncu=20, n_rol=1))
    assert o.pay.sum() == pytest.approx(100.0)


def test_yas_profili_bos_veri():
    o = yas_profili(pd.DataFrame({"player_id": [], "age_season_end": [],
                                  "minutes": []}))
    assert o.empty


def test_yas_profili_oyuncu_tekillestirir():
    """Ayni oyuncu 14 rolde gorunuyor - dakikasi 14 kez sayilmamali."""
    df = pd.DataFrame({
        "player_id": [1] * 5 + [2] * 5,
        "age_season_end": [19.0] * 5 + [33.0] * 5,
        "minutes": [1000.0] * 5 + [1000.0] * 5,
    })
    o = yas_profili(df).set_index("bant")
    assert int(o.loc["U21", "oyuncu"]) == 1
    assert o.loc["U21", "dakika"] == pytest.approx(1000.0)

# --------------------------------------------- olculmus degerler kilitli
def test_esik_olculmus_degerde_kalir():
    """Esik 8'den 12'ye OLCULEREK cikarildi (§35) - sessizce geri donmesin.

    Olcum: kadrosu degismemis takim-rol ciftlerinde 'fark' sezonlar arasi
    kendiliginden oynuyor; |degisim| %68 yuzdeligi 12,1. Eski 8 esigi
    vakalarin yalnizca %51'ini kapsiyordu, yani gurultuye 'bosluk' diyordu.
    Degistirmek icin once scripts/validate_squad.py yeniden calistirilmali.
    """
    assert ESIK == 12.0


def test_kaleci_yedek_benzerligi_ters():
    """En carpici bulgu: kalecide etki TERSINE donuyor.

    Kulupler kaleci degistirirken rastgeleden DAHA FARKLI stilde biri
    aliyor (-0,170, GA tamami negatif). Arayuz bunu aciktan uyarmali -
    sessizce yanlis yol gostermek en kotu secenek.
    """
    ort, lo, hi, n = GECMIS_YEDEK_BENZERLIGI["Goalkeeper"]
    assert hi < 0, "kaleci bulgusu artik negatif degil - arayuz notu yenilenmeli"
    seviye, o, l, h, nn = yedek_benzerligi_notu("Goalkeeper")
    assert seviye == "ters"
    assert (o, l, h, nn) == (ort, lo, hi, n)


def test_notu_metin_uretmez():
    """src/ dilden bagimsiz kalmali - Turkce cumleyi arayuz kuruyor.

    Ilk surumde metin burada uretiliyordu ve sayfada Turkce arayuzun
    ortasinda ASCII bir cumle olarak goruldu.
    """
    for deger in yedek_benzerligi_notu("Defender"):
        assert not isinstance(deger, str) or deger == "guclu"


def test_yedek_benzerligi_seviyeleri():
    assert yedek_benzerligi_notu("Defender")[0] == "guclu"
    assert yedek_benzerligi_notu("Attacker")[0] == "zayif"
    assert yedek_benzerligi_notu("Midfielder")[0] == "zayif"
    assert yedek_benzerligi_notu("Yok")[0] == "bilinmiyor"


def test_yedek_benzerligi_guven_araliklari_tutarli():
    for pg, (ort, lo, hi, n) in GECMIS_YEDEK_BENZERLIGI.items():
        assert lo < ort < hi, f"{pg}: ortalama GA disinda"
        assert n > 0
