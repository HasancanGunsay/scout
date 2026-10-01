"""Metrik ve percentile testleri."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features import metrics as met
from scout.features import percentile as pct


def _df(n=40, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "player_id": range(n),
        "league_id": 72, "season": 2024,
        "position": ["Attacker"] * n,
        "minutes": rng.uniform(200, 3000, n),
        "goals": rng.poisson(5, n).astype(float),
        "assists": rng.poisson(3, n).astype(float),
        "pens_scored": 0.0,
        "shots": rng.poisson(25, n).astype(float),
        "shots_on": rng.poisson(10, n).astype(float),
        "duels": rng.poisson(120, n).astype(float),
        "duels_won": rng.poisson(60, n).astype(float),
        "dribbles": rng.poisson(20, n).astype(float),
        "dribbles_won": rng.poisson(9, n).astype(float),
        "tackles": rng.poisson(15, n).astype(float),
        "interceptions": rng.poisson(8, n).astype(float),
        "blocks": rng.poisson(3, n).astype(float),
        "key_passes": rng.poisson(15, n).astype(float),
        "passes": rng.poisson(600, n).astype(float),
        "fouls_made": rng.poisson(12, n).astype(float),
        "fouls_drawn": rng.poisson(14, n).astype(float),
        "yellow": rng.poisson(3, n).astype(float),
        "red": 0.0,
        "starts": rng.uniform(1, 30, n),
        "apps": rng.uniform(5, 34, n),
    }).assign(nineties=lambda d: d.minutes / 90.0)


class TestPositionGroup:
    def test_forward_attacker_olarak_eslenir(self):
        """GERCEK HATA: API bazen 'Forward' donduruyordu ve bu oyuncular
        'Unknown' grubuna dusup HIC SKOR ALMIYORDU (16 oyuncu, biri tam sezon)."""
        d = pd.DataFrame({"position": ["Forward", "Attacker", "Striker"]})
        out = met.add_position_group(d)
        assert (out.pos_group == "Attacker").all()

    def test_bilinmeyen_etiket_uyari_verir(self):
        """Sessizce kaybolmasin - yeni etiket gelirse haber versin."""
        d = pd.DataFrame({"position": ["Sweeper"], "minutes": [900.0]})
        with pytest.warns(UserWarning, match="SKOR ALMAYACAK.*Sweeper"):
            out = met.add_position_group(d)
        assert out.pos_group.iloc[0] == "Unknown"

    def test_bos_mevki_de_uyari_verir(self):
        """API bazen mevki alanini bos donduruyor (6 Arjantinli, 1823 dakika).
        Bu da sessizce dusmemeli."""
        d = pd.DataFrame({"position": [None, None], "minutes": [990.0, 331.0]})
        with pytest.warns(UserWarning, match="mevki BOS"):
            out = met.add_position_group(d)
        assert (out.pos_group == "Unknown").all()

    def test_temiz_veride_uyari_yok(self):
        d = pd.DataFrame({"position": ["Attacker", "Forward"], "minutes": [90.0, 90.0]})
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("error")
            out = met.add_position_group(d)
        assert (out.pos_group == "Attacker").all()

    def test_dort_temel_grup_korunur(self):
        d = pd.DataFrame({"position": ["Goalkeeper", "Defender",
                                       "Midfielder", "Attacker"]})
        out = met.add_position_group(d)
        assert list(out.pos_group) == ["Goalkeeper", "Defender",
                                       "Midfielder", "Attacker"]


class TestPer90:
    def test_per90_dogru_hesaplanir(self):
        d = pd.DataFrame({"goals": [9.0], "assists": [0.0], "pens_scored": [0.0],
                          "nineties": [9.0]})
        out = met.add_per90(d)
        assert out.goals_p90.iloc[0] == pytest.approx(1.0)

    def test_penaltisiz_gol_cikarilir(self):
        d = pd.DataFrame({"goals": [10.0], "assists": [0.0], "pens_scored": [3.0],
                          "nineties": [10.0]})
        out = met.add_per90(d)
        assert out.np_goals_raw.iloc[0] == pytest.approx(7.0)

    def test_negatif_uretilmez(self):
        """pens_scored > goals gibi bozuk veri negatif uretmemeli."""
        d = pd.DataFrame({"goals": [1.0], "assists": [0.0], "pens_scored": [5.0],
                          "nineties": [10.0]})
        out = met.add_per90(d)
        assert out.np_goals_raw.iloc[0] >= 0

    def test_sifir_dakika_nan_verir_bolme_hatasi_degil(self):
        d = pd.DataFrame({"goals": [0.0], "assists": [0.0], "pens_scored": [0.0],
                          "nineties": [0.0]})
        out = met.add_per90(d)
        assert pd.isna(out.goals_p90.iloc[0])


class TestRates:
    def test_sifir_paydada_nan(self):
        """0 sut atan oyuncunun isabet orani %0 DEGIL, tanimsizdir."""
        d = pd.DataFrame({"shots": [0.0], "shots_on": [0.0],
                          "duels": [10.0], "duels_won": [6.0],
                          "dribbles": [0.0], "dribbles_won": [0.0],
                          "goals": [0.0], "starts": [1.0], "apps": [1.0]})
        out = met.add_rates(d)
        assert pd.isna(out.shot_accuracy.iloc[0])
        assert out.duel_win_pct.iloc[0] == pytest.approx(0.6)


class TestPercentile:
    def test_0_100_araliginda(self):
        d = met.build(_df())
        out = pct.percentile_in_cohort(d, ["goals_p90"],
                                       cohort=["league_id", "season", "pos_group"])
        v = out.goals_p90_pct.dropna()
        assert v.min() >= 0 and v.max() <= 100

    def test_kucuk_kohortta_uretilmez(self):
        """8 kisilik havuzda '85. percentile' anlamsizdir."""
        d = met.build(_df(n=8))
        out = pct.percentile_in_cohort(d, ["goals_p90"],
                                       cohort=["league_id", "season", "pos_group"],
                                       min_size=12)
        assert out.goals_p90_pct.isna().all()

    def test_siralama_korunur(self):
        """Percentile bir SIRA donusumu - Pearson degil SPEARMAN 1 olmali.

        (Ham deger ile percentile arasinda Pearson korelasyonu ancak dagilim
        duzgunse 1'e yaklasir; sira korelasyonu ise tanim geregi tam olmali.)
        """
        d = met.build(_df())
        out = pct.percentile_in_cohort(d, ["goals_p90"],
                                       cohort=["league_id", "season", "pos_group"])
        s = out.dropna(subset=["goals_p90", "goals_p90_pct"])
        assert s.goals_p90.corr(s.goals_p90_pct, method="spearman") == pytest.approx(1.0)

    def test_invert_ters_cevirir(self):
        d = met.build(_df())
        out = pct.percentile_in_cohort(d, ["fouls_made_p90"],
                                       cohort=["league_id", "season", "pos_group"])
        before = out.fouls_made_p90_pct.copy()
        after = pct.invert(out, {"fouls_made": "fouls_made_p90"}).fouls_made_p90_pct
        assert np.allclose(before + after, 100.0, equal_nan=True)

    def test_yayinlanmayan_metrik_NaN_kalir(self):
        """Ligin hic yayinlamadigi metrik 0 degil NaN olmali (§21).

        Eski surumde _sum_cols fillna(0) yapiyordu; build_db'nin bilincli
        olarak NaN biraktigi 'bu lig bu metrigi vermiyor' durumu geri sifira
        donuyordu. Sonuc: Veikkausliiga'da var olmayan veriden 1.046 skor
        uretildi ve ortalamasi 50,1 ile normal gorundu.
        """
        d = _df()
        d["shots"] = np.nan          # lig sut verisi yayinlamiyor
        out = met.build(d)
        assert out["shots_raw"].isna().all(), "yayinlanmayan metrik 0'a cevrildi"
        assert out["shots_p90"].isna().all()
        # bilinen metrik etkilenmemeli
        assert out["goals_raw"].notna().any()

    def test_kismi_bilinen_metrik_toplanir(self):
        """En az bir bilesen biliniyorsa toplanir - hepsi NaN degilse NaN olmaz."""
        d = _df()
        d["pens_scored"] = np.nan     # penalti verisi yok, gol verisi var
        out = met.build(d)
        assert out["np_goals_raw"].notna().any()

    def test_invert_isaret_sutunu_birakir(self):
        """CIFT TERS CEVIRME hatasina karsi kilit.

        percentile.invert bir sutunu cevirdiginde '<anahtar>_inverted' isaretini
        birakmali. scoring/engine.py bu isarete bakip ikinci kez cevirmiyor.
        Isaret uretilmedigi surece engine her seferinde tekrar ceviriyordu ve
        'cok faul yapan oyuncu iyidir' sonucu cikiyordu (§16).
        """
        d = met.build(_df())
        out = pct.percentile_in_cohort(d, ["fouls_made_p90"],
                                       cohort=["league_id", "season", "pos_group"])
        inv = pct.invert(out, {"fouls_made": "fouls_made_p90"})
        assert "fouls_made_inverted" in inv.columns
        assert bool(inv["fouls_made_inverted"].all())
