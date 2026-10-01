"""Ham sayimlardan analiz edilebilir metriklere.

Iki metrik ailesi var ve ikisi FARKLI istatistiksel muamele ister:

  SAYIM (count)  : gol, sut, top calma... -> 90 dakikaya normalize edilir.
                   Poisson benzeri; guvenilirligi oynanan dakikaya bagli.
  ORAN  (rate)   : ikili mucadele kazanma %, dribbling basari %...
                   Binom benzeri; guvenilirligi PAYDA sayisina bagli
                   (10 mucadelede %70 ile 400 mucadelede %70 ayni sey degil).

Bu ayrim §1.2'deki shrinkage icin kritik - iki aile ayri modellenir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --- 90 dakikaya normalize edilecek sayim metrikleri ---------------------
# anahtar: uretilecek sutun | deger: kaynak sutun(lar), toplanir
COUNT_METRICS: dict[str, list[str]] = {
    "goals": ["goals"],
    "np_goals": ["goals", "-pens_scored"],       # penaltisiz gol - daha iyi yetenek gostergesi
    "assists": ["assists"],
    "ga": ["goals", "assists"],
    "np_ga": ["goals", "assists", "-pens_scored"],
    "shots": ["shots"],
    "shots_on": ["shots_on"],
    "key_passes": ["key_passes"],
    "passes": ["passes"],
    "tackles": ["tackles"],
    "interceptions": ["interceptions"],
    "blocks": ["blocks"],
    "def_actions": ["tackles", "interceptions", "blocks"],
    "duels": ["duels"],
    "duels_won": ["duels_won"],
    "dribbles": ["dribbles"],
    "dribbles_won": ["dribbles_won"],
    "fouls_drawn": ["fouls_drawn"],
    "fouls_made": ["fouls_made"],
    "cards": ["yellow", "red"],
}

# --- kaleciye ozgu sayim metrikleri --------------------------------------
# COUNT_METRICS'ten AYRI tutuluyor, iki sebeple:
#   1) Saha oyuncusunda tanimsiz. Ortak hatta sokulursa fillna(0) yuzunden
#      her stoper "0 kurtaris" ile kaydolur; kaleci kohortu disinda anlamsiz
#      sifir yiginlari shrinkage fitini bozar.
#   2) Kaynak veride BOS olabiliyor (586 kalecinin 63'unde 'saves' yok).
#      Bosu 0 saymak o kaleciyi "hic kurtaris yapmamis" gosterir - en kotu
#      kaleci sanilir. Bos, bos kalmali.
# Bu metrikler olmadan 'Kaleci - Kurtaran' sablonu agirliginin %82'sini
# kaybediyordu ve kaleciler yalnizca pas + ikili mucadeleye gore siralaniyordu.
GK_COUNT_METRICS: dict[str, str] = {
    "saves": "saves",
    "goals_conceded": "goals_conceded",
}

# --- oran metrikleri: (pay, payda) ---------------------------------------
RATE_METRICS: dict[str, tuple[str, str]] = {
    "shot_accuracy": ("shots_on", "shots"),
    "duel_win_pct": ("duels_won", "duels"),
    "dribble_pct": ("dribbles_won", "dribbles"),
    "goals_per_shot": ("goals", "shots"),
    "starts_pct": ("starts", "apps"),
}

# Mevki gruplari - percentile kohortu olarak kullanilir.
POSITION_GROUPS = ["Goalkeeper", "Defender", "Midfielder", "Attacker"]

# API tutarsiz etiket donduruyor: cogu zaman "Attacker", bazen "Forward".
# Bu es anlamli eslemesi olmadan 16 oyuncu (18.196 dakika, biri TAM SEZON)
# 'Unknown' grubuna dusup kohortsuz kaliyor ve HIC SKOR ALMIYORDU.
# Sessiz veri kaybiydi; denetimde yakalandi (§15).
POSITION_ALIASES = {
    "Forward": "Attacker",
    "Striker": "Attacker",
    "Attacker": "Attacker",
    "Midfielder": "Midfielder",
    "Defender": "Defender",
    "Goalkeeper": "Goalkeeper",
}


def _sum_cols(df: pd.DataFrame, spec: list[str]) -> pd.Series:
    """['goals', '-pens_scored'] -> df.goals - df.pens_scored

    BILESENLERIN TAMAMI NaN ISE SONUC NaN - 0 degil (§21).
    Eski surum fillna(0) yapiyordu ve build_db'nin bilincli olarak NaN
    biraktigi "lig bu metrigi hic yayinlamiyor" durumunu geri sifira
    ceviriyordu. Sonuc: Veikkausliiga oyuncularina var olmayan verilerden
    skor uretiliyordu. Iki yerde de duzeltilmesi gerekiyordu.

    En az bir bilesen biliniyorsa toplanir (bilinmeyen bilesen 0 sayilir);
    ornegin penalti verisi olmayan bir ligde np_goals = goals olur.
    """
    parcalar = []
    for item in spec:
        neg = item.startswith("-")
        col = item[1:] if neg else item
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        parcalar.append(-vals if neg else vals)
    if not parcalar:
        return pd.Series(np.nan, index=df.index, dtype=float)
    # min_count=1: hepsi NaN ise NaN dondur
    return pd.concat(parcalar, axis=1).sum(axis=1, min_count=1)


def add_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Sayim metriklerini 90 dakikaya normalize et.

    Ham toplam da '<isim>_raw' olarak korunur - shrinkage'in pay/payda
    hesabinda ham sayilara ihtiyaci var.
    """
    out = df.copy()
    nineties = out["nineties"].replace(0, np.nan)

    for name, spec in COUNT_METRICS.items():
        raw = _sum_cols(out, spec).clip(lower=0)  # negatif olamaz
        out[f"{name}_raw"] = raw
        out[f"{name}_p90"] = (raw / nineties).astype(float)

    return out


def add_gk_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Kaleci sayim metriklerini 90 dakikaya normalize et - YALNIZCA kalecilerde.

    add_position_group'tan SONRA calismali (pos_group'a ihtiyac duyar).
    Saha oyuncularinda ve kaynak degeri bos olan kalecilerde NaN birakir;
    gerekcesi GK_COUNT_METRICS aciklamasinda.
    """
    out = df.copy()
    nineties = out["nineties"].replace(0, np.nan)
    is_gk = out["pos_group"].eq("Goalkeeper")

    for name, src in GK_COUNT_METRICS.items():
        if src not in out.columns:
            out[f"{name}_raw"] = np.nan
            out[f"{name}_p90"] = np.nan
            continue
        raw = pd.to_numeric(out[src], errors="coerce").where(is_gk).clip(lower=0)
        out[f"{name}_raw"] = raw
        out[f"{name}_p90"] = (raw / nineties).astype(float)

    return out


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Oran metriklerini ekle. Payda 0 ise NaN - '0/0 = %0' yanlis olur."""
    out = df.copy()
    for name, (num, den) in RATE_METRICS.items():
        if num not in out.columns or den not in out.columns:
            continue
        # NaN korunur (§21): payda bilinmiyorsa oran da bilinmiyor demektir,
        # "0 mucadeleden 0 kazanma" degil.
        n = pd.to_numeric(out[num], errors="coerce")
        d = pd.to_numeric(out[den], errors="coerce")
        out[f"{name}_num"] = n
        out[f"{name}_den"] = d
        out[name] = (n / d.replace(0, np.nan)).astype(float)
    return out


# --- TOPA SAHIP OLMA AYARLI savunma metrikleri (§32) --------------------
# PROBLEM (olculdu §30): ham savunma hacmi TAKIM BAGLAMIYLA kirli. Zayif
# takim cok savunur, oyuncusu cok top calar. Takimin kendi savunma
# yogunlugu (AUC 0,408 stoperlerde) oyuncunun kendi metriginden DAHA GUCLU
# anti-tahminci - yani metrik buyuk olcude takimin zayifligini olcuyor.
#
# COZUM: possession-adjusted metrik. Gercek possession verisi ucretsiz
# planda yok; TAKIM PAS HACMI iyi bir vekil (cok pas = cok topa sahip =
# az savunma firsati). Ayni ham sayiyi cok topa sahip bir takimda yapmak
# daha degerlidir.
#
#     pAdj = ham_p90 x (takim_pas90 / ligin_medyan_pas90)
#
# Olculdu (stoper, deger sicramasi AUC): ham 0,456 -> takim orani 0,479
# -> possession vekili 0,514. Sahte anti-sinyal kalkiyor.
PADJ_METRIKLERI = ["tackles", "interceptions", "blocks", "def_actions", "duels"]


def add_possession_adjusted(df: pd.DataFrame) -> pd.DataFrame:
    """Savunma metriklerinin takim baglamindan arindirilmis surumleri.

    add_per90'dan SONRA calismali (_p90 sutunlarina ihtiyac duyar).
    Takim/lig bilgisi yoksa sessizce atlar - ham metrikler zaten duruyor.
    """
    out = df.copy()
    gerekli = {"team_id", "league_id", "season", "passes", "minutes"}
    if not gerekli.issubset(out.columns):
        return out

    dk = pd.to_numeric(out["minutes"], errors="coerce")
    pas = pd.to_numeric(out["passes"], errors="coerce")

    # takim pas/90 = takimin toplam pasi / takimin toplam 90'i
    yardim = pd.DataFrame({"lg": out["league_id"], "sz": out["season"],
                           "tm": out["team_id"], "pas": pas, "dk": dk})
    tt = (yardim.groupby(["lg", "sz", "tm"], dropna=False)
          .agg(pas=("pas", "sum"), dk=("dk", "sum")).reset_index())
    tt["takim_pas90"] = tt.pas / tt.dk.replace(0, np.nan) * 90.0
    out = out.merge(tt[["lg", "sz", "tm", "takim_pas90"]],
                    left_on=["league_id", "season", "team_id"],
                    right_on=["lg", "sz", "tm"], how="left").drop(
                        columns=["lg", "sz", "tm"])

    # lig medyani ile normalize - ligler arasi olcek farki karismasin
    med = out.groupby(["league_id", "season"])["takim_pas90"].transform("median")
    katsayi = (out["takim_pas90"] / med.replace(0, np.nan)).clip(0.5, 2.0)
    out["padj_katsayi"] = katsayi

    for m in PADJ_METRIKLERI:
        ham = f"{m}_p90"
        if ham in out.columns:
            out[f"{m}_padj_p90"] = out[ham] * katsayi
            out[f"{m}_padj_raw"] = out.get(f"{m}_raw", np.nan) * katsayi
    return out


def add_position_group(df: pd.DataFrame) -> pd.DataFrame:
    """API mevkisini kohort grubuna cevir.

    Es anlamlilar eslenir (Forward -> Attacker). Taninmayan etiket kalirsa
    'Unknown' olur; bu durumda oyuncu kohortsuz kalacagi icin uyari basilir -
    sessizce kaybolmasin.
    """
    out = df.copy()
    pos = out["position"].astype("string").str.strip()
    mapped = pos.map(POSITION_ALIASES)
    out["pos_group"] = mapped.fillna("Unknown")

    lost = out[out.pos_group == "Unknown"]
    if len(lost):
        import warnings

        etiketler = sorted(lost["position"].dropna().unique())
        bos = int(lost["position"].isna().sum())
        parca = []
        if etiketler:
            parca.append(f"taninmayan etiket {etiketler} -> POSITION_ALIASES'a ekle")
        if bos:
            dk = int(lost.loc[lost["position"].isna(), "minutes"].sum())
            parca.append(f"{bos} oyuncuda mevki BOS (toplam {dk} dakika)")
        warnings.warn(
            f"{len(lost)} oyuncu kohortsuz kaldi ve SKOR ALMAYACAK: "
            + "; ".join(parca),
            stacklevel=2,
        )
    return out


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Tam metrik hattini uygula."""
    return (
        df.pipe(add_position_group)
        .pipe(add_per90)
        .pipe(add_gk_per90)      # pos_group'a bagli - add_position_group'tan sonra
        .pipe(add_possession_adjusted)   # add_per90'dan sonra (§32)
        .pipe(add_rates)
    )


def per90_names() -> list[str]:
    return [f"{k}_p90" for k in COUNT_METRICS]


def rate_names() -> list[str]:
    return list(RATE_METRICS)
