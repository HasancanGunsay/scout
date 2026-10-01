"""Boylamsal yas egrisi testleri.

NEDEN BOYLAMSAL: kesitsel fit iki kez reddedildi (§19). Yas-performans
kesitine egri uydurmak HAYATTA KALMA YANLILIGI tasir - 35 yasinda hala
oynayanlar secilmis bir azinliktir ve egri onlarin iyiligini yasa mal
eder. Olculdu: kesitsel egri 16'dan 38'e monoton artiyordu.

Fark yontemi (ayni oyuncunun ardisik sezonlari) bunu yapisal olarak
cozer: oyuncu kendi kontrolu olur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scout.features.age_long import BoylamsalYasEgrisi, gecisler


def _panel(n=500, tepe=26.0, seed=4, ayni_lig=True):
    """Bilinen tepesi olan sentetik panel: performans = -(yas-tepe)^2."""
    rng = np.random.default_rng(seed)
    satir = []
    for pid in range(n):
        yas0 = rng.uniform(18, 32)
        # ayni_lig=False iken oyuncularin bir kismi SEZON ARASINDA lig
        # degistirsin - aksi halde kisit test edilemez.
        ligler = ([1, 1, 1] if ayni_lig
                  else list(rng.integers(1, 4, 3)))
        for k, sezon in enumerate((2022, 2023, 2024)):
            yas = yas0 + k
            lig = int(ligler[k])
            satir.append({
                "player_id": pid, "season": sezon, "league_id": lig,
                "age_season_end": yas, "minutes": 1500.0,
                "score": 60.0 - 0.25 * (yas - tepe) ** 2 + rng.normal(0, 1.5),
            })
    return pd.DataFrame(satir)


class TestGecisler:
    def test_uc_sezon_iki_gecis(self):
        g = gecisler(_panel(n=10), "score")
        assert len(g) == 20

    def test_yillik_normalize(self):
        d = _panel(n=5)
        d = d[d.season != 2023]           # 2022 -> 2024, iki yillik bosluk
        g = gecisler(d, "score")
        assert (g.fark_yil == 2).all()

    def test_ayni_lig_kisiti(self):
        d = _panel(n=60, ayni_lig=False)
        hepsi = gecisler(d, "score", ayni_lig=False)
        kisitli = gecisler(d, "score", ayni_lig=True)
        assert len(kisitli) < len(hepsi)


class TestEgri:
    def test_bilinen_tepeyi_buluyor(self):
        e = BoylamsalYasEgrisi(derece=2).fit(_panel(n=800, tepe=26.0), "score")
        assert e.egri_ is not None
        assert abs(e.tepe_yas_ - 26.0) <= 2.5, f"tepe {e.tepe_yas_}"
        assert e.makul

    def test_monoton_artan_panel_REDDEDILIR(self):
        """Hayatta kalma yanliligi deseni: hep yukari giden egri kabul edilmemeli."""
        rng = np.random.default_rng(1)
        satir = []
        for pid in range(400):
            yas0 = rng.uniform(18, 32)
            for k, sezon in enumerate((2022, 2023, 2024)):
                satir.append({"player_id": pid, "season": sezon, "league_id": 1,
                              "age_season_end": yas0 + k, "minutes": 1500.0,
                              "score": 40 + 0.8 * (yas0 + k) + rng.normal(0, 1)})
        e = BoylamsalYasEgrisi(derece=2).fit(pd.DataFrame(satir), "score")
        assert not e.makul, f"monoton artan egri kabul edildi (tepe {e.tepe_yas_})"

    def test_duzlestirme_gurultuyu_azaltiyor(self):
        """Duzlestirmesiz egri, gurultulu uc kutulara esir olur."""
        d = _panel(n=600, tepe=26.0)
        ham = BoylamsalYasEgrisi(derece=0).fit(d, "score")
        duz = BoylamsalYasEgrisi(derece=2).fit(d, "score")
        assert abs(duz.tepe_yas_ - 26.0) <= abs(ham.tepe_yas_ - 26.0) + 1e-9

    def test_yetersiz_veri_egri_uretmez(self):
        e = BoylamsalYasEgrisi().fit(_panel(n=5), "score")
        assert e.egri_ is None and not e.makul
