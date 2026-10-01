"""Hesap defteri: sistem ne dedi, ne oldu (FAZ 5).

Bir scout ekibini EKIP yapan sey, iddiasinin kaydinin tutulmasidir. Su ana
kadar hicbir iddiamiz yazili degildi, dolayisiyla hicbiri yanlislanamiyordu.

=========================================================================
IKI BOLUM - VE ARALARINDAKI FARK KRITIK
=========================================================================
1) GECMISE DONUK DEGERLENDIRME (retrospektif)
   2022-2024 sezonlarinin sonucu ZATEN BILINIYOR. Bugun bu sezonlar icin
   bir kayit acmak "ileriye donuk tahmin" DEGILDIR - model bu veriyle
   egitildi (2022+2023) ya da uzerinde sinandi (2024).

   Bu bolum bir SICIL degil, bir KALIBRASYON RAPORUDUR. Ne ise yaradigi:
   modelin nerede yanildigini gostermek (hangi lig, hangi yas, hangi
   mevki). Basari iddiasi olarak kullanilamaz.

2) ILERIYE DONUK DEFTER (prospektif)
   Sonuc penceresi HENUZ KAPANMAMIS oyuncular icin bugun kaydedilen
   iddialar. Gercek sicil budur; sonuc geldiginde puanlanir.

   Su an bu bolum bos olacak ve BU NORMAL: elimizdeki en yeni sezon 2024
   ve onun 12 aylik penceresi kapandi. 2025 sezonu API'de acilinca
   (ucretsiz plan henuz vermiyor) dolmaya baslar.

Iki bolumu karistirmak, geriye donuk testi "sistem su kadar isabetli"
diye sunmak olurdu. Bu proje o hatayi bir kez yapti (§31) - tekrar
etmiyoruz.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

KAYNAK_OTOMATIK = "otomatik"
KAYNAK_KULLANICI = "kullanici"

# Defter satirinin sutunlari
SUTUNLAR = ["kayit_tarihi", "player_id", "league_id", "season", "player_name",
            "league_name", "kapsam", "model_olasilik", "emsal_oran",
            "lig_taban", "kaynak", "not", "tahmin_turu"]
# tahmin_turu (7.0): iddianin olasiligi NEREDEN geldi. FAZ 7.0 oncesi
# kayitlarda bos (NULL) = uretim modeli, 2022-24 icin ORNEKLEM ICI.


def iddia_kaydi(r: dict, tarih: dt.date | None = None,
                kaynak: str = KAYNAK_OTOMATIK, notu: str = "") -> dict:
    """Tek bir iddiayi defter satirina cevir."""
    return {
        "kayit_tarihi": (tarih or dt.date.today()).isoformat(),
        "player_id": int(r["player_id"]),
        "league_id": int(r["league_id"]),
        "season": int(r["season"]),
        "player_name": r.get("player_name"),
        "league_name": r.get("league_name"),
        "kapsam": r.get("kapsam"),
        "model_olasilik": float(r["model_olasilik"]),
        "emsal_oran": (float(r["oran"]) if pd.notna(r.get("oran")) else None),
        "lig_taban": (float(r["lig_taban"]) if pd.notna(r.get("lig_taban"))
                      else None),
        "kaynak": kaynak,
        "not": notu,
        "tahmin_turu": r.get("tahmin_turu"),
    }


def bolumle(defter: pd.DataFrame, sonuc: pd.DataFrame) -> dict:
    """Defteri retrospektif / prospektif diye ayir.

    Olcut: iddia KAYIT TARIHINDE sonuc penceresi kapanmis miydi?
    Kapanmissa retrospektif (sonuc zaten biliniyordu), kapanmamissa
    prospektif.
    """
    gerekli = ["player_id", "league_id", "season", "sezon_bitis", "kademe",
               "gozlem_ay"]
    if defter.empty or not set(gerekli) <= set(sonuc.columns):
        bos = defter.assign(**{c: pd.Series(dtype="object")
                               for c in gerekli if c not in defter.columns})
        return {"retrospektif": bos.iloc[:0], "prospektif": bos}
    d = defter.merge(sonuc[gerekli],
                     on=["player_id", "league_id", "season"], how="left")
    if d.empty:
        return {"retrospektif": d, "prospektif": d}

    kayit = pd.to_datetime(d.kayit_tarihi).dt.date
    bitis = pd.to_datetime(d.sezon_bitis).dt.date
    # kayit tarihinde 12 aylik pencere kapanmis miydi?
    kapali = pd.Series(
        [(k - b).days >= 365 if pd.notna(b) else False
         for k, b in zip(kayit, bitis)], index=d.index)
    return {"retrospektif": d[kapali], "prospektif": d[~kapali]}


def puanla(d: pd.DataFrame) -> pd.DataFrame:
    """Sonucu gelmis iddialara isabet/isabetsizlik ver."""
    if d.empty:
        return d.assign(gerceklesti=pd.Series(dtype=float))
    out = d.copy()
    out["gerceklesti"] = np.where(out.kademe.notna(),
                                  (out.kademe >= 3).astype(float), np.nan)
    return out


def disaridan_degerlendirme(tahmin: pd.DataFrame, sonuc: pd.DataFrame
                            ) -> pd.DataFrame:
    """Gecmise donuk kalibrasyon raporunun GIRDISI (7.0).

    FAZ 7.0'a kadar bu rapor defterdeki 2022-24 iddialarindan hesaplaniyordu;
    o iddialar ise sezonu egitimde GORMUS uretim modelinden geliyordu (ornek-
    lem ici - iyimser). Artik player_tahmin'deki DISARIDAN tahminlerden:
    modelin nerede yanildigini, cevabi bilmeyen modelle olcer.

    tahmin : player_tahmin (player_id, league_id, season, kapsam,
             model_olasilik, ...)
    sonuc  : player_outcome'dan en az kademe (+ istege bagli league_name)
    """
    anahtar = ["player_id", "league_id", "season"]
    s = sonuc.drop(columns=[c for c in ("kapsam",) if c in sonuc.columns])
    d = tahmin.merge(s, on=anahtar, how="inner")
    return puanla(d).dropna(subset=["gerceklesti"])


def eski_iddia_sayisi(defter: pd.DataFrame) -> int:
    """7.0 oncesi (orneklem ici uretim modeliyle) kaydedilmis iddia sayisi."""
    if "tahmin_turu" not in defter.columns:
        return len(defter)
    return int(defter.tahmin_turu.isna().sum())


def kalibrasyon(d: pd.DataFrame, kova: int = 5) -> pd.DataFrame:
    """Model ne dedi, ne oldu - kova kova."""
    x = d.dropna(subset=["model_olasilik", "gerceklesti"])
    if len(x) < kova * 5:
        return pd.DataFrame(columns=["kova", "n", "dedi", "oldu"])
    x = x.copy()
    x["kova"] = pd.qcut(x.model_olasilik, kova, duplicates="drop")
    g = (x.groupby("kova", observed=True)
          .agg(n=("gerceklesti", "size"), dedi=("model_olasilik", "mean"),
               oldu=("gerceklesti", "mean")).reset_index())
    g["kova"] = g.kova.astype(str)
    return g


def nerede_yaniliyor(d: pd.DataFrame, boyut: str, asgari: int = 25
                     ) -> pd.DataFrame:
    """Hangi dilimde model iyimser/kotumser?

    'sapma' = ortalama tahmin - gerceklesen oran. Pozitif = model FAZLA
    umutlu. Kucuk gruplar (asgari altinda) GOSTERILMEZ - ayni kural (§21).
    """
    x = d.dropna(subset=["model_olasilik", "gerceklesti"])
    if x.empty or boyut not in x.columns:
        return pd.DataFrame()
    g = (x.groupby(boyut)
          .agg(n=("gerceklesti", "size"), dedi=("model_olasilik", "mean"),
               oldu=("gerceklesti", "mean")).reset_index())
    g = g[g.n >= asgari]
    g["sapma"] = g.dedi - g.oldu
    return g.sort_values("sapma", ascending=False)


def kullanici_ortusmesi(shortlist: list[dict], d: pd.DataFrame) -> dict:
    """Kullanicinin secimleri sistemle ne kadar ortusuyor?

    Bir scout ekibinde asil ogrenme burada: sistem ve insan nerede
    ayrisiyor, ayrisinca kim hakli cikiyor.
    """
    if not shortlist or d.empty:
        return {"n": 0}
    anahtar = {(int(s.get("player_id", -1)), int(s.get("league_id", -1)),
                int(s.get("season", -1))) for s in shortlist}
    x = d.copy()
    x["secildi"] = [
        (int(a), int(b), int(c)) in anahtar
        for a, b, c in zip(x.player_id, x.league_id, x.season)]
    secilen = x[x.secildi]
    if secilen.empty:
        return {"n": 0}
    return {
        "n": int(len(secilen)),
        "ort_model": float(secilen.model_olasilik.mean()),
        "ort_model_geneli": float(x.model_olasilik.mean()),
        "gerceklesme": (float(secilen.gerceklesti.mean())
                        if secilen.gerceklesti.notna().any() else None),
        "gerceklesme_geneli": (float(x.gerceklesti.mean())
                               if x.gerceklesti.notna().any() else None),
    }
