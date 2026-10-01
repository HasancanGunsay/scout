"""Takip listesi - kullanicinin izledigi oyuncular (FAZ 8.2).

KISI ANAHTARI: "tm:<tm_id>" - Transfermarkt kimligi iki havuzu birlestirir:
API 2024 havuzundan eklenen oyuncu ile TM 2025/26 havuzundaki AYNI kisi
tek kayittir. TM eslesmesi yoksa "api:<api_player_id>".

IKI DOSYA
  durum  data/takip/takip.json          guncel liste; atomik yeniden yazilir
  gunluk data/defter/takip_gunlugu.csv  APPEND-ONLY olay kaydi

Gunluk hesap defterinin "senin secimlerin" bolumunu besler. Bir secimin
degeri NE ZAMAN ve NE BILINEREK yapildigindan gelir:
  sonuc_gorunur = True   oyuncunun 12 aylik sonuc penceresi secim aninda
                         KAPALIYDI (API 2022-24; sonuc ekranda da var).
                         Goz testi DEGIL, yalniz dokum.
  sonuc_gorunur = False  sonuc henuz yok (TM 2025/26, pencere 2027-06-15).
                         Gercek sinav budur.
Silinen oyuncu gunlukten SILINMEZ: "biraktim, sonra yildizlasti" de bir
kayittir.

Bu modul ASCII kod yazar (durum: izle/ilgilen/oncelikli/birakildi);
Turkce etiketler app/ tarafinda.

SCOUT_TAKIP_DIZIN ortam degiskeni verilirse iki dosya da oraya yazilir
(testler ve deneme sunuculari kullanicinin listesini kirletmesin).
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DURUMLAR = ["izle", "ilgilen", "oncelikli", "birakildi"]
VARSAYILAN_DURUM = "izle"
OLAYLAR = ["ekle", "durum", "not", "rapor", "sil"]
GUNLUK_SUTUNLARI = ["zaman", "kisi", "ad", "olay", "durum", "kaynak",
                    "anahtar", "model_olasilik", "havuz_puani", "deger",
                    "sonuc_gorunur", "metin"]
SURUM = 1


def yollar() -> tuple[Path, Path]:
    """(durum dosyasi, gunluk). Ortam degiskeni HER CAGRIDA okunur."""
    d = os.environ.get("SCOUT_TAKIP_DIZIN")
    if d:
        return Path(d) / "takip.json", Path(d) / "takip_gunlugu.csv"
    return (ROOT / "data" / "takip" / "takip.json",
            ROOT / "data" / "defter" / "takip_gunlugu.csv")


def kisi_anahtari(tm_id=None, api_id=None) -> str:
    if tm_id is not None and not pd.isna(tm_id):
        return f"tm:{int(tm_id)}"
    if api_id is not None and not pd.isna(api_id):
        return f"api:{int(api_id)}"
    raise ValueError("kisi icin tm_id ya da api_id gerekli")


def _simdi() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _bos() -> dict:
    return {"surum": SURUM, "oyuncular": {}}


def yukle(yol: Path | None = None) -> dict:
    yol = yol or yollar()[0]
    if not yol.exists():
        return _bos()
    try:
        d = json.loads(yol.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # Bozuk dosyayi sessizce bos liste saymak, ilk kayitta kullanicinin
        # listesini SILER. Yuksek sesle dur.
        raise RuntimeError(f"takip listesi okunamadi: {yol} ({exc})") from exc
    d.setdefault("oyuncular", {})
    return d


def _yaz(durum: dict, yol: Path) -> None:
    """Atomik: yarim yazilmis dosya listeyi bozmasin."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=yol.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(durum, f, ensure_ascii=False, indent=1)
        os.replace(gecici, yol)
    except BaseException:
        Path(gecici).unlink(missing_ok=True)
        raise


def _gunluge(olay: dict, yol: Path) -> None:
    """Yalniz EKLER. Var olan satira dokunulmaz."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    yeni = not yol.exists()
    with yol.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GUNLUK_SUTUNLARI)
        if yeni:
            w.writeheader()
        w.writerow({k: olay.get(k, "") for k in GUNLUK_SUTUNLARI})


def _olay(kayit: dict, olay: str, zaman: str, metin: str = "") -> dict:
    ilk = kayit.get("ilk", {})
    return {"zaman": zaman, "kisi": kayit["kisi"], "ad": kayit["ad"],
            "olay": olay, "durum": kayit["durum"],
            "kaynak": kayit.get("kaynak", ""),
            "anahtar": kayit.get("anahtar", ""),
            "model_olasilik": ilk.get("model_olasilik", ""),
            "havuz_puani": ilk.get("havuz_puani", ""),
            "deger": ilk.get("deger", ""),
            "sonuc_gorunur": ilk.get("sonuc_gorunur", ""),
            "metin": metin}


def _sayi(v):
    return None if v is None or pd.isna(v) else float(v)


def takipte(durum: dict, kisi: str) -> bool:
    return kisi in durum["oyuncular"]


def ekle(kisi: str, ad: str, *, kaynak: str, anahtar: str,
         sonuc_gorunur: bool, model_olasilik=None, havuz_puani=None,
         deger=None, api: tuple[int, int, int] | None = None,
         zaman: str | None = None, yol: Path | None = None,
         gunluk: Path | None = None) -> dict:
    """Takibe al. Zaten takipteyse dokunmaz (eklenme ani ilk secimdir).

    ilk = secim anindaki sistem iddiasi; sonradan GUNCELLENMEZ.
    api = (player_id, league_id, season) - API satirindan eklendiyse.
    """
    vy, vg = yollar()
    yol, gunluk = yol or vy, gunluk or vg
    durum = yukle(yol)
    if takipte(durum, kisi):
        return durum["oyuncular"][kisi]
    zaman = zaman or _simdi()
    kayit = {
        "kisi": kisi, "ad": ad, "eklendi": zaman,
        "durum": VARSAYILAN_DURUM, "kaynak": kaynak, "anahtar": anahtar,
        "api": list(api) if api else None,
        "ilk": {"model_olasilik": _sayi(model_olasilik),
                "havuz_puani": _sayi(havuz_puani), "deger": _sayi(deger),
                "sonuc_gorunur": bool(sonuc_gorunur)},
        "notlar": [], "raporlar": [],
    }
    durum["oyuncular"][kisi] = kayit
    _yaz(durum, yol)
    _gunluge(_olay(kayit, "ekle", zaman), gunluk)
    return kayit


def _degistir(kisi: str, yol: Path | None, gunluk: Path | None):
    vy, vg = yollar()
    yol, gunluk = yol or vy, gunluk or vg
    durum = yukle(yol)
    if not takipte(durum, kisi):
        raise KeyError(f"takipte degil: {kisi}")
    return durum, durum["oyuncular"][kisi], yol, gunluk


def durum_degistir(kisi: str, yeni: str, *, zaman: str | None = None,
                   yol: Path | None = None, gunluk: Path | None = None) -> None:
    if yeni not in DURUMLAR:
        raise ValueError(f"bilinmeyen durum: {yeni}")
    durum, kayit, yol, gunluk = _degistir(kisi, yol, gunluk)
    if kayit["durum"] == yeni:
        return
    kayit["durum"] = yeni
    _yaz(durum, yol)
    _gunluge(_olay(kayit, "durum", zaman or _simdi()), gunluk)


def not_ekle(kisi: str, metin: str, *, zaman: str | None = None,
             yol: Path | None = None, gunluk: Path | None = None) -> None:
    metin = metin.strip()
    if not metin:
        raise ValueError("bos not")
    durum, kayit, yol, gunluk = _degistir(kisi, yol, gunluk)
    zaman = zaman or _simdi()
    kayit["notlar"].append({"zaman": zaman, "metin": metin})
    _yaz(durum, yol)
    _gunluge(_olay(kayit, "not", zaman, metin), gunluk)


def rapor_ekle(kisi: str, rapor: dict, *, zaman: str | None = None,
               yol: Path | None = None, gunluk: Path | None = None) -> None:
    """Yapilandirilmis goz testi raporu (1-5 puanlar, karar, notlar)."""
    durum, kayit, yol, gunluk = _degistir(kisi, yol, gunluk)
    zaman = zaman or _simdi()
    kayit["raporlar"].append({"zaman": zaman, **rapor})
    _yaz(durum, yol)
    _gunluge(_olay(kayit, "rapor", zaman, str(rapor.get("karar", ""))), gunluk)


def sil(kisi: str, *, zaman: str | None = None, yol: Path | None = None,
        gunluk: Path | None = None) -> None:
    """Listeden cikar. Gunlukte iz kalir; notlar gunlukte de durur."""
    durum, kayit, yol, gunluk = _degistir(kisi, yol, gunluk)
    del durum["oyuncular"][kisi]
    _yaz(durum, yol)
    _gunluge(_olay(kayit, "sil", zaman or _simdi()), gunluk)


def gunluk_oku(gunluk: Path | None = None) -> pd.DataFrame:
    gunluk = gunluk or yollar()[1]
    if not gunluk.exists():
        return pd.DataFrame(columns=GUNLUK_SUTUNLARI)
    return pd.read_csv(gunluk, dtype={"anahtar": str, "metin": str},
                       keep_default_na=False, na_values=[""])


def api_secimleri(durum: dict) -> list[dict]:
    """API satirindan eklenenler, defter.kullanici_ortusmesi bicimiyle."""
    return [{"player_id": k["api"][0], "league_id": k["api"][1],
             "season": k["api"][2], "player_name": k["ad"]}
            for k in durum["oyuncular"].values() if k.get("api")]
