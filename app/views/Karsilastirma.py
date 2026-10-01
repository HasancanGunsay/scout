"""Karşılaştırma - 2-5 oyuncuyu yan yana koy. '10'u 3'e indirme' adımının aracı."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scout.scoring.engine import column_for

sh.page_setup("Karşılaştırma", "2-5 oyuncuyu yan yana koy. Sistemin verdiği listeyi kendi kısa listene indirmenin aracı.", "balance")

feats = sh.load_features()
scores = sh.load_scores()

labels = feats.apply(
    lambda r: f"{r.player_name} — {r.team_name} ({r.league_name} {int(r.season)})", axis=1
)
lookup = dict(zip(labels, feats.index))

short = sh.TK.api_secimleri(sh.takip_listesi())
default = []
for it in short:
    m = feats[(feats.player_id == it["player_id"])
              & (feats.league_id == it["league_id"])
              & (feats.season == it["season"])]
    if not m.empty:
        default.append(labels.loc[m.index[0]])

picks = st.multiselect(
    "Oyuncular (2-5)", sorted(lookup), default=default[:5],
    help="Takip listendekiler hazır geliyor.",
)

if len(picks) < 2:
    ui.empty_state(
        "En az 2 oyuncu seç",
        "Takibe aldıkların buraya otomatik gelir. "
        "Keşif ekranından oyuncu işaretleyerek başla.",
    )
    st.stop()
if len(picks) > 5:
    st.warning("En fazla 5 oyuncu karşılaştırılabilir; ilk 5 alındı.")
    picks = picks[:5]

rows = feats.loc[[lookup[p] for p in picks]]

if rows.pos_group.nunique() > 1:
    st.warning(
        "Farklı mevki gruplarından oyuncular seçtin. Percentile'lar kendi havuzlarında "
        "hesaplandığı için doğrudan kıyas yanıltıcı olabilir.", icon="⚠️",
    )
if rows.league_id.nunique() > 1:
    st.info(
        "Farklı liglerden oyuncular. **Lig gücü katsayısı kurulmadan (Faz 4) ligler arası "
        "kıyas güvenilir değil.**", icon="ℹ️",
    )

sh.coverage_warning(rows.league_id.unique())
sh.veri_kalitesi_uyarisi(rows.league_id.unique())

# ------------------------------------------------------------------ ozet tablo
st.subheader("Künye")
info = rows[["player_name", "age_season_end", "position", "team_name", "league_name",
             "season", "minutes", "apps", "rating", "height_cm", "nationality"]].rename(
    columns={"player_name": "Oyuncu", "age_season_end": "Yaş", "position": "Mevki",
             "team_name": "Takım", "league_name": "Lig", "season": "Sezon",
             "minutes": "Dakika", "apps": "Maç", "rating": "Reyting",
             "height_cm": "Boy", "nationality": "Uyruk"}
).round(1)
st.dataframe(info.set_index("Oyuncu").T, width="stretch")

# ------------------------------------------------------------------ radar
st.divider()
st.subheader("Metrik profili")

RADAR = {
    "Goalkeeper": ["saves", "goals_conceded", "passes", "duels_won"],
    "Defender": ["duel_win_pct", "def_actions", "tackles", "interceptions",
                 "passes", "key_passes", "dribbles_won"],
    "Midfielder": ["passes", "key_passes", "def_actions", "duels_won",
                   "dribbles_won", "np_ga", "interceptions"],
    "Attacker": ["np_goals", "assists", "shots", "key_passes", "dribbles_won",
                 "duels_won", "def_actions"],
}
mets = RADAR.get(rows.iloc[0].pos_group, RADAR["Midfielder"])
names = [sh.metric_label(m) for m in mets]

fig = go.Figure()
for _, r in rows.iterrows():
    vals = []
    for m in mets:
        col = column_for(m)
        vals.append(float(r[col]) if col in feats.columns and pd.notna(r.get(col)) else 0.0)
    fig.add_trace(go.Scatterpolar(
        r=vals + vals[:1], theta=names + names[:1], fill="toself",
        name=r.player_name, opacity=0.45, line=dict(width=2),
        hovertemplate="%{theta}: %{r:.0f}<extra>" + str(r.player_name) + "</extra>",
    ))
ui.apply_plotly(fig)
fig.update_layout(
    polar=dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(visible=True, range=[0, 100], tickvals=[25, 50, 75, 100],
                        gridcolor=ui.COLORS["border"], tickfont=dict(size=10)),
        angularaxis=dict(gridcolor=ui.COLORS["border"]),
    ),
    height=520, margin=dict(l=80, r=80, t=24, b=60),
)
st.plotly_chart(fig, width="stretch")
st.caption("Değerler percentile (0-100), her oyuncunun kendi lig/sezon/mevki havuzunda.")

# ------------------------------------------------------------------ metrik tablo
st.divider()
st.subheader("Metrik metrik")
tbl = {}
for _, r in rows.iterrows():
    col = {}
    for m in mets:
        c = column_for(m)
        col[sh.metric_label(m)] = round(float(r[c]), 1) if pd.notna(r.get(c)) else None
    tbl[r.player_name] = col
mdf = pd.DataFrame(tbl)
st.dataframe(
    mdf.style.background_gradient(cmap="Blues", axis=1, vmin=0, vmax=100)
    .format("{:.0f}", na_rep="—"),
    width="stretch",
)
st.caption(
    "Değerler percentile (0-100); koyu mavi = kendi havuzunda üstün. "
    "Renk yalnızca yardımcıdır — sayılar her zaman görünür."
)

# ------------------------------------------------------------------ rol skorlari
st.divider()
st.subheader("Rol skorları")
key = rows[["player_id", "league_id", "season"]]
sc = scores.merge(key, on=["player_id", "league_id", "season"])
if not sc.empty:
    piv = sc.pivot_table(index="role_name", columns="player_id", values="score")
    piv.columns = [rows[rows.player_id == c].iloc[0].player_name for c in piv.columns]
    st.dataframe(
        piv.style.background_gradient(cmap="Blues", axis=None, vmin=0, vmax=100)
        .format("{:.1f}", na_rep="—"),
        width="stretch",
    )

