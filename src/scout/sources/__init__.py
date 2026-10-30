"""Kaynak katmani (GELISTIRME FAZ 9.4).

NEDEN
API-Football ve Transfermarkt ozellik/sonuc kodunun icine gomuluydu: yeni bir
lig ya da kaynak (FAZ 11 TFF) eklemek her seferinde cekirdege dokunmayi
gerektiriyordu. Bu paket her kaynagi AYNI standart tablolara cevirir; kisi
kaydi (scout.resolve.kisi) kaynak kimliklerini tek kisiye baglar.

SOZLESME
Her adaptor `Kaynak` arayuzunu uygular: standart tablo adi -> DuckDB SQL
(analitik veritabani uzerinde). Kaynagin vermedigi tablo icin None.
Her satirda `kaynak` ve `kaynak_id` (VARCHAR) zorunlu; `kaynak_surum` hangi
anlik goruntuden geldigini soyler.

EKLEMELI: mevcut hesaplar (ozellik, sonuc, model) bu tablolari OKUMAZ; birebir
ayni kalir. Ilk gercek kullanici TFF adaptoru (FAZ 11) olacak.
"""
from __future__ import annotations

from typing import Protocol

# Standart tablolar: ad -> (sutun, DuckDB tipi). Sira sabit (UNION icin).
SEMA: dict[str, list[tuple[str, str]]] = {
    "kaynak_kimlik": [
        ("kaynak", "VARCHAR"), ("kaynak_id", "VARCHAR"), ("kaynak_surum", "VARCHAR"),
        ("ad", "VARCHAR"), ("dogum_tarihi", "DATE"), ("uyruk", "VARCHAR"),
        ("boy_cm", "DOUBLE"), ("ayak", "VARCHAR"), ("mevki", "VARCHAR"),
    ],
    "kaynak_mac_katilim": [
        ("kaynak", "VARCHAR"), ("kaynak_id", "VARCHAR"), ("kaynak_surum", "VARCHAR"),
        ("mac_id", "VARCHAR"), ("tarih", "DATE"), ("lig", "VARCHAR"),
        ("kulup_id", "VARCHAR"), ("dakika", "DOUBLE"), ("gol", "DOUBLE"),
        ("asist", "DOUBLE"), ("sari", "DOUBLE"), ("kirmizi", "DOUBLE"),
    ],
    "kaynak_oyuncu_sezon": [
        ("kaynak", "VARCHAR"), ("kaynak_id", "VARCHAR"), ("kaynak_surum", "VARCHAR"),
        ("lig", "VARCHAR"), ("sezon", "INTEGER"), ("kulup_id", "VARCHAR"),
        ("mac", "DOUBLE"), ("ilk11", "DOUBLE"), ("dakika", "DOUBLE"),
        ("gol", "DOUBLE"), ("asist", "DOUBLE"),
    ],
    "kaynak_deger": [
        ("kaynak", "VARCHAR"), ("kaynak_id", "VARCHAR"), ("kaynak_surum", "VARCHAR"),
        ("tarih", "DATE"), ("deger_eur", "DOUBLE"),
    ],
    "kaynak_sozlesme": [
        ("kaynak", "VARCHAR"), ("kaynak_id", "VARCHAR"), ("kaynak_surum", "VARCHAR"),
        ("kulup", "VARCHAR"), ("bitis", "DATE"),
    ],
}


class Kaynak(Protocol):
    ad: str            # 'api', 'tm', 'tff'... (kisi anahtarinin oneki)
    surum: str         # anlik goruntu / plan bilgisi

    def sql(self, tablo: str) -> str | None:
        """Standart tablo icin SELECT (SEMA sirasiyla) ya da None."""


def sutunlar(tablo: str) -> list[str]:
    return [c for c, _ in SEMA[tablo]]


def bos_sql(tablo: str) -> str:
    """Tipli, bos bir SELECT - hic kaynak vermediginde tablo yine olusur."""
    return "SELECT " + ", ".join(f"CAST(NULL AS {t}) AS {c}" for c, t in SEMA[tablo]) \
        + " WHERE FALSE"


def birlesik_sql(kaynaklar: list[Kaynak], tablo: str) -> str:
    """Tum kaynaklarin standart tablosu - sutunlar SEMA'ya gore tiplenir."""
    parcalar = []
    for k in kaynaklar:
        s = k.sql(tablo)
        if s:
            # Adaptor SELECT'i SEMA SIRASIYLA dondurur; adlar sira ile baglanir
            # (adaptorun sutun takma adi vermesi gerekmez).
            ad_listesi = ", ".join(sutunlar(tablo))
            secim = ", ".join(f"CAST({c} AS {t}) AS {c}" for c, t in SEMA[tablo])
            parcalar.append(f"SELECT {secim} FROM ({s}) AS _k({ad_listesi})")
    return " UNION ALL ".join(parcalar) if parcalar else bos_sql(tablo)
