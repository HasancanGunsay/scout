"""Esleştirilmis kontrol grubu: "top-K sonradan daha mi iyi yapti?" (FAZ 6.4).

NEDEN RASTGELE KONTROL YETMEZ
Top-K'yi rastgele oyuncularla kiyaslarsak "top-K daha cok oynadi" bulgusu
yalnizca "iyi oyuncular daha cok oynar" der - model degerinden bagimsiz. Dogru
soru: AYNI yasta, AYNI dakikada, AYNI fiyat bandinda, AYNI mevki-liglerdeki
siradan bir oyuncuya gore, modelin sectigi oyuncu sonradan daha mi iyi?

Eslestirme model degiskenlerinin EN GUCLULERINE (dakika, yas, deger) yapilir.
Bu bilincli olarak MUHAFAZAKAR: modelin en cok dayandigi seyleri sabitler,
geriye kalan fark oyun metriklerinin (skor, rating...) katkisidir.

TUZAKLAR
- Ayni oyuncu birden cok sezonda hedefte olabilir -> guven araligi OYUNCU
  bazinda kumelenmeli (satir bazli daraltir).
- Bir oyuncu kendi kontrolu olamaz (ayni player_id disarida).
- Sonuc eksikligi (NaN) 0 DEGIL: yalniz iki tarafta da gozlenenler
  karsilastirilir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260930)


def eslestir(tedavi: pd.DataFrame, havuz: pd.DataFrame, sayisal: list[str],
             kesin: list[str] | None = None, k: int = 5,
             asgari: int = 2) -> dict:
    """Her tedavi satiri icin en yakin k kontrolun index'leri.

    sayisal : mesafenin hesaplandigi (standartlastirilan) sutunlar
    kesin   : tam esitlik zorunlu sutunlar (mevki, sezon, kapsam ...)
    asgari  : bundan az aday varsa tedavi satiri ATLANIR (zorlama eslesme yok)
    """
    kesin = kesin or []
    X = havuz[sayisal].apply(pd.to_numeric, errors="coerce")
    ort, sd = X.mean(), X.std().replace(0, 1.0)

    def z(df):
        return ((df[sayisal].apply(pd.to_numeric, errors="coerce") - ort)
                / sd).fillna(0.0).to_numpy(float)

    Zh = z(havuz)
    Zt = z(tedavi)
    konum_h = {ix: i for i, ix in enumerate(havuz.index)}

    if kesin:
        gruplar = havuz.groupby(kesin).indices
    out: dict = {}
    for i, (ix, r) in enumerate(tedavi.iterrows()):
        if kesin:
            anahtar = tuple(r[c] for c in kesin)
            anahtar = anahtar[0] if len(kesin) == 1 else anahtar
            adaylar = gruplar.get(anahtar, np.array([], dtype=int))
        else:
            adaylar = np.arange(len(havuz))
        if len(adaylar) == 0:
            continue
        # kendisi ve ayni oyuncu kontrol olamaz
        ayni = (havuz.iloc[adaylar].player_id.to_numpy() == r["player_id"])
        adaylar = adaylar[~ayni]
        if len(adaylar) < asgari:
            continue
        d = np.linalg.norm(Zh[adaylar] - Zt[i], axis=1)
        sec = adaylar[np.argsort(d)[:k]]
        out[ix] = havuz.index[sec].to_numpy()
    return out


def fark_tablosu(tedavi: pd.DataFrame, havuz: pd.DataFrame, eslesme: dict,
                 sonuclar: list[str]) -> pd.DataFrame:
    """Tedavi degeri - kontrol ortalamasi. Iki tarafta da gozlenenler."""
    kayit = []
    for ix, kont in eslesme.items():
        r = {"player_id": tedavi.loc[ix, "player_id"], "n_kontrol": len(kont)}
        for s in sonuclar:
            t = tedavi.loc[ix, s]
            c = pd.to_numeric(havuz.loc[kont, s], errors="coerce").dropna()
            r[s] = (float(t) - float(c.mean())
                    if pd.notna(t) and len(c) > 0 else np.nan)
        kayit.append(r)
    return pd.DataFrame(kayit)


def kume_bootstrap(fark: pd.DataFrame, kol: str, B: int = 2000,
                   rng: np.random.Generator | None = None
                   ) -> tuple[float, float, float, int]:
    """Farkin ortalamasi ve %95 GA - OYUNCU bazinda kumelenmis.

    Ayni oyuncu birden cok sezonda tedavi grubunda olabilir; satirlari
    bagimsiz saymak GA'yi yapay daraltir.
    """
    rng = rng or RNG
    d = fark[["player_id", kol]].dropna()
    if len(d) < 10:
        return np.nan, np.nan, np.nan, len(d)
    gruplar = d.groupby("player_id")[kol].agg(["sum", "count"])
    toplam, adet = gruplar["sum"].to_numpy(), gruplar["count"].to_numpy()
    n = len(gruplar)
    ort = np.empty(B)
    for b in range(B):
        s = rng.integers(0, n, n)
        ort[b] = toplam[s].sum() / adet[s].sum()
    return (float(toplam.sum() / adet.sum()), float(np.percentile(ort, 2.5)),
            float(np.percentile(ort, 97.5)), len(d))
