"""Kalibratoru zaman icinde nasil guncellemeli? (FAZ 7.3)

SORUN
Model yildan yila iyi SIRALIYOR ama olasiliklarin kendisi oynuyor: TM
muhurlu testinde sezon sapmasi +0,063 / -0,056 / +0,011 / +0,017 (§53.5),
API doneminde dusuk gorunurluk iyimserligi 2022 -> 2024 azaldi (§50.4).
Taban oran degisiyor (2019/20 COVID: %64).

KURALLAR - hedef sezon s icin, YALNIZ s'den onceki sezonlarin ileri-zincir
tahminleri ve sonuclari kullanilir (s-1'in 12 aylik penceresi s'nin
tahmin aninda kapanmis olur):
  ham            kalibrasyon yok
  tum_gecmis     Platt, onceki TUM sezonlar (6.6'daki yaklasimin zaman karsiligi)
  son1           Platt, yalniz s-1
  son2           Platt, s-2 ve s-1
  son1_kesisim   yalniz kesisim kaydirmasi, s-1 (tek parametre)
  agirlikli      Platt, tum gecmis, ustel agirlik (yarilanma 1 sezon)

METIN URETMEZ.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scout.model.kalibrasyon import kesisim_fit, platt_fit, platt_uygula

KURALLAR = ["ham", "tum_gecmis", "son1", "son2", "son1_kesisim", "agirlikli"]
YARILANMA = 1.0          # sezon; onceden sabit, ayarlanmaz


def kalibre(gecmis: pd.DataFrame, p_hedef, hedef_sezon: int,
            kural: str) -> np.ndarray:
    """gecmis: (season, p, y) - ileri-zincir tahminler. Yalniz hedef
    sezondan ONCEKI sezonlar kullanilir; sonrasi verilse bile gormez."""
    p_hedef = np.asarray(p_hedef, float)
    if kural == "ham":
        return p_hedef
    g = gecmis[gecmis.season < hedef_sezon]
    if g.empty:
        return p_hedef
    son = g.season.max()
    if kural == "tum_gecmis":
        ab = platt_fit(g.p, g.y)
    elif kural == "son1":
        s = g[g.season == son]
        ab = platt_fit(s.p, s.y)
    elif kural == "son2":
        s = g[g.season >= son - 1]
        ab = platt_fit(s.p, s.y)
    elif kural == "son1_kesisim":
        s = g[g.season == son]
        ab = kesisim_fit(s.p, s.y)
    elif kural == "agirlikli":
        w = 0.5 ** ((son - g.season) / YARILANMA)
        ab = platt_fit(g.p, g.y, w=w.to_numpy())
    else:
        raise ValueError(f"bilinmeyen kural: {kural}")
    return platt_uygula(p_hedef, ab)
