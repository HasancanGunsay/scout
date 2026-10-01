"""Eksik mevki bilgisini oyun profilinden cikar (ADIM 1).

SORUN: API bazi oyuncularda 'position' alanini bos donduruyor. Mevkisi
olmayan oyuncu kohortsuz kalir ve HIC SKOR ALMAZ - sessizce kaybolur.
Olculdu: 12 oyuncu, 3.850 dakika, biri 1.100 dakikayla tam bir sezon.

YAKLASIM: kendi verimizle egit. 15.000+ oyuncunun mevkisi zaten biliniyor;
oyun profili (per-90 sayimlar) mevkiyi guclu sekilde belirliyor. Kaleci
zaten neredeyse deterministik: kurtarisi olan baska kimse yok.

TASARIM KARARLARI
  - Cikarim GORUNUR: 'position_source' sutunu 'api' mi 'cikarim' mi
    oldugunu soyler. Uydurulmus veri gercek veriden ayirt edilebilmeli.
  - EMIN DEGILSE BOS BIRAKIR: min_proba altindaki tahmin kabul edilmez.
    Yanlis mevki, mevkisizlikten daha zararli - oyuncu yanlis kohortta
    yanlis sablonla puanlanir ve bu fark edilmez.
  - Lineer model, agac degil: katsayilar okunabilir olsun.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Transfermarkt mevki etiketleri -> kendi gruplarimiz.
# TM eslesmesi varsa cikarima gerek yok; gercek veri her zaman tercih edilir.
TM_POSITION_MAP: dict[str, str] = {
    "Goalkeeper": "Goalkeeper",
    "Centre-Back": "Defender", "Right-Back": "Defender", "Left-Back": "Defender",
    "Defensive Midfield": "Midfielder", "Central Midfield": "Midfielder",
    "Attacking Midfield": "Midfielder", "Right Midfield": "Midfielder",
    "Left Midfield": "Midfielder",
    "Centre-Forward": "Attacker", "Left Winger": "Attacker",
    "Right Winger": "Attacker", "Second Striker": "Attacker",
}

# Profil sutunlari - ham sayimlar, 90 dakikaya bolunerek kullanilir
PROFIL = ["saves", "goals_conceded", "shots", "goals", "assists", "key_passes",
          "passes", "tackles", "interceptions", "blocks", "duels", "dribbles",
          "fouls_made", "fouls_drawn"]

MIN_DAKIKA = 90.0     # bu kadar oynamayanda profil gurultulu
MIN_PROBA = 0.60      # bunun altinda tahmin KABUL EDILMEZ


def _profil_matrisi(df: pd.DataFrame) -> pd.DataFrame:
    dk = pd.to_numeric(df["minutes"], errors="coerce").replace(0, np.nan)
    out = pd.DataFrame(index=df.index)
    for c in PROFIL:
        v = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan
        out[c] = (v / dk * 90.0) if c in df.columns else 0.0
    return out.fillna(0.0)


def infer(df: pd.DataFrame, *, min_proba: float = MIN_PROBA) -> tuple[pd.DataFrame, dict]:
    """Eksik 'position' degerlerini doldur.

    Donen: (df + position_source + position_proba, rapor)
    """
    out = df.copy()
    if "position" not in out.columns:
        out["position"] = pd.NA
    out["position_source"] = np.where(out["position"].notna(), "api", "yok")
    out["position_proba"] = np.nan

    rapor: dict[str, object] = {"eksik": int(out["position"].isna().sum())}
    if not rapor["eksik"]:
        return out, rapor

    etiketli = out[out["position"].notna() & (out["minutes"] >= MIN_DAKIKA)]
    eksik = out[out["position"].isna()]
    if len(etiketli) < 200 or len(eksik) == 0:
        rapor["durum"] = "egitim verisi yetersiz"
        return out, rapor

    X = _profil_matrisi(etiketli)
    y = etiketli["position"].astype(str)
    model = Pipeline([("sc", StandardScaler()),
                      ("lr", LogisticRegression(max_iter=3000, C=1.0))])

    # Durustluk: capraz dogrulanmis dogruluk bildirilmeden model kullanilmaz
    rapor["cv_dogruluk"] = float(
        cross_val_score(model, X, y, cv=4, scoring="accuracy").mean())
    model.fit(X, y)

    Xe = _profil_matrisi(eksik)
    proba = model.predict_proba(Xe)
    en_iyi = proba.max(axis=1)
    tahmin = model.classes_[proba.argmax(axis=1)]

    kabul = en_iyi >= min_proba
    idx = eksik.index
    out.loc[idx[kabul], "position"] = tahmin[kabul]
    out.loc[idx[kabul], "position_source"] = "cikarim"
    out.loc[idx, "position_proba"] = en_iyi

    rapor["kabul"] = int(kabul.sum())
    rapor["red"] = int((~kabul).sum())
    rapor["ayrinti"] = pd.DataFrame({
        "oyuncu": eksik["player_name"].to_numpy(),
        "dakika": eksik["minutes"].to_numpy(),
        "tahmin": tahmin,
        "olasilik": en_iyi.round(3),
        "karar": np.where(kabul, "kabul", "RED (emin degil)"),
    }).sort_values("dakika", ascending=False)
    return out, rapor
