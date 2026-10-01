"""Laboratuvar - serbest sorgulama. 'Merak ettiğimi anında bakarım' ekranı.

Liderler sekmesi (1 Eki 2026, kullanıcı isteği): metrikler AİLE halinde.
Bir metriğe göre sıralarken aynı ailenin diğer metrikleri yanında durur
(pas /90 yanında toplam pas, ikili kazanma % yanında ikili sayısı) - oran
hacimsiz okunmasın. Katalog: app/_metrikler.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _metrikler as MK
import _shared as sh
import _style as ui
import pandas as pd
import plotly.express as px
import streamlit as st

sh.page_setup("Laboratuvar", "Serbest sorgulama alanı. Merak ettiğin her şeye kısıtsız bakabilirsin.", "science")

feats = sh.load_features()
# katalogda olup veride olmayan metrik sessizce düşmesin: yalnız var olanlar
AILELER = {a: [m for m in ms if m.kol in feats.columns]
           for a, ms in MK.AILELER.items()}
SECENEK = [m.kol for ms in AILELER.values() for m in ms]

tab1, tab2, tab3 = st.tabs(["Dağılım grafiği", "Liderler", "SQL"])

# ------------------------------------------------------------------ scatter
with tab1:
    st.caption("İki metriği karşı karşıya koy — aykırı değerler burada görünür.")
    c1, c2, c3 = st.columns(3)
    x = c1.selectbox("X ekseni", SECENEK, format_func=MK.ad,
                     index=SECENEK.index("shots_p90_sh") if "shots_p90_sh" in SECENEK else 0)
    y = c2.selectbox("Y ekseni", SECENEK, format_func=MK.ad,
                     index=SECENEK.index("np_ga_p90_sh") if "np_ga_p90_sh" in SECENEK else 1)
    RENK = {"pos_group": "Mevki", "league_name": "Lig", "age_band": "Yaş bandı",
            "team_name": "Takım"}
    color = c3.selectbox("Renk", list(RENK), format_func=RENK.get)

    f1, f2 = st.columns(2)
    minmin = f1.slider("Asgari dakika", 0, 3000, 450, 50)
    maxage = f2.slider("Azami yaş", 16.0, 40.0, 40.0, 0.5, format="%.1f")

    d = feats[(feats.minutes >= minmin) & (feats.age_season_end <= maxage)].copy()
    if d.empty:
        ui.empty_state("Filtreye uyan oyuncu yok", "Dakika veya yaş sınırını gevşet.")
    else:
        d["pos_group"] = d.pos_group.map(MK.MEVKI_ADI).fillna(d.pos_group)
        fig = px.scatter(
            d, x=x, y=y, color=color, hover_name="player_name",
            hover_data={"team_name": True, "age_season_end": ":.1f",
                        "minutes": True, "league_name": True},
            labels={x: MK.ad(x), y: MK.ad(y), color: RENK[color],
                    "team_name": "Takım", "age_season_end": "Yaş",
                    "minutes": "Dakika", "league_name": "Lig"},
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
    st.caption("Bir metrikte kim önde — ve o metriği bağlamına oturtan "
               "ilişkili metrikler yanında.")
    c1, c2, c3 = st.columns([1.2, 1.4, 0.8])
    aile = c1.selectbox("Kategori", list(AILELER), key="lead_aile")
    metrikler = AILELER[aile]
    metric = c2.selectbox("Sırala", [m.kol for m in metrikler],
                          format_func=MK.ad, key=f"lead_metric_{aile}")
    m_sec = MK.TUMU[metric]
    yon = c3.radio("Yön", ["Yüksek önce", "Düşük önce"],
                   index=1 if m_sec.dusuk_iyi else 0, key=f"lead_yon_{metric}",
                   help="Faul, kart, yenen gol gibi metriklerde düşük olan iyidir.")

    f1, f2, f3, f4, f5 = st.columns(5)
    MEVKILER = ["(hepsi)", "Goalkeeper", "Defender", "Midfielder", "Attacker"]
    pos = f1.selectbox("Mevki", MEVKILER,
                       index=0 if aile != "Kaleci" else 1,
                       format_func=lambda p: MK.MEVKI_ADI.get(p, p), key="lead_pos")
    sezonlar = ["(hepsi)"] + sorted(feats.season.dropna().unique().tolist(), reverse=True)
    sezon = f2.selectbox("Sezon", sezonlar, key="lead_sezon")
    ligler = ["(hepsi)"] + sorted(feats.league_name.dropna().unique().tolist())
    lig = f3.selectbox("Lig", ligler, key="lead_lig")
    maxage2 = f4.slider("Azami yaş", 16.0, 40.0, 40.0, 0.5, key="lead_yas",
                        format="%.1f")
    minmin2 = f5.slider("Asgari dakika", 0, 3000, 900, 50, key="lead_min")

    g1, g2 = st.columns([3, 1])
    ek = g1.multiselect(
        "Ek sütunlar (başka kategorilerden)",
        [k for k in SECENEK if k not in {m.kol for m in metrikler}],
        format_func=MK.ad, key="lead_ek", placeholder="Metrik ekle…",
        help="Örneğin pas listesine 'İkili kazanma %' eklemek gibi.")
    n = g2.slider("Kaç oyuncu", 10, 100, 25, 5, key="lead_n")

    d = feats[(feats.minutes >= minmin2) & (feats.age_season_end <= maxage2)]
    if pos != "(hepsi)":
        d = d[d.pos_group == pos]
    if sezon != "(hepsi)":
        d = d[d.season == sezon]
    if lig != "(hepsi)":
        d = d[d.league_name == lig]
    d = d.dropna(subset=[metric])

    if d.empty:
        ui.empty_state("Filtreye uyan oyuncu yok", "Filtreleri gevşet.")
    else:
        top = d.sort_values(metric, ascending=(yon == "Düşük önce")).head(n)
        # sıralanan metrik önce, sonra ailenin geri kalanı, sonra ek sütunlar
        sira = [metric] + [m.kol for m in metrikler if m.kol != metric] + ek
        t = pd.DataFrame({
            "Oyuncu": top.player_name, "Yaş": top.age_season_end.round(1),
            "Takım": top.team_name, "Lig": top.league_name, "Sezon": top.season,
            "Mevki": top.pos_group.map(MK.MEVKI_ADI).fillna(top.pos_group),
            "Dakika": top.minutes,
        })
        cfg = {"Yaş": st.column_config.NumberColumn(format="%.1f"),
               "Sezon": st.column_config.NumberColumn(format="%d"),
               "Dakika": st.column_config.NumberColumn(format="%d")}
        for k in sira:
            m = MK.TUMU[k]
            t[m.ad] = top[k] * (100 if m.yuzde else 1)
            cfg[m.ad] = st.column_config.NumberColumn(
                m.ad + (" ▼" if k == metric else ""), format=m.bicim,
                help=m.aciklama or None)
        st.dataframe(t, hide_index=True, use_container_width=True, height=560,
                     column_config=cfg)
        st.caption(f"{len(d):,} oyuncu-sezon filtreye uydu · ilk {len(top)} gösteriliyor"
                   .replace(",", "."))
        if "pass_accuracy" in sira:
            st.info("**İsabetli pas/maç (API) bir yüzde değil.** API bu alanda "
                    "yaklaşık maç başına isabetli pas **sayısı** veriyor; çok pas "
                    "atan oyuncuda yüksek çıkar. Gerçek pas isabeti yüzdesi "
                    "ücretsiz veride yok — Sofascore'dan bakın.")

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
