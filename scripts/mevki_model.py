"""FAZ 6.3a: mevki mevki model secimi - KANITA DAYALI.

    python scripts/mevki_model.py

Varyantlar (hepsi lig-disarida-birak CV, 2022+2023; 2024'e DOKUNULMUYOR):
  P  havuzlanmis model, TM hedefiyle                       (mevcut)
  X  havuzlanmis + mevki gostergeleri (kesisim kaymasi)
  S  MEVKIYE OZEL ayri model (kaleci: havuzlanmis, n=242)
  U  havuzlanmis, BIRLESIK hedefle: y = y_TM VEYA y2 (ust lige gecis)

Karar kurali (onceden ilan): bir varyant ancak P'yi, ilgili mevkide VE
en az iki hedefte (y_TM, y2) esli bootstrap GA'si sifiri dislayarak
gecerse benimsenir. Aksi halde P kalir.

U'nun degerlendirmesi ozel: U, y_TM ve y2'yi birlikte ogrenir; bu yuzden U
hem TM hedefinde HEM y2'de P ile kiyaslanir - birinde kaybedip digerinde
kazaniyorsa 'kor noktayi kapatti' denemez.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import train_model as tm  # noqa: E402
from scout.features.outcome2 import ust_gecis  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
MEVKILER = ["Defender", "Midfielder", "Attacker", "Goalkeeper"]
POS_KOL = ["pos_D", "pos_M", "pos_A"]        # kaleci = referans


def hazirla_veri(con) -> pd.DataFrame:
    egitim = tm.veri_yukle(con, tm.EGITIM_SEZONLARI)
    havuz = con.sql("""SELECT player_id, league_id, season, country, minutes
                       FROM player_features""").df()
    o = ust_gecis(egitim[["player_id", "league_id", "season", "country"]],
                  havuz)
    d = egitim.merge(o[["player_id", "league_id", "season", "o_seviye",
                        "gozlenebilir", "y2"]],
                     on=["player_id", "league_id", "season"], how="left")
    d["y2_gecerli"] = d.gozlenebilir.fillna(False) & (d.o_seviye >= 2)
    d["y2"] = d.y2.fillna(0).astype(int)
    d["y_bir"] = ((d.y == 1) | ((d.y2 == 1) & d.y2_gecerli)).astype(int)
    for k, pg in zip(POS_KOL, ["Defender", "Midfielder", "Attacker"]):
        d[k] = (d.pos_group == pg).astype(int)
    return d.reset_index(drop=True)


def lolo(d: pd.DataFrame, kol: list[str], ycol: str,
         mevki_ozel: bool = False) -> pd.Series:
    """Lig-disarida-birak; mevki_ozel ise her mevki ayri model."""
    tah = pd.Series(np.nan, index=d.index)
    for lig in d.league_id.unique():
        te = d.league_id == lig
        tr = ~te
        if mevki_ozel:
            for pg in MEVKILER:
                tep = te & (d.pos_group == pg)
                if tep.sum() == 0:
                    continue
                trp = tr & (d.pos_group == pg)
                # kaleci (ve yetersiz) -> havuzlanmis
                if pg == "Goalkeeper" or trp.sum() < 300 or d.loc[trp, ycol].sum() < 30:
                    trp = tr
                _, p = tm.egit(tm._hazirla(d[trp], kol), d.loc[trp, ycol].to_numpy(),
                               tm._hazirla(d[tep], kol, ref=d[trp]))
                tah[tep] = p
        else:
            if d.loc[tr, ycol].sum() < 30 or te.sum() < 10:
                continue
            _, p = tm.egit(tm._hazirla(d[tr], kol), d.loc[tr, ycol].to_numpy(),
                           tm._hazirla(d[te], kol, ref=d[tr]))
            tah[te] = p
    return tah


def karsilastir(d: pd.DataFrame, hedef: str, gecerli: pd.Series,
                B: int = 200) -> pd.DataFrame:
    """P/X/S/U'yu hedefe gore mevki mevki kiyasla."""
    satir = []
    for ad, g in [("HEPSI", d)] + [(m, d[d.pos_group == m]) for m in MEVKILER]:
        g = g[gecerli.loc[g.index]].copy()
        g["y"] = g[hedef]
        if len(g) < 80 or g.y.sum() < 20 or (1 - g.y).sum() < 20:
            satir.append(dict(mevki=ad, n=len(g), olumlu=int(g.y.sum()),
                              not_="yetersiz"))
            continue
        auc = {k: lig_ici_auc(g, k) for k in ("P", "X", "S", "U")}
        bs = esli_bootstrap(g, ["P", "X", "S", "U"], B=B)
        r = dict(mevki=ad, n=len(g), olumlu=int(g.y.sum()), **auc)
        for v in ("X", "S", "U"):
            o, lo, hi = fark_ga(bs, v, "P")
            r[f"{v}-P"] = o
            r[f"{v}_ga"] = (lo, hi)
        satir.append(r)
    return pd.DataFrame(satir)


def yazdir(t: pd.DataFrame, baslik: str) -> None:
    print(f"\n{'=' * 96}\n{baslik}\n{'=' * 96}")
    print(f"{'mevki':12s}{'n':>6s}{'olumlu':>8s}{'P':>7s}{'X':>7s}{'S':>7s}{'U':>7s}"
          f"    X-P                 S-P                 U-P")
    for _, r in t.iterrows():
        if "not_" in r and isinstance(r.get("not_"), str):
            print(f"{r.mevki:12s}{int(r.n):6d}{int(r.olumlu):8d}   (yetersiz orneklem)")
            continue

        def f(v):
            lo, hi = r[f"{v}_ga"]
            return f"{r[v + '-P']:+.3f}[{lo:+.2f},{hi:+.2f}]" + (
                "*" if (lo > 0 or hi < 0) else " ")

        print(f"{r.mevki:12s}{int(r.n):6d}{int(r.olumlu):8d}{r.P:7.3f}{r.X:7.3f}"
              f"{r.S:7.3f}{r.U:7.3f}    {f('X')} {f('S')} {f('U')}")
    print("  * = %95 GA sifiri disliyor")


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    d = hazirla_veri(con)
    con.close()
    print(f"[in] {len(d):,} satir · TM olumlu {int(d.y.sum()):,} · "
          f"y2 olumlu {int(((d.y2 == 1) & d.y2_gecerli).sum()):,} · "
          f"birlesik olumlu {int(d.y_bir.sum()):,}")
    print("[in] mevki dagilimi:", d.pos_group.value_counts().to_dict())

    oz = tm.OZELLIKLER
    d["P"] = lolo(d, oz, "y")
    d["X"] = lolo(d, oz + POS_KOL, "y")
    d["S"] = lolo(d, oz, "y", mevki_ozel=True)
    d["U"] = lolo(d, oz, "y_bir")
    d = d.dropna(subset=["P", "X", "S", "U"])

    hepsi = pd.Series(True, index=d.index)
    yazdir(karsilastir(d, "y", hepsi), "HEDEF 1: TM sonucu (y)")
    yazdir(karsilastir(d, "y2", d.y2_gecerli),
           "HEDEF 2: ust lige gecis (y2) - bagimsiz")
    yazdir(karsilastir(d, "y_bir", hepsi), "HEDEF 3: birlesik (y_TM veya y2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
