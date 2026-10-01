"""Skorlama motoru - §5.

Girdi : player_features (shrinkage uygulanmis, percentile'a cevrilmis metrikler)
Cikti : rol basina 0-100 skor + HER METRIGIN KATKISI

ACIKLANABILIRLIK ZORUNLU (§5.4): her skorun yaninda hangi metrigin ne kadar
katki verdigi saklanir. Aciklanamayan skor, guvenilmeyen skordur - scout
"neden bu cocuk 87 aldi" diye sorabilmeli.

IKI SKOR URETILIR (§1.3):
  score      - kendi lig+sezon+mevki havuzunda percentile'lardan (SIMDIKI)
  age_score  - kendi YAS BANDI icindeki percentile'lardan (YASITLARINA GORE)

19'luk bir cocuk score'da 55, age_score'da 92 alabilir. Ikisi de dogrudur
ve farkli sorulari cevaplar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Kisa metrik anahtari -> player_features sutun eki
# Sayim metrikleri '<ad>_p90_sh', oran metrikleri '<ad>_sh' olarak duruyor.
RATE_KEYS = {"duel_win_pct", "dribble_pct", "shot_accuracy", "goals_per_shot", "starts_pct"}
PLAIN_KEYS = {"rating"}  # dogrudan sutun, shrinkage/percentile yok


def column_for(metric: str, *, age_band: bool = False) -> str:
    """Metrik anahtarindan percentile sutun adini uret."""
    suffix = "_agepct" if age_band else "_pct"
    if metric in PLAIN_KEYS:
        return f"{metric}{suffix}"
    if metric in RATE_KEYS:
        return f"{metric}_sh{suffix}"
    return f"{metric}_p90_sh{suffix}"


@dataclass
class Role:
    key: str
    name: str
    pos_group: str
    weights: dict[str, float]
    invert: list[str]
    # Dogrulanmis rol ayrimi varsa sablonu yalnizca o alt gruba uygula.
    # Ornek: stoper sablonlari bekleri puanlamasin (§14).
    cluster: str | None = None

    def select(self, df: "pd.DataFrame") -> "pd.DataFrame":
        sub = df[df["pos_group"] == self.pos_group]
        if self.cluster and "role_cluster" in sub.columns:
            tag = f"{self.pos_group}::{self.cluster}"
            hit = sub[sub["role_cluster"] == tag]
            # ayrim bu ligde uygulanmadiysa (kanit yok / kohort kucuk)
            # sablonu tum mevki grubuna uygula - oyuncu skorsuz kalmasin
            return hit if len(hit) else sub
        return sub


def load_roles(path: Path) -> tuple[list[Role], dict]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    roles = [
        Role(
            key=r["key"],
            name=r["name"],
            pos_group=r["pos_group"],
            weights={k: float(v) for k, v in r["weights"].items()},
            invert=list(r.get("invert", [])),
            cluster=r.get("cluster"),
        )
        for r in cfg["roles"]
    ]
    return roles, cfg.get("thresholds", {})


def score_role(
    df: pd.DataFrame,
    role: Role,
    *,
    age_band: bool = False,
    weight_overrides: dict[str, float] | None = None,
) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Bir rol icin skor + katki tablosu + kapsam orani uret.

    weight_overrides : arayuzdeki slider'lar (§5.3 Katman 4) buradan girer.

    Returns
    -------
    score        : 0-100
    contrib      : her metrigin skora katkisi (waterfall icin)
    coverage     : kullanilabilen agirligin toplam agirliga orani
                   (metrik eksikse skor yine uretilir ama kapsam dusuk isaretlenir)
    """
    weights = dict(role.weights)
    if weight_overrides:
        weights.update(weight_overrides)

    num = pd.Series(0.0, index=df.index)
    used_w = pd.Series(0.0, index=df.index)
    total_w = sum(abs(w) for w in weights.values()) or 1.0
    contrib = pd.DataFrame(index=df.index)

    for metric, w in weights.items():
        if w == 0:
            continue
        col = column_for(metric, age_band=age_band)
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        # 'invert' listesindekiler percentile asamasinda cevrilmediyse burada cevir
        if metric in role.invert and f"{metric}_inverted" not in df.columns:
            vals = 100.0 - vals
        ok = vals.notna()
        num = num.add((vals * w).where(ok, 0.0), fill_value=0.0)
        used_w = used_w.add(pd.Series(float(w), index=df.index).where(ok, 0.0), fill_value=0.0)
        contrib[metric] = (vals * w).where(ok)

    score = (num / used_w.replace(0, np.nan)).clip(0, 100)
    coverage = used_w / total_w
    # katkilari skorun bilesenlerine cevir (toplamlari skora esit olsun)
    contrib = contrib.div(used_w.replace(0, np.nan), axis=0)
    return score, contrib, coverage


def score_all(
    df: pd.DataFrame,
    roles: list[Role],
    *,
    age_band: bool = False,
) -> pd.DataFrame:
    """Her oyuncuyu kendi mevki grubundaki TUM rollere gore puanla.

    Uzun format dondurur: (player, role) basina bir satir.
    """
    frames = []
    suffix = "_age" if age_band else ""
    for role in roles:
        sub = role.select(df)
        if sub.empty:
            continue
        score, contrib, cov = score_role(sub, role, age_band=age_band)
        out = pd.DataFrame(
            {
                "player_id": sub["player_id"].to_numpy(),
                "league_id": sub["league_id"].to_numpy(),
                "season": sub["season"].to_numpy(),
                "role": role.key,
                "role_name": role.name,
                f"score{suffix}": score.to_numpy(),
                f"coverage{suffix}": cov.to_numpy(),
            },
            index=sub.index,
        )
        # katkilari JSON'a cevir - arayuzde waterfall icin
        out[f"contrib{suffix}"] = contrib.round(2).apply(
            lambda r: {k: v for k, v in r.items() if pd.notna(v)}, axis=1
        )
        frames.append(out)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def best_role(scores: pd.DataFrame) -> pd.DataFrame:
    """Her oyuncunun en yuksek skor aldigi rol = 'dogal rolu'."""
    idx = scores.groupby(["player_id", "league_id", "season"])["score"].idxmax()
    return scores.loc[idx].rename(columns={"role": "natural_role",
                                           "role_name": "natural_role_name"})
