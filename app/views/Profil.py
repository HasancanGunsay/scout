"""Oyuncu profili - radar + skor açıklaması (waterfall)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sh.page_setup("Oyuncu profili", "Metrik profili, skorun neden o skor olduğu, rol uyumu ve izleme bağlantıları.", "person")

feats = sh.load_features()
scores = sh.load_scores()
role_list, _ = sh.roles()

# ------------------------------------------------------------------ secim
c1, c2 = st.columns([3, 1])
with c1:
    labels = feats.apply(
        lambda r: f"{r.player_name} — {r.team_name} ({r.league_name} {int(r.season)})",
        axis=1,
    )
    lookup = dict(zip(labels, feats.index))
    pick = st.selectbox("Oyuncu ara", sorted(lookup), index=None,
                        placeholder="isim yazmaya başla...")
if pick is None:
    ui.empty_state("Oyuncu seçilmedi",
                   "Yukarıdaki kutuya isim yazmaya başla veya Keşif ekranından gel.")
    st.stop()

p = feats.loc[lookup[pick]]

# ------------------------------------------------------------------ ozet
st.markdown(f"## {p.player_name}")

_chips = [(f"{p.team_name}", "mute"), (f"{p.league_name} {int(p.season)}", "mute")]
if p.minutes >= 1800:
    _chips.append(("Tam sezon", "ok"))
elif p.minutes >= 900:
    _chips.append(("Yeterli dakika", "ok"))
elif p.minutes >= 450:
    _chips.append(("Sınırlı dakika", "warn"))
else:
    _chips.append(("Çok az dakika — skorlar güvenilmez", "risk"))
if pd.notna(p.get("age_season_end")) and p.age_season_end < 21.5:
    _chips.append(("U21", "info"))

# Guven sinyali (§18.4) - yukaridaki dakika rozetinden FARKLI bir sey soyler.
# Yukaridaki: "istatistik guvenilir mi" (orneklem yeterli mi)
# Bu        : "kulubu ona guveniyor mu" (yasitlarina gore ne kadar oynadi)
_g = p.get("minutes_agepct")
if pd.isna(_g):
    _g = p.get("minutes_pct")
if pd.notna(_g):
    _etiket, _kind = sh.guven_seviyesi(float(_g))
    _chips.append((f"Güven: {_etiket} (%{float(_g):.0f})", _kind))
ui.badges(*_chips)

k = st.columns(6)
k[0].metric("Yaş", f"{p.age_season_end:.1f}")
k[1].metric("Mevki", p.position or "—")
k[2].metric("Dakika", f"{int(p.minutes)}")
k[3].metric("Maç", f"{int(p.apps)}")
k[4].metric("Reyting", f"{p.rating:.2f}" if pd.notna(p.rating) else "—")
k[5].metric("Boy", f"{int(p.height_cm)} cm" if pd.notna(p.height_cm) else "—")

# Transfermarkt meta verisi (varsa)
if "market_value_eur" in feats.columns and (
    pd.notna(p.get("market_value_eur")) or pd.notna(p.get("contract_until"))
):
    m = st.columns(5)
    mv = p.get("market_value_eur")
    m[0].metric("Piyasa değeri", f"€{int(mv):,}".replace(",", ".") if pd.notna(mv) else "—")
    pk = p.get("peak_market_value_eur")
    m[1].metric("Zirve değer", f"€{int(pk):,}".replace(",", ".") if pd.notna(pk) else "—")
    cu = p.get("contract_until")
    m[2].metric("Sözleşme", str(cu)[:10] if pd.notna(cu) else "—")
    m[3].metric("Ayak", p.get("foot") or "—")
    m[4].metric("Milli maç", int(p.international_caps)
                if pd.notna(p.get("international_caps")) else "—")
    if pd.notna(p.get("tm_url")):
        st.caption(f"Transfermarkt eşleşmesi: {p.get('match_confidence')} seviyesi · "
                   f"[profil](https://www.transfermarkt.com{p.tm_url})")
elif "market_value_eur" in feats.columns:
    st.caption(
        "Transfermarkt eşleşmesi yok — piyasa değeri ve sözleşme bilgisi mevcut değil. "
        "Bu, oyuncunun kalitesiyle ilgili bir şey söylemez; CC0 veri seti Serie B'nin "
        "yarısını kapsamıyor."
    )

if p.get("multi_team"):
    st.info(f"Sezon içinde kulüp değiştirmiş: {p.get('all_teams', '—')}. "
            "API bu durumda sezon toplamlarını her iki kulüpte tekrarlayabiliyor; "
            "en çok dakikalı kayıt esas alındı.", icon="↔️")

sh.coverage_warning([p.league_id])
sh.veri_kalitesi_uyarisi([p.league_id])

# ------------------------------------------------------------------ radar
st.divider()
left, right = st.columns([1, 1])

RADAR = {
    "Goalkeeper": ["saves", "goals_conceded", "passes", "duels_won", "rating"],
    "Defender": ["duel_win_pct", "def_actions", "tackles", "interceptions",
                 "passes", "key_passes", "dribbles_won", "fouls_made"],
    "Midfielder": ["passes", "key_passes", "def_actions", "duels_won",
                   "dribbles_won", "np_ga", "interceptions", "fouls_drawn"],
    "Attacker": ["np_goals", "assists", "shots", "key_passes", "dribbles_won",
                 "duels_won", "def_actions", "fouls_drawn"],
}

with left:
    st.markdown("**Metrik profili** (kendi lig+sezon+mevki havuzunda percentile)")
    from scout.scoring.engine import column_for

    mets = RADAR.get(p.pos_group, RADAR["Midfielder"])
    vals, names = [], []
    for m in mets:
        col = column_for(m)
        if col in feats.columns and pd.notna(p.get(col)):
            vals.append(float(p[col]))
            names.append(sh.metric_label(m))
    if vals:
        fig = go.Figure(go.Scatterpolar(
            r=vals + vals[:1], theta=names + names[:1], fill="toself",
            name=p.player_name, line=dict(color=ui.COLORS["primary"], width=2),
            fillcolor="rgba(30,64,175,.15)",
            hovertemplate="%{theta}: %{r:.0f}. percentile<extra></extra>",
        ))
        ui.apply_plotly(fig)
        fig.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0, 100], tickvals=[25, 50, 75, 100],
                                gridcolor=ui.COLORS["border"], tickfont=dict(size=10)),
                angularaxis=dict(gridcolor=ui.COLORS["border"]),
            ),
            showlegend=False, height=420, margin=dict(l=70, r=70, t=24, b=24),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("50 = kendi lig/sezon/mevki havuzunun ortancası.")
    else:
        ui.empty_state("Radar için yeterli metrik yok")

# ------------------------------------------------------------------ roller
with right:
    st.markdown("**Rol skorları** — hangi role en çok uyuyor?")
    mine = scores[
        (scores.player_id == p.player_id)
        & (scores.league_id == p.league_id)
        & (scores.season == p.season)
    ].sort_values("score", ascending=False)

    if mine.empty:
        st.info("Skor bulunamadı.")
    else:
        disp = mine[["role_name", "score", "score_age", "coverage"]].rename(
            columns={"role_name": "Rol", "score": "Skor",
                     "score_age": "Yaşıtlarına göre", "coverage": "Kapsam"}
        ).round(1)
        st.dataframe(disp, hide_index=True, use_container_width=True,
                     column_config={"Skor": st.column_config.ProgressColumn(
                         "Skor", min_value=0, max_value=100, format="%.1f")})

# ------------------------------------------------------------------ waterfall
st.divider()
st.markdown("**Skor neden bu?** — her metriğin katkısı (§5.4)")
if not mine.empty:
    role_pick = st.selectbox("Rol", mine.role_name.tolist())
    row = mine[mine.role_name == role_pick].iloc[0]
    try:
        contrib = json.loads(row.contrib) if isinstance(row.contrib, str) else {}
    except (json.JSONDecodeError, TypeError):
        contrib = {}

    if contrib:
        cdf = (
            pd.DataFrame({"metrik": list(contrib), "katki": list(contrib.values())})
            .assign(metrik=lambda d: d.metrik.map(sh.metric_label))
            .sort_values("katki", ascending=True)
        )
        fig = go.Figure(go.Bar(
            x=cdf.katki, y=cdf.metrik, orientation="h",
            marker_color=ui.COLORS["primary"],
            text=cdf.katki.round(1), textposition="outside",
            hovertemplate="%{y}: %{x:.1f} puan<extra></extra>",
        ))
        ui.apply_plotly(fig)
        fig.update_layout(
            height=max(300, 30 * len(cdf)),
            xaxis_title="skora katkı (puan)", yaxis_title="",
            margin=dict(l=10, r=40, t=8, b=32),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Çubukların toplamı skoru verir: **{row.score:.1f}**. "
            f"Kapsam {row.coverage:.2f} — ağırlığın bu oranı hesaplanabildi."
        )
    else:
        ui.empty_state("Katkı bilgisi yok")

# ------------------------------------------------------------------ eylem
st.divider()
a, b = st.columns([1, 3])
with a:
    takipte = sh.takipte_api(int(p.player_id))
    if st.button("★ Takipten çıkar" if takipte else "Takibe al",
                 type="secondary" if takipte else "primary", width="stretch"):
        added = sh.takip_api_degistir(int(p.player_id), int(p.league_id),
                                      int(p.season), p.player_name)
        st.success("Takip listesine eklendi." if added
                   else "Takip listesinden çıkarıldı.")
with b:
    q = str(p.player_name).replace(" ", "+")
    st.markdown(
        f"**Video ara:** [YouTube](https://www.youtube.com/results?search_query={q}+skills) · "
        f"[Transfermarkt](https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={q})"
    )
    st.caption("Sistem dikkatini yönlendirir, kararı göz testi verir.")



# ------------------------------------------------------- benzer oyuncular
st.divider()
st.subheader("Benzer oyuncular")
st.caption(
    "**Stil** benzerliği — ne yaptığı, ne kadar iyi yaptığı değil. "
    "Ölçüldü: stil komşularının skor farkı 15,3, rastgele oyuncuların 17,5; "
    "yani liste kaliteyi değil oyun tarzını yakalıyor. Kaliteyi kendin süz."
)

bc1, bc2, bc3 = st.columns([1, 1, 1])
with bc1:
    b_ayni_sezon = st.checkbox("Aynı sezon", True,
                               help="Kapalıysa tüm sezonlardan aday aranır.")
with bc2:
    # Varsayilan SINIRSIZ: gizli bir varsayilan filtre sonuclari sessizce
    # daraltir ve kullanici sebebini bilmez. "Bunun gibi ama ucuz" ararken
    # daha yasli bir oyuncu cogu zaman tam da ulasilabilir olandir.
    b_yas = st.slider("Azami yaş", 16.0, 40.0, 40.0, 0.5)
with bc3:
    b_ucuz = st.checkbox(
        "Sadece daha ucuzlar", False,
        help="Transfermarkt değeri bu oyuncununkinden düşük olanlar. "
             "Değeri bilinmeyenler listede kalır — eşleşmemek ucuz olmamak "
             "demek değil.",
    )

havuz = feats.copy()
if b_ayni_sezon:
    havuz = havuz[havuz.season == p.season]
havuz = havuz[(havuz.age_season_end <= b_yas) | (havuz.index == p.name)]
if b_ucuz and "market_value_eur" in havuz.columns and pd.notna(p.get("market_value_eur")):
    havuz = havuz[havuz.market_value_eur.isna()
                  | (havuz.market_value_eur < p.market_value_eur)
                  | (havuz.index == p.name)]

benz = sh.benzer_oyuncular(havuz, p.name, n=8)
if benz.empty:
    ui.empty_state("Benzer oyuncu bulunamadı",
                   "Filtreleri gevşet ya da 'aynı sezon' şartını kaldır.")
else:
    g = pd.DataFrame({
        "Oyuncu": benz.player_name,
        "Yaş": benz.age_season_end.round(1),
        "Takım": benz.team_name,
        "Lig": benz.league_name,
        "Sezon": benz.season.astype(int),
        "Dakika": benz.minutes.astype(int),
        "Benzerlik": benz.benzerlik.round(0),
    })
    if "market_value_eur" in benz.columns:
        g["Değer (€)"] = benz.market_value_eur
    st.dataframe(
        g, hide_index=True, use_container_width=True,
        column_config={
            "Benzerlik": st.column_config.ProgressColumn(
                "Benzerlik", min_value=0, max_value=100, format="%.0f",
                help="100 = aynı oyun tarzı. Kohortun kendi ölçeğine göre "
                     "normalize edilmiştir."),
            "Değer (€)": st.column_config.NumberColumn("Değer (€)", format="%d"),
        },
    )
