"""Dis veri kaynaklarinin yollari ve tazeligi - tek dogruluk kaynagi.

GELISTIRME FAZ 9.1 (30 Eki 2026). Iki sorunu cozer:
1. Kullanilan Transfermarkt anlik goruntusu config/kaynaklar.yaml'da sabit;
   betikler kendi yolunu (sabit tarih ya da 'en yeni') secmez.
2. Kaynaklarin tazeligi olculur: TM veri seti Temmuz 2026'dan beri durmus,
   bunu fark eden bir kontrol yoktu.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AYAR = ROOT / "config" / "kaynaklar.yaml"
TM_DIZIN = ROOT / "data" / "raw" / "transfermarkt"
TM_DOSYA = "transfermarkt-datasets.duckdb"
SEZON_ERISIM = ROOT / "data" / "raw" / "season_access.json"


CANLI_DB = ROOT / "data" / "scout.duckdb"


def db_yolu() -> Path:
    """Analitik veritabani. SCOUT_DB ortam degiskeni verilirse o dosya.

    Atomik build (FAZ 9.5): gunluk zincir adimlari canli dosyaya degil bir
    KOPYAYA yazar (SCOUT_DB), denetim gecerse kopya canlinin yerine tasinir.
    Zincir yarida kalirsa canli veritabani hic degismemis olur.
    """
    import os

    v = os.environ.get("SCOUT_DB")
    return Path(v) if v else CANLI_DB


def ayarlar(yol: Path | None = None) -> dict:
    return yaml.safe_load((yol or AYAR).read_text(encoding="utf-8"))


def tm_anlik_goruntuler(dizin: Path | None = None) -> list[str]:
    """Diskteki TM anlik goruntuleri (tarih klasor adlari), eskiden yeniye."""
    d = dizin or TM_DIZIN
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if (p / TM_DOSYA).exists())


def tm_db_yolu(ayar: dict | None = None, dizin: Path | None = None) -> Path:
    """Zincirin KULLANDIGI TM anlik goruntusu (config/kaynaklar.yaml)."""
    a = (ayar or ayarlar())["transfermarkt"]["anlik_goruntu"]
    mevcut = tm_anlik_goruntuler(dizin)
    if not mevcut:
        raise FileNotFoundError(f"TM anlik goruntusu yok: {dizin or TM_DIZIN}")
    secilen = mevcut[-1] if a == "en_yeni" else str(a)
    if secilen not in mevcut:
        raise FileNotFoundError(
            f"config/kaynaklar.yaml TM anlik goruntusu '{secilen}' diskte yok; "
            f"mevcut: {mevcut}")
    return (dizin or TM_DIZIN) / secilen / TM_DOSYA


# ---------------------------------------------------------------- tazelik
@dataclass
class Bulgu:
    sonuc: str        # GECTI / UYARI / KALDI (audit.py ile ayni)
    kontrol: str
    detay: str


def _tarih(x) -> dt.date | None:
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x)[:10])


def tm_tarihleri(db: Path) -> dict:
    """Bir TM anlik goruntusundeki en yeni mac / katilim / deger tarihi."""
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        r = con.sql("""SELECT (SELECT max(date) FROM games),
                              (SELECT max(date) FROM appearances),
                              (SELECT max(date) FROM player_valuations)""").fetchone()
    finally:
        con.close()
    return {"mac": _tarih(r[0]), "katilim": _tarih(r[1]), "deger": _tarih(r[2])}


def tm_tazelik(kullanilan: str, mevcut: list[str], tarihler: dict,
               bugun: dt.date, bayat_gun: int, karar_tarihi: str) -> list[Bulgu]:
    """Saf fonksiyon (test edilir): TM kaynaginin durumu."""
    b: list[Bulgu] = []
    son_mac = tarihler.get("mac")
    if son_mac is None:
        return [Bulgu("KALDI", "TM: son mac tarihi okunamadi", kullanilan)]
    gecen = (bugun - son_mac).days
    if gecen > bayat_gun:
        b.append(Bulgu(
            "UYARI", "TM veri seti guncel degil",
            f"son mac {son_mac} ({gecen} gun once); veri seti Temmuz 2026'dan beri "
            f"guncellenmiyor - yedek sonuc kaynagi karari {karar_tarihi} (GELISTIRME 9.3)"))
    else:
        b.append(Bulgu("GECTI", "TM veri seti guncel", f"son mac {son_mac}"))
    deger = tarihler.get("deger")
    if deger is not None and son_mac is not None and (son_mac - deger).days > 60:
        b.append(Bulgu("UYARI", "TM piyasa degerleri maclardan geride",
                       f"son deger {deger}, son mac {son_mac}"))
    if mevcut and kullanilan != mevcut[-1]:
        b.append(Bulgu("UYARI", "Daha yeni TM anlik goruntusu bekliyor",
                       f"kullanilan {kullanilan}, diskte {mevcut[-1]} - gecis icin "
                       "kaynak_karsilastir.py + onay"))
    return b


def api_tazelik(sezon_erisim: dict | None, bugun: dt.date, sinama_gun: int,
                kota: dict | None, gunluk_kota: int) -> list[Bulgu]:
    """Saf fonksiyon (test edilir): API sezon penceresi ve kota."""
    b: list[Bulgu] = []
    if not sezon_erisim:
        b.append(Bulgu("UYARI", "API sezon erisimi hic sinanmamis",
                       "probe_season_access.py calistir"))
    else:
        yas = (bugun - _tarih(sezon_erisim["tarih"])).days
        acik = sezon_erisim.get("acik") or []
        if yas > sinama_gun + 5:
            b.append(Bulgu("UYARI", "API sezon sinamasi bayat",
                           f"son sinama {yas} gun once (beklenen <= {sinama_gun})"))
        else:
            b.append(Bulgu("GECTI", "API sezon sinamasi taze",
                           f"{sezon_erisim['tarih']}: acik={acik or 'yok (2022-24)'}"))
        if acik:
            b.append(Bulgu("UYARI", "API'de YENI SEZON ACILDI",
                           f"{acik} - config/leagues.yaml'a eklenebilir"))
    if kota and _tarih(kota.get("date")) == bugun:
        b.append(Bulgu("GECTI", "API kotasi bugun",
                       f"{kota.get('used', 0)}/{gunluk_kota} kullanildi"))
    return b


def tum_bulgular(bugun: dt.date | None = None) -> list[Bulgu]:
    """Gercek dosyalardan: audit.py ve Veri sayfasi bunu cagirir."""
    bugun = bugun or dt.date.today()
    a = ayarlar()
    tm = a["transfermarkt"]
    b: list[Bulgu] = []
    try:
        yol = tm_db_yolu(a)
        b += tm_tazelik(yol.parent.name, tm_anlik_goruntuler(), tm_tarihleri(yol),
                        bugun, tm["bayat_gun"], tm["karar_tarihi"])
    except FileNotFoundError as e:
        b.append(Bulgu("KALDI", "TM anlik goruntusu bulunamadi", str(e)))
    erisim = (json.loads(SEZON_ERISIM.read_text(encoding="utf-8"))
              if SEZON_ERISIM.exists() else None)
    kota_dosya = ROOT / "data" / "raw" / "apifootball" / "_quota.json"
    kota = json.loads(kota_dosya.read_text(encoding="utf-8")) if kota_dosya.exists() else None
    api = a["api_football"]
    b += api_tazelik(erisim, bugun, api["sezon_sinama_gun"], kota, api["gunluk_kota"])
    return b
