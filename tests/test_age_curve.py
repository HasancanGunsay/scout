"""Yas egrisi kabul kapisi testleri.

NEDEN ONEMLI: 11 Agustos 2026'da 2022 verisi gelince egri kendiliginden
"aktiflesti" ama fit edilen egri 16 yasindan 38 yasina kadar MONOTON
ARTIYORDU - hic tepe yapmadan. Bu, hayatta kalma yanliliginin imzasi:
35 yasinda hala oynayanlar secilmis bir azinlik ve egri onlarin iyiligini
yasa mal ediyor.

O gunku kapi (aralik + iki sezon) bunu gecirmisti. Bu testler sekil
sartlarini kilitliyor (§19).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.age import AgeCurve


def _df(rating_fn, n: int = 600, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    yas = rng.uniform(17, 37, n)
    return pd.DataFrame({
        "age_season_end": yas,
        "rating": rating_fn(yas) + rng.normal(0, 0.05, n),
        "league_id": rng.choice([1, 2, 3], n),
        "nineties": rng.uniform(6, 34, n),
        "season": rng.choice([2022, 2024], n),
    })


class TestKabulKapisi:
    def test_monoton_artan_egri_REDDEDILIR(self):
        """Hayatta kalma yanliligi deseni: yas arttikca performans artiyor.

        Gercekte olan buydu ve kabul edilmisti. Bir daha edilmemeli.
        """
        c = AgeCurve().fit(_df(lambda a: 6.7 + 0.01 * a), "rating")
        assert not c.informative, (
            f"monoton artan egri kabul edildi - tepe {c.peak_age_}, "
            f"dusus {c.decline_after_peak_}"
        )

    def test_monoton_azalan_egri_REDDEDILIR(self):
        c = AgeCurve().fit(_df(lambda a: 7.4 - 0.01 * a), "rating")
        assert not c.informative

    def test_makul_tepeli_egri_KABUL_EDILIR(self):
        """26 yas civarinda tepe yapip dusen egri - futbolca dogru sekil."""
        c = AgeCurve().fit(_df(lambda a: 7.0 - 0.004 * (a - 26.0) ** 2), "rating")
        assert c.informative, (
            f"gecerli egri reddedildi - tepe {c.peak_age_}, "
            f"aralik {c.curve_range_}, dusus {c.decline_after_peak_}"
        )
        assert 23.0 <= c.peak_age_ <= 32.0

    def test_tepe_yasi_dogru_bulunuyor(self):
        c = AgeCurve().fit(_df(lambda a: 7.0 - 0.004 * (a - 27.0) ** 2), "rating")
        assert c.peak_age_ == pytest.approx(27.0, abs=1.5)

    def test_tek_sezon_her_halukarda_REDDEDILIR(self):
        d = _df(lambda a: 7.0 - 0.004 * (a - 26.0) ** 2)
        d["season"] = 2024
        assert not AgeCurve().fit(d, "rating").informative
