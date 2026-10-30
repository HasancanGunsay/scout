"""Kisi kaydi: her kaynagin oyuncu kimligini TEK kisiye baglar (FAZ 9.4).

Bugunku `player_links` API<->TM ikilisinin N kaynaga genellemesi.

KURALLAR (mevcut sistemle birebir ayni - takip.kisi_anahtari):
- Omurga kaynagin (TM) her kimligi bir kisidir: 'tm:<id>'.
- Diger kaynaklarin kimligi, adaptorun eslesme kurali bir kisiye bagliyorsa
  o kisidir (API icin: YALNIZ kabul edilmis eslesme, §60).
- Baglanmayan kimlik kendi basina kisidir: '<kaynak>:<id>' (or. 'api:123').
- Bir kaynak kimligi tam olarak BIR kisiye baglanir; iki ayri TM kimligi
  ayni kisiye baglanmaz (denetim + test).
"""
from __future__ import annotations

import pandas as pd

from scout.sources import SEMA, birlesik_sql


def kisi_kaynak_sql(kaynaklar: list) -> str:
    """(kisi_id, kaynak, kaynak_id, guven, yontem) - kaynak_kimlik tablosu uzerinden."""
    eslesmeler = []
    for k in kaynaklar:
        e = k.eslesme_sql() if hasattr(k, "eslesme_sql") else None
        if e:
            eslesmeler.append(f"SELECT '{k.ad}' AS kaynak, * FROM ({e})")
    eslesme = " UNION ALL ".join(eslesmeler) if eslesmeler else (
        "SELECT CAST(NULL AS VARCHAR) kaynak, CAST(NULL AS VARCHAR) kaynak_id, "
        "CAST(NULL AS VARCHAR) kisi_id, CAST(NULL AS VARCHAR) guven, "
        "CAST(NULL AS VARCHAR) yontem WHERE FALSE")
    omurga = [f"'{k.ad}'" for k in kaynaklar if getattr(k, "omurga", False)]
    omurga_kosul = f"k.kaynak IN ({', '.join(omurga)})" if omurga else "FALSE"
    return f"""
        WITH e AS ({eslesme})
        SELECT CASE WHEN {omurga_kosul} THEN k.kaynak || ':' || k.kaynak_id
                    WHEN e.kisi_id IS NOT NULL THEN e.kisi_id
                    ELSE k.kaynak || ':' || k.kaynak_id END AS kisi_id,
               k.kaynak, k.kaynak_id,
               CASE WHEN {omurga_kosul} THEN 'kaynak'
                    ELSE coalesce(e.guven, '-') END AS guven,
               CASE WHEN {omurga_kosul} THEN 'omurga'
                    ELSE coalesce(e.yontem, 'tekil') END AS yontem
        FROM kaynak_kimlik k
        LEFT JOIN e ON e.kaynak = k.kaynak AND e.kaynak_id = k.kaynak_id"""


def kisi_sql(kaynaklar: list) -> str:
    """Kisi basina tek satir: nitelikler kaynak onceligine gore (liste sirasi
    degil - omurga once, sonra adaptor listesi sirasi)."""
    sira = sorted(range(len(kaynaklar)),
                  key=lambda i: (not getattr(kaynaklar[i], "omurga", False), i))
    oncelik = " ".join(f"WHEN '{kaynaklar[i].ad}' THEN {n}" for n, i in enumerate(sira))
    return f"""
        WITH x AS (
            SELECT kk.kisi_id, kk.kaynak, k.ad, k.dogum_tarihi, k.uyruk,
                   CASE kk.kaynak {oncelik} ELSE 99 END AS oncelik
            FROM kisi_kaynak kk JOIN kaynak_kimlik k USING (kaynak, kaynak_id))
        SELECT kisi_id,
               arg_min(ad, oncelik) AS ad,
               arg_min(dogum_tarihi, oncelik) AS dogum_tarihi,
               arg_min(uyruk, oncelik) AS uyruk,
               count(DISTINCT kaynak) AS kaynak_sayisi,
               string_agg(DISTINCT kaynak, ',' ORDER BY kaynak) AS kaynaklar
        FROM x GROUP BY kisi_id"""


def kur(con, kaynaklar: list) -> dict:
    """Standart tablolari ve kisi kaydini olustur. Doner: tablo -> satir sayisi."""
    sayilar = {}
    for tablo in SEMA:
        con.execute(f"CREATE OR REPLACE TABLE {tablo} AS {birlesik_sql(kaynaklar, tablo)}")
        sayilar[tablo] = con.execute(f"SELECT count(*) FROM {tablo}").fetchone()[0]
    con.execute(f"CREATE OR REPLACE TABLE kisi_kaynak AS {kisi_kaynak_sql(kaynaklar)}")
    con.execute(f"CREATE OR REPLACE TABLE kisi AS {kisi_sql(kaynaklar)}")
    for t in ("kisi_kaynak", "kisi"):
        sayilar[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    return sayilar


def denetim(con) -> list[tuple[str, bool, str]]:
    """(kontrol, gecti_mi, detay) - audit.py ve testler kullanir."""
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    out = []
    n = q("SELECT count(*) - count(DISTINCT (kaynak, kaynak_id)) FROM kisi_kaynak")
    out.append(("kisi kaydi: her kaynak kimligi tek kisiye bagli", n == 0, f"{n} yinelenen"))
    n = q("""SELECT count(*) FROM (SELECT kisi_id FROM kisi_kaynak WHERE kaynak = 'tm'
             GROUP BY 1 HAVING count(*) > 1)""")
    out.append(("kisi kaydi: iki TM kimligi ayni kisiye baglanmamis", n == 0, f"{n} kisi"))
    n = q("""SELECT count(*) FROM kisi_kaynak kk
             LEFT JOIN kisi_kaynak t ON t.kaynak = 'tm' AND t.kisi_id = kk.kisi_id
             WHERE kk.kisi_id LIKE 'tm:%' AND t.kisi_id IS NULL""")
    out.append(("kisi kaydi: 'tm:' kisilerinin TM kimligi var", n == 0,
                f"{n} bagli kimlik TM'de yok"))
    n = q("SELECT count(*) - (SELECT count(DISTINCT kaynak_id) FROM kaynak_kimlik "
          "WHERE kaynak = 'api') FROM kisi_kaynak WHERE kaynak = 'api'")
    out.append(("kisi kaydi: her API oyuncusu kayitta", n == 0, f"fark {n}"))
    return out


def ozet(con) -> pd.DataFrame:
    return con.execute("""SELECT kaynak, yontem, guven, count(*) n FROM kisi_kaynak
                          GROUP BY ALL ORDER BY ALL""").df()
