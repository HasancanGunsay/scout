"""TM ileriye donuk defteri (FAZ 7.5): 2025/26 havuzunun TAMAMI, bugun.

NEDEN
API ucretsiz plani 2025'i acmiyor; ne zaman acacagi bilinmiyor. Ama TM
2025/26 sezonunu iceriyor ve TM modeli muhurlu testte gecti (§53). Sonuc
penceresi (sezon bitisi 2026-06-15 -> 2027-06-15) ACIK: bugun yazilan
olasilik, sonucu kimsenin bilmedigi bir iddiadir. Gercek sicil budur.

KULLANICININ ISTEDIGI (1 Eki 2026): tek isim degil, HAVUZ. Bu yuzden
deftere birkac isim degil, 2025/26'da izlenen 14 ligde >=450 dk oynamis
TUM U23'ler yazilir - kendi siralamalariyla. Arayuz (FAZ 8) havuzu buradan
okur.

KURALLAR
- Ekleme yalniz: ayni (oyuncu, lig, sezon, model_surumu) ikinci kez yazilmaz.
- Puanlama yalniz pencere TAMAMEN kapandiginda (sansur, §outcome).
- Onceden yazilan olcutler (PLAN §56): P1 model > dakika+yas, P2 model >
  piyasa (lig-ici AUC), P3 kalibrasyon, P4 ucuz bant top-20.

METIN URETMEZ.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

MODEL_SURUMU = "tm_tam_v1"      # §53: 2013-2024 ile egitilmis 'tam'
DEFTER_SEZONU = 2025
PENCERE_BITIS = dt.date(2027, 6, 15)   # sezon_bitis(2025) + 12 ay
UCUZ_TAVAN = 5e6
ANAHTAR = ["player_id", "comp", "season", "model_surumu"]

SUTUNLAR = [
    "kayit_tarihi", "kaynak_surum", "model_surumu", "player_id", "player_name",
    "comp", "season", "club_id", "kulup", "guncel_kulup", "ince_mevki",
    "pos_group", "yas", "dk", "dakika_payi", "ilk11", "ilk11_payi", "gol",
    "asist", "ga_90", "deger", "deger_var", "deger_durumu", "ucuz",
    "model_olasilik",
    "saf_olasilik", "basit_olasilik", "piyasa_olasilik", "sira_lig_mevki",
    "sira_mevki", "pencere_bitis",
]


def kayit_tablosu(h: pd.DataFrame, kayit_tarihi: dt.date,
                  kaynak_surum: str) -> pd.DataFrame:
    """Tahminleri (model/saf/basit/piyasa sutunlari ile) defter satirina
    cevir ve siralari ekle. Siralar model olasiligina gore, 1 = en yuksek."""
    d = h.copy()
    d["kayit_tarihi"] = kayit_tarihi.isoformat()
    d["kaynak_surum"] = kaynak_surum
    d["model_surumu"] = MODEL_SURUMU
    d["model_olasilik"] = d.pop("model")
    d["saf_olasilik"] = d.pop("saf")
    d["basit_olasilik"] = d.pop("basit")
    d["piyasa_olasilik"] = d.pop("piyasa")
    # 2025'te degerleme yoklugu GORUNMEZLIK DEGIL, anlik goruntu boslugu:
    # Wesley (Roma), Bonny (Inter) gibi oyuncularin hic degerlemesi yok
    # (TM degerleri 2026-02-27'de bitiyor). API donemindeki "degersiz =
    # dusuk gorunurluk" (§39.4) burada GECERSIZ - degersiz ucuz SAYILMAZ.
    d["ucuz"] = (d.deger_var == 1) & (d.deger <= UCUZ_TAVAN)
    d["deger_durumu"] = np.where(d.deger_var == 1, "var", "bilinmiyor")
    d["sira_lig_mevki"] = d.groupby(["comp", "pos_group"]).model_olasilik.rank(
        ascending=False, method="first").astype(int)
    d["sira_mevki"] = d.groupby("pos_group").model_olasilik.rank(
        ascending=False, method="first").astype(int)
    d["pencere_bitis"] = PENCERE_BITIS.isoformat()
    for c in SUTUNLAR:
        if c not in d:
            d[c] = None
    return d[SUTUNLAR].reset_index(drop=True)


def yeni_satirlar(aday: pd.DataFrame, eski: pd.DataFrame) -> pd.DataFrame:
    """Ekleme yalniz: defterde zaten olan anahtarlar atilir."""
    if eski is None or eski.empty:
        return aday
    var = set(map(tuple, eski[ANAHTAR].astype(str).to_numpy()))
    m = [tuple(r) not in var for r in aday[ANAHTAR].astype(str).to_numpy()]
    return aday[m]


def pencere_kapandi_mi(veri_sonu: dt.date) -> bool:
    return veri_sonu >= PENCERE_BITIS


def dosya_parmak_izi(yol) -> str:
    """SHA-256 - muhurlu defterin degismedigini puanlamadan once kanitlar."""
    import hashlib
    from pathlib import Path

    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


def muhur_dogrula(csv_yolu, muhur: dict) -> None:
    """docs/defter_2025_puanlama.md ile kaydedilen muhur (FAZ 9.2).
    Defter dosyasi muhurden sonra degistiyse puanlama REDDEDILIR."""
    iz = dosya_parmak_izi(csv_yolu)
    if iz != muhur["sha256"]:
        raise ValueError(f"defter muhurden sonra degismis: {iz[:12]} != "
                         f"{muhur['sha256'][:12]} - puanlama yapilmaz")


def puanla(defter: pd.DataFrame, sonuc: pd.DataFrame) -> pd.DataFrame:
    """sonuc: (player_id, comp, season, kademe, pencere_tam) - yeni bir TM
    anlik goruntusunden kurulmus tm_oyuncu_sezon. Pencere tam degilse NaN."""
    s = sonuc[["player_id", "comp", "season", "kademe", "pencere_tam"]]
    d = defter.merge(s, on=["player_id", "comp", "season"], how="left")
    tam = d.pencere_tam.fillna(False).astype(bool)
    d["gerceklesti"] = np.where(tam & d.kademe.notna(),
                                (d.kademe >= 3).astype(float), np.nan)
    return d
