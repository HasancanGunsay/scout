"""Atomik build ve build kaydi (FAZ 9.5).

ESKI DURUM (eski P1-2, Temmuz 2026'dan beri acik): gunluk zincir adimlari
dogrudan canli veritabanina yaziyordu. build_features basarili olup
build_scores cokerse player_features yeni, player_scores eski kaliyordu;
arayuz tutarsiz veriyi belli etmeden gosteriyordu.

YENI DURUM: zincir canlinin KOPYASINA yazar (SCOUT_DB). Sonunda:
- zincir tamam VE denetimde canliya gore YENI bir KALDI yok -> kopya canlinin
  yerine tasinir (os.replace, ayni diskte atomik); eskisi .prev olarak kalir.
- degilse canli hic degismez; kopya incelemek icin .red olarak saklanir.
Her karar build_kaydi.csv'ye (append-only) yazilir.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

KAYIT_ALANLARI = ["build_id", "baslangic", "bitis", "zincir_ok", "kirilan_adim",
                  "tm_anlik_goruntu", "denetim_once_kaldi", "denetim_sonra_kaldi",
                  "yeni_kaldi", "gecis", "neden"]


@dataclass
class Karar:
    gecis: bool
    neden: str
    yeni_kaldi: list[str] = field(default_factory=list)


def karar(zincir_ok: bool, once_kaldi: list[str] | None,
          sonra_kaldi: list[str] | None) -> Karar:
    """Saf fonksiyon: kopya canlinin yerine gecsin mi?

    Kural: zincir tamamlanmis olmali VE denetim, canli veritabaninda zaten
    kalmayan hicbir kontrolde KALMAMALI. Bilinen (canlida da kalan)
    kontroller gecisi engellemez - yoksa 5 bilinen saglayici eksigi her
    gunu bloklardi.
    """
    if not zincir_ok:
        return Karar(False, "zincir yarida kaldi")
    if sonra_kaldi is None:
        return Karar(False, "denetim calismadi (ozet yok)")
    once = set(once_kaldi or [])
    yeni = sorted(set(sonra_kaldi) - once)
    if yeni:
        return Karar(False, f"denetimde yeni KALDI: {len(yeni)}", yeni)
    return Karar(True, "zincir tamam, yeni KALDI yok")


def ozet_oku(yol: Path | None) -> list[str] | None:
    if yol is None or not Path(yol).exists():
        return None
    return json.loads(Path(yol).read_text(encoding="utf-8"))["kaldi_kontroller"]


def _checkpoint(db: Path) -> None:
    """WAL dosyasi kalmissa ana dosyaya yaz (dosya tasinmadan once)."""
    if Path(str(db) + ".wal").exists():
        con = duckdb.connect(str(db))
        con.execute("CHECKPOINT")
        con.close()


def hazirla(canli: Path, kopya: Path) -> None:
    """Canlinin kopyasini olustur: zincir buna yazar."""
    _checkpoint(canli)
    for ek in ("", ".wal"):
        p = Path(str(kopya) + ek)
        if p.exists():
            p.unlink()
    shutil.copy2(canli, kopya)


def uygula(k: Karar, canli: Path, kopya: Path) -> None:
    """Karari uygula. Gecis: canli -> .prev (kopya), kopya -> canli (atomik)."""
    if not kopya.exists():
        return
    _checkpoint(kopya)
    if k.gecis:
        shutil.copy2(canli, canli.with_suffix(".prev.duckdb"))
        _tasi(kopya, canli)
    else:
        _tasi(kopya, canli.with_suffix(".red.duckdb"))


def _tasi(kaynak: Path, hedef: Path, deneme: int = 6, bekle: float = 2.0) -> None:
    """os.replace + yeniden deneme. Windows'ta arayuz o an canliyi kopyaliyorsa
    (app/_shared._con, saniyenin altinda) hedef kisa sure kilitli olabilir."""
    import time

    for i in range(deneme):
        try:
            os.replace(kaynak, hedef)
            return
        except PermissionError:
            if i == deneme - 1:
                raise
            time.sleep(bekle)


def kayit_yaz(kayit_csv: Path, satir: dict) -> None:
    yeni = not kayit_csv.exists()
    with kayit_csv.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=KAYIT_ALANLARI)
        if yeni:
            w.writeheader()
        w.writerow({k: satir.get(k, "") for k in KAYIT_ALANLARI})


def satir(build_id: str, baslangic: str, zincir_ok: bool, kirilan: str,
          tm: str, once: list[str] | None, sonra: list[str] | None, k: Karar) -> dict:
    return {
        "build_id": build_id, "baslangic": baslangic,
        "bitis": dt.datetime.now().isoformat(timespec="seconds"),
        "zincir_ok": zincir_ok, "kirilan_adim": kirilan, "tm_anlik_goruntu": tm,
        "denetim_once_kaldi": "" if once is None else len(once),
        "denetim_sonra_kaldi": "" if sonra is None else len(sonra),
        "yeni_kaldi": " | ".join(k.yeni_kaldi), "gecis": k.gecis, "neden": k.neden,
    }

