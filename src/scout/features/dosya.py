"""Scout dosyasi MANTIGI: hangi risk yanacak, hangi kor nokta gosterilecek.

METIN URETMEZ. src/ dilden bagimsiz kaliyor; kullaniciya gorunen Turkce
cumleleri arayuz kuruyor (app/_dosya_metin.py). Bu ayrimi bir kez ihlal
ettim ve sayfada Turkce arayuzun ortasinda ASCII cumleler goruldu (§35.6);
ikinci kez ayni hataya dusmemek icin buradan METIN CIKMIYOR.

Doner: risk KODLARI ve kor nokta KODLARI. Esik ve kosullar burada,
kelimeler arayuzde.
"""

from __future__ import annotations

import pandas as pd

DAKIKA_GUVENSIZ = 900
KAPSAM_ESIGI = 0.60
YAS_SINIRDA = 22.5
ASGARI_SEZON = 2

# Risk kodlari - arayuz bunlari Turkce metne cevirir
KUCUK_ORNEKLEM = "kucuk_orneklem"
EKSIK_METRIK = "eksik_metrik"
LIG_BOZUK = "lig_bozuk"
SONUC_GORUNMEZ = "sonuc_gorunmez"
DEGER_YOK = "deger_yok"
TEK_SEZON = "tek_sezon"
YAS_SINIR = "yas_sinir"


def riskler(r: dict) -> list[tuple[str, dict]]:
    """(risk_kodu, baglam) listesi. Bos liste 'risk yok' DEMEK DEGIL."""
    out: list[tuple[str, dict]] = []

    dk = r.get("minutes")
    if pd.notna(dk) and dk < DAKIKA_GUVENSIZ:
        out.append((KUCUK_ORNEKLEM, {"dakika": int(dk),
                                     "esik": DAKIKA_GUVENSIZ}))

    kap = r.get("coverage")
    if pd.notna(kap) and kap < KAPSAM_ESIGI:
        out.append((EKSIK_METRIK, {"kapsam": float(kap)}))

    if r.get("lig_bozuk"):
        out.append((LIG_BOZUK, {}))

    # Sonucun kismen gorunmez olmasi (§38.4) - dusuk gorunurluklu ligler
    if r.get("kapsam") == "sicrama_only":
        out.append((SONUC_GORUNMEZ, {}))

    # Degerlemesi olmamak, modelde EN GUCLU degisken (deger_var +1,44).
    # Kalitesizlik degil GORUNMEZLIK anlamina gelebilir - §39.4.
    if r.get("deger_var") == 0:
        out.append((DEGER_YOK, {}))

    if int(r.get("n_sezon", 0) or 0) < ASGARI_SEZON:
        out.append((TEK_SEZON, {}))

    yas = r.get("yas")
    if pd.notna(yas) and yas >= YAS_SINIRDA:
        out.append((YAS_SINIR, {"yas": float(yas), "tepe": 25}))
    return out


# Verinin goremedigi seyler - mevkiye ozgu + genel. Kodlar arayuzde
# Turkce metne cevrilir.
GENEL_KOR = ["fizik", "karakter", "baski_alti", "sakatlik", "sozlesme"]
MEVKIYE_KOR = {
    "Goalkeeper": ["gk_ayak", "gk_ceza_sahasi", "gk_birebir"],
    "Defender": ["def_pozisyon", "def_hava", "def_pas_yonu"],
    "Midfielder": ["mf_alan_acma", "mf_pas_kiriciligi", "mf_tempo"],
    "Attacker": ["fw_bitiricilik", "fw_derinlik", "fw_sirti_donuk"],
}


def kor_noktalar(pos_group: str) -> list[str]:
    """Verinin goremedigi seylerin kodlari."""
    return MEVKIYE_KOR.get(pos_group, []) + GENEL_KOR


def katki_tablosu(contrib: dict, n: int = 6) -> pd.DataFrame:
    """Skoru en cok tasiyan metrikler. Waterfall'un ozeti."""
    if not contrib:
        return pd.DataFrame(columns=["metrik", "katki"])
    d = (pd.Series(contrib, dtype=float).sort_values(key=abs, ascending=False)
         .head(n).rename("katki").reset_index())
    d.columns = ["metrik", "katki"]
    return d


def kademe_kodu(kademe) -> int | None:
    """Sonuc kademesini int'e cevir, yoksa None."""
    if kademe is None or pd.isna(kademe):
        return None
    return int(kademe)
