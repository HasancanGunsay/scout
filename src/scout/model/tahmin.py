"""Tek dogruluk kaynagi: player_tahmin (FAZ 7.0).

SORUN
FAZ 7.0'a kadar iki ayri olasilik vardi:
  player_ranking      disaridan (lig-disi CV / zaman-disi), kalibre
  player_model_score  uretim modeli - 2022-24'u EGITIMDE GORMUS (orneklem ici)
Ayni oyuncu Mevki Siralamasi'nda %48, Scout Dosyasi'nda %70 gorunebiliyordu;
ikincisi gecmis sezonlarda cevabi bilen modelden geliyordu.

KURAL
Bir sezon icin disaridan tahmin VARSA o kullanilir. Yalnizca disaridan tahmin
olmayan satirlar (sonucu henuz bilinmeyen yeni sezonlar: 2025+) uretim
modelinden gelir; onlar zaten disaridir. Uretim tahmini de ayni kapsam
kalibratoruyle (data/kalibrator.json) duzeltilir.

METIN URETMEZ - tahmin_turu kodlari ASCII.
"""

from __future__ import annotations

import pandas as pd

from scout.model.kalibrasyon import GLOBAL, grup_uygula

ANAHTAR = ["player_id", "league_id", "season"]
SUTUNLAR = ANAHTAR + ["kapsam", "model_olasilik", "model_ham", "tahmin_turu"]
TUR_URETIM = "uretim"
TUR_URETIM_KALIBRESIZ = "uretim_kalibresiz"


def tahmin_tablosu(ranking: pd.DataFrame, uretim: pd.DataFrame | None = None,
                   kalibrator: dict | None = None) -> pd.DataFrame:
    """ranking : player_ranking (model_olasilik kalibre, model_ham ham)
    uretim  : player_model_score + kapsam (model_olasilik = HAM uretim)
    kalibrator : kalibrator.json'daki parametre['model'] sozlugu
    """
    r = ranking.copy()
    if "model_ham" not in r:
        r["model_ham"] = r.model_olasilik
    out = [r[SUTUNLAR]]

    if uretim is not None and len(uretim):
        u = uretim.merge(r[ANAHTAR], on=ANAHTAR, how="left", indicator=True)
        u = u[u._merge == "left_only"].drop(columns="_merge").copy()
        if len(u):
            u["model_ham"] = u.model_olasilik
            if kalibrator and GLOBAL in kalibrator:
                u["model_olasilik"] = grup_uygula(
                    u.model_ham, u.kapsam.astype(str), kalibrator)
                u["tahmin_turu"] = TUR_URETIM
            else:
                u["tahmin_turu"] = TUR_URETIM_KALIBRESIZ
            out.append(u[SUTUNLAR])

    t = pd.concat(out, ignore_index=True)
    assert not t.duplicated(ANAHTAR).any(), "player_tahmin anahtari tekil degil"
    return t
