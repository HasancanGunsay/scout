"""Laboratuvar - serbest sorgulama. 'Merak ettiğimi anında bakarım' ekranı."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import plotly.express as px
import streamlit as st

sh.page_setup("Laboratuvar", "Serbest sorgulama alanı. Merak ettiğin her şeye kısıtsız bakabilirsin.", "science")

feats = sh.load_features()

tab1, tab2, tab3 = st.tabs(["Dağılım grafiği", "Lig lideri", "SQL"])

NUMERIC = sorted(
    c for c in feats.columns
    if feats[c].dtype.kind in "if" and not c.endswith(("_w", "_se", "_num", "_den"))
)

# ------------------------------------------------------------------ scatter
with tab1:
    st.caption("İki metriği karşı karşıya koy — aykırı değerler burada görünür.")
    c1, c2, c3 = st.columns(3)
    x = c1.selectbox("X ekseni", NUMERIC,
                     index=NUMERIC.index("shots_p90_sh") if "shots_p90_sh" in NUMERIC else 0)
    y = c2.selectbox("Y ekseni", NUMERIC,
                     index=NUMERIC.index("np_ga_p90_sh") if "np_ga_p90_sh" in NUMERIC else 1)
    color = c3.selectbox("Renk", ["pos_group", "league_name", "age_band", "team_name"])

    f1, f2 = st.columns(2)
    minmin = f1.slider("Asgari dakika", 0, 3000, 450, 50)
    maxage = f2.slider("Azami yaş", 16.0, 40.0, 40.0, 0.5)

    d = feats[(feats.minutes >= minmin) & (feats.age_season_end <= maxage)]
    if d.empty:
        ui.empty_state("Filtreye uyan oyuncu yok", "Dakika veya yaş sınırını gevşet.")
    else:
        fig = px.scatter(
            d, x=x, y=y, color=color, hover_name="player_name",
            hover_data=["team_name", "age_season_end", "minutes", "league_name"],
            height=620, opacity=0.75,
            color_discrete_sequence=ui.PLOTLY_TEMPLATE["layout"]["colorway"],
        )
        ui.apply_plotly(fig)
        fig.update_layout(margin=dict(l=8, r=8, t=8, b=60))
        fig.update_traces(marker=dict(size=9, line=dict(width=0.5, color="white")))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{len(d)} oyuncu · noktaların üzerine gelerek oyuncu adını gör")

# ------------------------------------------------------------------ liderler
with tab2:
    st.caption("Herhangi bir metrikte lig lideri kim?")
    c1, c2, c3 = st.columns(3)
    metric = c1.selectbox("Metrik", NUMERIC, key="lead_metric")
    pos = c2.selectbox("Mevki grubu", ["(hepsi)", "Goalkeeper", "Defender",
                                       "Midfielder", "Attacker"])
    minmin2 = c3.slider("Asgari dakika", 0, 3000, 900, 50, key="lead_min")

    d = feats[feats.minutes >= minmin2]
    if pos != "(hepsi)":
        d = d[d.pos_group == pos]
    top = d.nlargest(25, metric)[
        ["player_name", "age_season_end", "team_name", "league_name", "season",
         "pos_group", "minutes", metric]
    ].rename(columns={"player_name": "Oyuncu", "age_season_end": "Yaş",
                      "team_name": "Takım", "league_name": "Lig", "season": "Sezon",
                      "pos_group": "Mevki", "minutes": "Dakika"})
    st.dataframe(top.round(3), hide_index=True, use_container_width=True, height=560)

# ------------------------------------------------------------------ sql
with tab3:
    st.caption(
        "Doğrudan SQL. Tablolar: `player_features`, `player_scores`, "
        "`player_natural_role`, `tm_players`, `tm_transfers`, `tm_player_valuations`."
    )
    default_q = """SELECT player_name, age_season_end AS yas, team_name, minutes,
       round(np_ga_p90_sh, 3) AS np_ga_90, round(rating, 2) AS rating
FROM player_features
WHERE league_id = 72 AND season = 2024
  AND age_season_end < 22 AND minutes >= 900
ORDER BY np_ga_p90_sh DESC
LIMIT 20"""
    q = st.text_area("Sorgu", default_q, height=190)
    if st.button("Çalıştır", type="primary"):
        try:
            st.dataframe(sh._con().sql(q).df(), use_container_width=True, hide_index=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"{type(exc).__name__}: {exc}")

