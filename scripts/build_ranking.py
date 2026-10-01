"""FAZ 6.3: mevki sirlama tablosu (player_ranking).

    python scripts/build_ranking.py

Her U23 (450+ dk) oyuncu-sezon icin:
  model_olasilik   TAM model, DISARIDAN tahmin
  piyasa_olasilik  yalniz-piyasa modeli (deger_var=1 ise), DISARIDAN
  piyasa_ustu      model - piyasa   (yalniz degerlemesi VAR ise; yoksa NaN)
  band / ucuz      sezon-sonu deger bandi
  guven            'iyi' | 'zayif' | 'dogrulanmamis' | 'dusuk'
  tahmin_turu      'lig-disi CV' (2022,2023) | 'zaman-disi' (2024)
  *_ham            kalibrasyon ONCESI olasiliklar (model/piyasa/saf)

KALIBRASYON (FAZ 6.6, PLAN §50): model/piyasa/saf kapsam-kosullu Platt ile
kalibre; kalibrator de disaridan. Kapsam ICINDE siralama degismez, karisik
listede izlenen ligler one cikar (sayfa bunu uyarir).

NEDEN DISARIDAN TAHMIN
Kullanici tarihsel bir sezonu secip "gercekte ne oldu" diye bakacak. Uretim
modeli bu sezonlari GORMUS (in-sample): gecmis siralamalar oldugundan iyi
gorunur ve kullanici yanlis bir guven edinir. Bu yuzden:
  2022, 2023 -> lig-disarida-birak CV (satir kendi ligini hic gormemis)
  2024       -> 2022+2023 ile egitilmis model (zaman disi)
2025+ acildiginda uretim modeli (model_ranker.joblib) kullanilacak.

GUVEN ETIKETLERI (6.2 ve 6.2b'nin bulgulari):
  dogrulanmamis  deger_var=0: TM sonucu kor, yalniz tek pencere isareti
  zayif          0,5-5M bandi: model ~ dakika+yas'tan ayirt edilemiyor
  dusuk          kaleci: n=242
  iyi            <0,5M ve >=5M: oyun verisi dakika+yasin USTUNE bilgi katiyor
Oncelik: dusuk > dogrulanmamis > zayif > iyi (en kotumser olan kazanir).
"""

from __future__ import annotations

import json
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

import fiyat_bandi as fb  # noqa: E402
import train_model as tm  # noqa: E402
from scout.model.kalibrasyon import grup_fit, grup_uygula, lolo_kalibre  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
MEVKILER = ["Defender", "Midfielder", "Attacker", "Goalkeeper"]


def guven_etiketi(pos_group: str, deger_var: int, bant: str) -> str:
    if pos_group == "Goalkeeper":
        return "dusuk"
    if deger_var == 0:
        return "dogrulanmamis"
    if bant in ("2 0,5-2M", "3 2-5M"):
        return "zayif"
    return "iyi"


KALIBRE = ("model", "piyasa", "saf")
KALIBRATOR = ROOT / "data" / "kalibrator.json"


def kalibre_et(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """FAZ 6.6: kapsam-kosullu Platt (PLAN §50). Kalibrator de DISARIDAN:
      lig-disi CV satirlari -> kalibrator o ligi hic gormemis (lolo_kalibre)
      zaman-disi (2024)     -> kalibrator 2022+2023 CV satirlarindan
    Ham degerler {kol}_ham olarak saklanir. Ikinci donus: tum CV satirlariyla
    kurulan parametreler (2025+ uretim tahminleri icin).
    """
    d = d.copy()
    cv = (d.tahmin_turu == "lig-disi CV") & d.y.notna()
    zd = d.tahmin_turu == "zaman-disi"
    par_hepsi = {}
    for kol in KALIBRE:
        d[f"{kol}_ham"] = d[kol]
        d.loc[cv, kol] = lolo_kalibre(d[cv], kol, "kapsam")
        par = grup_fit(d.loc[cv, f"{kol}_ham"], d.loc[cv, "y"],
                       d.loc[cv, "kapsam"].astype(str))
        d.loc[zd, kol] = grup_uygula(d.loc[zd, f"{kol}_ham"],
                                     d.loc[zd, "kapsam"].astype(str), par)
        par_hepsi[kol] = {g: list(ab) for g, ab in par.items()}
    return d, par_hepsi


def tablo_uret(con) -> pd.DataFrame:
    egitim = tm.veri_yukle(con, tm.EGITIM_SEZONLARI)
    d24 = tm.veri_yukle(con, (2024,))

    cv = fb.cv_tahmin(egitim)
    cv["tahmin_turu"] = "lig-disi CV"
    zd = fb.tahmin_uret(egitim, d24)
    zd["tahmin_turu"] = "zaman-disi"

    d = pd.concat([cv, zd], ignore_index=True)
    d, par = kalibre_et(d)
    KALIBRATOR.write_text(json.dumps(
        {"yontem": "platt_kapsam", "kaynak": "2022+2023 lig-disi CV",
         "parametre": par}, indent=2), encoding="utf-8")
    d["bant"] = fb.bant_ata(d.deger)
    d["ucuz"] = fb.ucuz_mu(d.bant)
    d["model_olasilik"] = d.model
    # piyasa referansi yalniz degerlemesi VAR iken tanimli (6.2 §45.4)
    d["piyasa_olasilik"] = np.where(d.deger_var == 1, d.piyasa, np.nan)
    d["piyasa_ustu"] = d.model_olasilik - d.piyasa_olasilik
    d["guven"] = [guven_etiketi(p, v, b) for p, v, b
                  in zip(d.pos_group, d.deger_var, d.bant)]
    return d


def kaydet(d: pd.DataFrame) -> None:
    kol = ["player_id", "league_id", "season", "player_name", "league_name",
           "country", "kapsam", "pos_group", "age_season_end", "minutes",
           "score", "deger", "deger_var", "bant", "ucuz", "model_olasilik",
           "piyasa_olasilik", "piyasa_ustu", "saf", "basit", "guven",
           "model_ham", "piyasa_ham", "saf_ham",
           "tahmin_turu", "kademe"]
    t = d[[c for c in kol if c in d.columns]].copy()
    con = duckdb.connect(str(DB))
    con.register("t", t)
    con.execute("CREATE OR REPLACE TABLE player_ranking AS SELECT * FROM t")
    con.close()
    print(f"[kaydet] player_ranking: {len(t):,} satir")


def rapor(d: pd.DataFrame) -> None:
    print(f"\n{'=' * 88}\nMEVKI BAZINDA - DISARIDAN TAHMIN "
          f"(lig-ici AUC, esli bootstrap)\n{'=' * 88}")
    print(f"{'mevki':12s}{'n':>6s}{'olumlu':>8s}{'model':>8s}{'piyasa':>8s}"
          f"{'basit':>8s}{'saf':>8s}    model-basit          saf-basit")
    for pg in MEVKILER:
        g = d[d.pos_group == pg].copy()
        g["y"] = (g.kademe >= 3).astype(int)
        if len(g) < 80 or g.y.sum() < 15:
            print(f"{pg:12s}{len(g):6d}{int(g.y.sum()):8d}   (yetersiz)")
            continue
        auc = {k: lig_ici_auc(g, k) for k in ("model", "piyasa", "basit", "saf")}
        bs = esli_bootstrap(g, ["model", "piyasa", "basit", "saf"], B=200)

        def f(a, b):
            o, lo, hi = fark_ga(bs, a, b)
            return f"{o:+.3f}[{lo:+.2f},{hi:+.2f}]" + (
                "*" if (lo > 0 or hi < 0) else " ")

        print(f"{pg:12s}{len(g):6d}{int(g.y.sum()):8d}{auc['model']:8.3f}"
              f"{auc['piyasa']:8.3f}{auc['basit']:8.3f}{auc['saf']:8.3f}"
              f"    {f('model', 'basit')} {f('saf', 'basit')}")

    print(f"\n{'=' * 88}\nKALIBRASYON - mevki x 4 dilim (model dedi / ne oldu)"
          f"\n{'=' * 88}")
    for pg in MEVKILER:
        g = d[d.pos_group == pg].copy()
        g["y"] = (g.kademe >= 3).astype(int)
        if len(g) < 100:
            print(f"{pg:12s} (n={len(g)}, dilimleme icin yetersiz)")
            continue
        g["dilim"] = pd.qcut(g.model_olasilik, 4, duplicates="drop")
        k = g.groupby("dilim", observed=True).agg(
            n=("y", "size"), dedi=("model_olasilik", "mean"), oldu=("y", "mean"))
        hata = float((k.dedi - k.oldu).abs().mul(k.n).sum() / k.n.sum())
        print(f"{pg:12s} kalibrasyon hatasi {hata:.3f} · "
              + " | ".join(f"{r.dedi:.2f}->{r.oldu:.2f}" for r in k.itertuples()))

    print(f"\n{'=' * 88}\nUCUZ BANTTA TOP-20 ISABETI (mevki x sezon; taban = ayni "
          f"bantin ortalamasi)\n{'=' * 88}")
    u = d[d.ucuz].copy()
    u["y"] = (u.kademe >= 3).astype(int)
    satir = []
    for (pg, sez), g in u.groupby(["pos_group", "season"]):
        if len(g) < 60:
            continue
        top = g.nlargest(20, "model_olasilik")
        satir.append(dict(mevki=pg, sezon=sez, n=len(g),
                          taban=g.y.mean(), top20=top.y.mean(),
                          guven=top.guven.mode().iat[0]))
    t = pd.DataFrame(satir)
    t["kat"] = t.top20 / t.taban
    print(t.round(3).to_string(index=False))
    print("\n  guven etiketi dagilimi (tum tablo):")
    print(d.guven.value_counts().to_string())


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    d = tablo_uret(con)
    con.close()
    print(f"[in] {len(d):,} satir · {d.tahmin_turu.value_counts().to_dict()}")
    rapor(d)
    kaydet(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
