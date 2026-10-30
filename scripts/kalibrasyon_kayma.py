"""FAZ 7.3: kalibrator guncelleme kurali - TM 2013-2024 uzerinde.

    python scripts/kalibrasyon_kayma.py            # gelistirme: hedef 2015-2017
    python scripts/kalibrasyon_kayma.py --test     # + sinama: hedef 2022-2024

ILERI-ZINCIR TAHMIN: her sezon t (2014-2024) icin model ('tam', §53)
YALNIZ 2013..t-1 ile egitilir ve t'yi tahmin eder - uretimdeki durum.
Kurallar (zaman_kalibrasyon.py) hedef sezon s icin yalniz s'den onceki
ileri-zincir tahminleri kullanir.

KARAR KURALI (calistirmadan ONCE yazildi):
  Gelistirme hedefleri 2015, 2016, 2017 (2018-2021 muhurlu testti; acildi
  ama 7.3'te SECIM icin kullanilmaz - §53.6). Olcu: havuzlanmis log-kayip.
  En dusuk log-kayipli kural, 'tum_gecmis'e karsi satir bazinda log-kayip
  farkinin oyuncu-kumeli %95 GA'si sifirin ALTINDAYSA secilir; degilse
  'tum_gecmis' kalir (mevcut yaklasimin zaman karsiligi).
  Sinama hedefleri 2022, 2023, 2024 (TM satirlari): secilen kural ham ve
  tum_gecmis'e karsi raporlanir; karari degistirmez.

ACIK KAYIT: 2022-24'un TM taban oranlari (%55-56) 7.1 saglamasinda
basildi (§52.4). Kural gelistirmede, onceden yazili olcuyle secildigi icin
bu bilgi secime girmiyor; yine de not edildi.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402

from scout.model.egitim import _hazirla, egit  # noqa: E402
from scout.model.kalibrasyon import brier, ece, logloss  # noqa: E402
from scout.model.tm_model import VARYANTLAR, hazirla  # noqa: E402
from scout.model.zaman_kalibrasyon import KURALLAR, kalibre  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
MODEL = "tam"
GEL_HEDEF = (2015, 2016, 2017)
TEST_HEDEF = (2022, 2023, 2024)
EPS = 1e-6
RNG = np.random.default_rng(11)


def ileri_zincir(d: pd.DataFrame, sezonlar) -> pd.DataFrame:
    kol = VARYANTLAR[MODEL]
    out = []
    for t in sezonlar:
        tr = d[(d.season >= 2013) & (d.season < t)]
        te = d[d.season == t].copy()
        _, te["p"] = egit(_hazirla(tr, kol), tr.y.to_numpy(),
                          _hazirla(te, kol, ref=tr))
        out.append(te[["player_id", "season", "comp", "p", "y"]])
    return pd.concat(out, ignore_index=True)


def _satir_kayip(p, y):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def degerlendir(fz: pd.DataFrame, hedefler, baslik: str) -> pd.DataFrame:
    satir, kal = [], []
    for s in hedefler:
        h = fz[fz.season == s].copy()
        for k in KURALLAR:
            h[k] = kalibre(fz, h.p, s, k)
        kal.append(h)
        for k in KURALLAR:
            satir.append(dict(sezon=s, kural=k, ece=ece(h[k], h.y),
                              brier=brier(h[k], h.y), logloss=logloss(h[k], h.y),
                              sapma=float(h[k].mean() - h.y.mean())))
    t = pd.DataFrame(satir)
    hep = pd.concat(kal, ignore_index=True)
    print(f"\n{'=' * 84}\n{baslik}  (n={len(hep):,})\n{'=' * 84}")
    print(t.pivot(index="kural", columns="sezon", values="sapma").round(3)
           .add_prefix("sapma_").to_string())
    ozet = pd.DataFrame({
        k: dict(ece_ort=t[t.kural == k].ece.mean(),
                logloss=logloss(hep[k], hep.y), brier=brier(hep[k], hep.y),
                abs_sapma_ort=t[t.kural == k].sapma.abs().mean())
        for k in KURALLAR}).T
    print("\n" + ozet.round(4).to_string())
    return hep


def kume_fark(hep: pd.DataFrame, a: str, b: str, B: int = 1000):
    fark = pd.Series(_satir_kayip(hep[a], hep.y) - _satir_kayip(hep[b], hep.y))
    gr = fark.groupby(hep.player_id.to_numpy())
    top, say = gr.sum().to_numpy(), gr.size().to_numpy()
    n = len(top)
    bs = []
    for _ in range(B):
        i = RNG.integers(0, n, n)
        bs.append(top[i].sum() / say[i].sum())
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return float(fark.mean()), float(lo), float(hi)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    d = hazirla(con.sql("SELECT * FROM tm_oyuncu_sezon").df())
    con.close()
    d = d[d.y.notna() & (d.season >= 2013)].reset_index(drop=True)
    son = max(TEST_HEDEF) if a.test else max(GEL_HEDEF)
    fz = ileri_zincir(d, range(2014, son + 1))
    print(f"[in] ileri-zincir tahmin 2014-{son}: {len(fz):,} satir")

    hep = degerlendir(fz, GEL_HEDEF, "GELISTIRME - hedef 2015-2017")
    ll = {k: logloss(hep[k], hep.y) for k in KURALLAR}
    en_iyi = min(ll, key=ll.get)
    print(f"\n  en dusuk log-kayip: {en_iyi}")
    secim = "tum_gecmis"
    if en_iyi != "tum_gecmis":
        o, lo, hi = kume_fark(hep, en_iyi, "tum_gecmis")
        print(f"  {en_iyi} - tum_gecmis log-kayip {o:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        if hi < 0:
            secim = en_iyi
    print(f"  >>> SECILEN KURAL: {secim}")

    if a.test:
        th = degerlendir(fz, TEST_HEDEF, "SINAMA - hedef 2022-2024 (TM)")
        for b in ("ham", "tum_gecmis"):
            if b != secim:
                o, lo, hi = kume_fark(th, secim, b)
                print(f"  {secim} - {b} log-kayip {o:+.4f} [{lo:+.4f}, {hi:+.4f}]"
                      + ("*" if hi < 0 or lo > 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
