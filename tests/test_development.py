"""Gelisim egrisi testleri.

NEDEN ONEMLI: ilk surum rolu tek bir sezona sabitliyordu. 'Dogal rol'
14 rolun MAKSIMUMU oldugu icin, sabitlenen sezonun skoru maksimum,
otekinin skoru maksimum-olmayan oluyordu ve fark KURGU GEREGI kayiyordu.
Olculdu: rolu 2022'ye sabitleyince ortalama gelisim -5,41; 2024'e
sabitleyince +3,89. Ayni veri, ters isaret.

Simetrik secim ('ortak' = iki sezonun ortalamasini en yuksek yapan rol)
bunu kaldiriyor: -0,78.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.development import gelisim

ROLLER = ["r1", "r2", "r3"]


def _veri(n=200, seed=3):
    """Gercek bir gelisim OLMAYAN sentetik veri.

    Her oyuncunun her rolde skoru rastgele; sezonlar arasi sistematik
    degisim yok. Dolayisiyla dogru bir olcum ~0 ortalama vermeli.
    """
    rng = np.random.default_rng(seed)
    satir, nat = [], []
    for pid in range(n):
        for sezon in (2022, 2024):
            skorlar = rng.uniform(10, 95, len(ROLLER))
            for rol, sk in zip(ROLLER, skorlar, strict=False):
                satir.append({"player_id": pid, "season": sezon, "role": rol,
                              "role_name": rol, "score": sk,
                              "score_age": sk, "coverage": 1.0,
                              "minutes": 1500, "age_season_end": 22.0,
                              "league_name": "L", "country": "C",
                              "team_name": "T", "player_name": f"P{pid}"})
            en_iyi = ROLLER[int(np.argmax(skorlar))]
            nat.append({"player_id": pid, "season": sezon, "role": en_iyi,
                        "role_name": en_iyi})
    return pd.DataFrame(satir), pd.DataFrame(nat)


class TestSecilimYanliligi:
    def test_tek_sezona_sabitleme_YANLI(self):
        """Kirik davranisi belgeler: iki yon zit isaretli olmali."""
        sc, nat = _veri()
        onceki = gelisim(sc, nat, rol_kaynagi="onceki").gelisim.mean()
        sonraki = gelisim(sc, nat, rol_kaynagi="sonraki").gelisim.mean()
        assert onceki < -2, f"beklenen negatif sapma yok: {onceki}"
        assert sonraki > 2, f"beklenen pozitif sapma yok: {sonraki}"

    def test_ortak_rol_yanliligi_KALDIRIR(self):
        """Gercek gelisim yokken ortalama ~0 olmali."""
        sc, nat = _veri()
        ort = gelisim(sc, nat, rol_kaynagi="ortak").gelisim.mean()
        assert abs(ort) < 2.0, f"simetrik secimde sapma kalmis: {ort}"

    def test_varsayilan_ortak(self):
        sc, nat = _veri()
        assert gelisim(sc, nat).equals(gelisim(sc, nat, rol_kaynagi="ortak"))


class TestTemelDavranis:
    def test_iki_sezonda_da_skoru_olmayan_disarida(self):
        sc, nat = _veri(n=50)
        sc = sc[~((sc.player_id == 0) & (sc.season == 2024))]
        assert 0 not in set(gelisim(sc, nat).player_id)

    def test_dakika_esigi_uygulaniyor(self):
        sc, nat = _veri(n=50)
        sc.loc[sc.player_id == 1, "minutes"] = 100
        assert 1 not in set(gelisim(sc, nat, min_dakika=450).player_id)

    def test_gelisim_delta_dogru(self):
        sc, nat = _veri(n=40)
        g = gelisim(sc, nat)
        assert np.allclose(g.gelisim, g.score_1 - g.score_0)
