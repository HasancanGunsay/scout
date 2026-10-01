"""Oyuncu — tek oyuncu-sezonun bütün görünümü (FAZ 8.4).

Eski "Oyuncu profili" ve "Scout dosyası" sayfaları birleşti: ikisi aynı
oyuncu-sezona iki ayrı açıdan bakıyordu, kullanıcı ikisi arasında gidip
geliyordu. Sekmeler:

  Scout dosyası  iddia, kanıt, bağlam, yörünge, emsal, riskler ve
                 VERİNİN GÖREMEDİĞİ (FAZ 4). Yalnız model iddiası olan
                 oyuncu-sezonlarda (U23, ≥450 dk, doğrulanmış TM eşleşmesi).
  Profil         metrik profili (radar), rol skorları, skorun açıklaması.
  Benzerler      stil olarak en yakın oyuncular (§25).

Oyuncu arama kutusuyla seçilir ya da Havuz / Takip / Keşif'ten
?pid=&lid=&sezon= ile açılır. Listede gezinmenin yeri Havuz.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import _takip_ui as TU
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.features.dosya import katki_tablosu, kor_noktalar, riskler  # noqa: E402
from scout.features.emsal import cumle as emsal_cumle  # noqa: E402
from scout.scoring.engine import column_for  # noqa: E402

import _dosya_metin as MT  # noqa: E402

sh.page_setup(
    "Oyuncu",
    "Bir oyuncu-sezonun bütün görünümü: sistemin iddiası ve onu sınamanın "
    "yolu, metrik profili, benzer oyuncular.",
    "person",
)

KEY = ["player_id", "league_id", "season"]


@st.cache_data(ttl=300)
def _adaylar() -> pd.DataFrame:
    """Model iddiası olan oyuncu-sezonlar (Scout dosyası sekmesi)."""
    try:
        return sh._con().sql("""
            SELECT o.player_id, o.league_id, o.season, o.player_name,
                   o.league_name, o.country, o.kapsam, o.kademe,
                   o.age_season_end AS yas, o.minutes, o.score,
                   o.lig_dk_y1, o.gol_y1, o.en_iyi_lig, o.gozlem_ay,
                   m.model_olasilik, m.model_ham, m.tahmin_turu,
                   e.n AS emsal_n, e.olumlu AS emsal_olumlu, e.oran,
                   e.oran_lo, e.oran_hi, e.lig_taban, e.kaldirac,
                   e.taban_ustunde, e.yeterli,
                   CASE WHEN v.tm_id IS NULL THEN 0 ELSE 1 END AS deger_var,
                   v.deger
            FROM player_outcome o
            LEFT JOIN (
                SELECT o2.player_id, o2.league_id, o2.season, l.tm_id,
                       max_by(pv.market_value_in_eur, pv.date) AS deger
                FROM player_outcome o2
                JOIN player_links l USING (player_id)
                JOIN tm_player_valuations pv ON pv.player_id = l.tm_id
                WHERE pv.date <= o2.sezon_bitis - INTERVAL 1 MONTH
                GROUP BY 1,2,3,4
            ) v USING (player_id, league_id, season)
            LEFT JOIN player_tahmin m USING (player_id, league_id, season)
            LEFT JOIN player_emsal e USING (player_id, league_id, season)
            WHERE m.model_olasilik IS NOT NULL
        """).df()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def _detay(pid: int, lid: int, sez: int) -> dict:
    con = sh._con()
    nat = con.sql(f"""
        SELECT role_name, score, score_age, coverage, contrib, pos_group,
               team_name, minutes_agepct, minutes_pct
        FROM player_natural_role
        WHERE player_id={pid} AND league_id={lid} AND season={sez}
    """).df()
    gecmis = con.sql(f"""
        SELECT season, league_name, round(score,1) skor,
               round(score_age,1) yas_skoru, cast(minutes AS INT) dk,
               round(age_season_end,1) yas
        FROM player_natural_role WHERE player_id={pid} ORDER BY season
    """).df()
    kalite = con.sql(f"""
        SELECT count(*) n FROM league_quality
        WHERE league_id={lid} AND season={sez} AND n_eksik_metrik > 0
    """).df().n[0]
    return {"nat": nat, "gecmis": gecmis, "lig_bozuk": bool(kalite)}


feats = sh.load_features()
scores = sh.load_scores()
adaylar = _adaylar()

# ------------------------------------------------------------------ seçim
etiket = (feats.player_name + " — " + feats.team_name.fillna("?") + " ("
          + feats.league_name + " " + feats.season.astype(int).astype(str) + ")")
anahtar = list(zip(feats.player_id.astype(int), feats.league_id.astype(int),
                   feats.season.astype(int)))
konum_of = {k: i for i, k in enumerate(anahtar)}

try:
    hedef = (int(st.query_params["pid"]), int(st.query_params["lid"]),
             int(st.query_params["sezon"]))
except (KeyError, ValueError):
    hedef = None
if hedef is None and len(adaylar):
    # parametre yoksa: en yeni sezonun en yüksek model iddiası (boş sayfa yok)
    son = adaylar[adaylar.season == adaylar.season.max()]
    t = son.loc[son.model_olasilik.idxmax()]
    hedef = (int(t.player_id), int(t.league_id), int(t.season))

with st.container(border=True):
    sira = np.argsort(etiket.to_numpy(), kind="stable").tolist()
    secenek = etiket.to_numpy()[sira].tolist()
    vars_idx = konum_of.get(hedef) if hedef else None
    secili = st.selectbox(
        "Oyuncu ara", secenek,
        index=sira.index(vars_idx) if vars_idx is not None else None,
        placeholder="isim yazmaya başla…",
        help="Bütün oyuncu-sezonlar. Listede gezinmek için Havuz.",
        key=f"oy_ara_{hedef}")
if secili is None:
    ui.empty_state("Oyuncu seçilmedi",
                   "Yukarıdaki kutuya isim yaz ya da Havuz'dan bir oyuncuya tıkla.")
    st.stop()

p = feats.iloc[sira[secenek.index(secili)]]
k3 = (int(p.player_id), int(p.league_id), int(p.season))
aday = adaylar[(adaylar.player_id == k3[0]) & (adaylar.league_id == k3[1])
               & (adaylar.season == k3[2])] if len(adaylar) else adaylar

# ------------------------------------------------------------------ başlık
rozet = [(sh.MEVKI_TR.get(p.pos_group, p.pos_group), "info")]
if pd.notna(p.get("age_season_end")):
    rozet.append((f"{p.age_season_end:.1f} yaş", "mute"))
if p.minutes >= 1800:
    rozet.append(("Tam sezon", "ok"))
elif p.minutes >= 900:
    rozet.append(("Yeterli dakika", "ok"))
elif p.minutes >= 450:
    rozet.append(("Sınırlı dakika", "warn"))
else:
    rozet.append(("Çok az dakika — skorlar güvenilmez", "risk"))
# Guven sinyali (§18.4): dakika rozetinden FARKLI - "kulubu ona guveniyor mu"
_g = p.get("minutes_agepct")
if pd.isna(_g):
    _g = p.get("minutes_pct")
if pd.notna(_g):
    _et, _kind = sh.guven_seviyesi(float(_g))
    rozet.append((f"Güven: {_et} (%{float(_g):.0f})", _kind))
if len(aday):
    a0 = aday.iloc[0]
    rozet.append(("Düşük görünürlük" if a0.kapsam == "sicrama_only"
                  else "İzlenen lig", "warn" if a0.kapsam == "sicrama_only"
                  else "mute"))
    rozet.append((f"Model %{100 * a0.model_olasilik:.0f}", "info"))
ui.oyuncu_basligi(p.player_name,
                  f"{p.team_name} · {p.league_name} {int(p.season)}", rozet)

tam = " ".join(str(x) for x in (p.get("firstname"), p.get("lastname"))
               if isinstance(x, str) and x.strip()) or str(p.player_name)
e1, e2 = st.columns([1, 2.4], vertical_alignment="center")
with e1:
    takipte = sh.takipte_api(int(p.player_id))
    if st.button("★ Takipten çıkar" if takipte else "Takibe al",
                 type="secondary" if takipte else "primary", width="stretch",
                 icon=None if takipte else ":material/bookmark_add:"):
        eklendi = sh.takip_api_degistir(*k3, p.player_name)
        st.toast("Takip listesine eklendi." if eklendi
                 else "Takip listesinden çıkarıldı.")
        st.rerun()
with e2:
    # 8.3: kısa ad ("T. Abed") aramayı bozar - API ad+soyad; TM profili
    # yalnız doğrulanmış eşleşmede (player_meta, §60)
    TU.baglantilar(tam, p.team_name, p.get("tm_url"))
st.caption(f"[YouTube'da izle](https://www.youtube.com/results?search_query="
           f"{quote_plus(tam + ' skills')}) · Sistem dikkatini yönlendirir, "
           "kararı göz testi verir.")

if p.get("multi_team"):
    st.info(f"Sezon içinde kulüp değiştirmiş: {p.get('all_teams', '—')}. "
            "API bu durumda sezon toplamlarını her iki kulüpte tekrarlayabiliyor; "
            "en çok dakikalı kayıt esas alındı.", icon="↔️")

tab_dosya, tab_profil, tab_benzer = st.tabs(
    ["Scout dosyası", "Profil", "Benzer oyuncular"])

# ============================================================ SCOUT DOSYASI
with tab_dosya:
    if aday.empty:
        ui.empty_state(
            "Bu oyuncu-sezon için model iddiası yok",
            "İddia yalnız U23, ≥450 dakika ve Transfermarkt eşleşmesi "
            "doğrulanmış oyuncu-sezonlarda üretilir (PLAN §60). Profil ve "
            "benzerler sekmeleri yine de çalışır.")
    else:
        r = aday.iloc[0].to_dict()
        d = _detay(*k3)
        nat = d["nat"]
        r["lig_adi"] = r["league_name"]
        r["score_age"] = (float(nat.score_age.iloc[0]) if len(nat)
                          and pd.notna(nat.score_age.iloc[0]) else float("nan"))
        r["coverage"] = float(nat.coverage.iloc[0]) if len(nat) else float("nan")
        r["lig_bozuk"] = d["lig_bozuk"]
        r["n_sezon"] = len(d["gecmis"])
        pos = nat.pos_group.iloc[0] if len(nat) else ""

        # HTML div icinde markdown render OLMUYOR - iddia kalin yazi iceriyor,
        # st.info markdown'i isliyor ve gorsel ayrimi da koruyor.
        st.info(MT.iddia(r))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Model olasılığı", f"%{100 * r['model_olasilik']:.0f}",
                  help=MT.olasilik_notu(r))
        c2.metric("Ligin tabanı", f"%{100 * r['lig_taban']:.0f}"
                  if pd.notna(r.get("lig_taban")) else "—")
        c3.metric("Rol skoru", f"{r['score']:.1f}" if pd.notna(r["score"]) else "—")
        c4.metric("Dakika", f"{int(r['minutes'])}")

        ui.section("Kanıt", "Skoru hangi metrikler taşıyor (waterfall özeti).")
        katki = pd.DataFrame()
        if len(nat) and pd.notna(nat.contrib.iloc[0]):
            try:
                katki = katki_tablosu(json.loads(nat.contrib.iloc[0]))
            except (json.JSONDecodeError, TypeError):
                katki = pd.DataFrame()
        if len(katki):
            katki["metrik"] = katki.metrik.map(sh.metric_label)
            st.dataframe(katki.style.format({"katki": "{:+.1f}"}),
                         width="stretch", hide_index=True)
            st.caption(f"Doğal rol: **{nat.role_name.iloc[0]}** · kapsam "
                       f"{nat.coverage.iloc[0]:.2f} (ağırlığın bu oranı "
                       "hesaplanabildi)")
        else:
            st.caption("Katkı ayrıştırması yok.")

        ui.section("Bağlam", "Aynı sayı, farklı ligde farklı şey demek.")
        b1, b2 = st.columns(2)
        with b1:
            if len(nat) and pd.notna(nat.minutes_agepct.iloc[0]):
                st.metric("Yaşıtlarına göre dakika payı",
                          f"%{nat.minutes_agepct.iloc[0]:.0f}",
                          help="19 yaşında %70 dakika almak dikkate değer, "
                               "28 yaşında sıradan.")
        with b2:
            sh.lig_zorlugu_notu([int(r["league_id"])])

        ui.section("Yörünge", "Sezon sezon — ve sonradan gerçekten ne olduğu.")
        g = d["gecmis"]
        if len(g) > 1:
            st.dataframe(g, width="stretch", hide_index=True)
        else:
            st.caption("Tek sezon verisi var — yörünge çizilemiyor.")
        st.markdown(f"**Sonuç:** {MT.yorunge_cumlesi(r)}")
        if pd.notna(r.get("gozlem_ay")) and r["gozlem_ay"] < 12:
            st.warning(f"Gözlem penceresi henüz {r['gozlem_ay']:.0f} ay — "
                       f"12 aylık sonuç tamamlanmadı.")

        ui.section("Emsal oranı", "Bu profildekiler ne oldu (§40).")
        if r.get("yeterli"):
            # Sorguda e.n / e.olumlu cakismasin diye yeniden adlandirildi
            st.markdown(emsal_cumle({**r, "n": r["emsal_n"],
                                     "olumlu": r["emsal_olumlu"]}))
            if not r.get("taban_ustunde"):
                st.caption(":warning: Güven aralığı ligin tabanını kapsıyor — "
                           "bu profil tabandan ayırt edilemiyor. Vakaların "
                           "çoğunda durum böyle; n=40'ın dürüst sınırı.")
        else:
            st.caption("Emsal grubu yetersiz — oran üretilmedi.")

        ui.section("Riskler", "Otomatik bayraklar. Boş liste 'risk yok' demek DEĞİL.")
        rs = [MT.risk_cumlesi(k, b) for k, b in riskler(r)]
        for x in rs:
            st.markdown(f"- {x}")
        if not rs:
            st.caption("Otomatik bayrak yok.")

        ui.section("Ne izlemelisin", "Verinin göremediği. Gözlemin sistemin "
                                     "tekrarı değil, DEVAMI olması için.")
        kor = [MT.kor_cumlesi(k) for k in kor_noktalar(pos)]
        for x in kor:
            st.markdown(f"- {x}")

        md = [f"# {r['player_name']}", "", f"**İddia:** {MT.iddia(r)}", "",
              f"- Lig: {r['league_name']} {int(r['season'])}",
              f"- Yaş: {r['yas']:.1f} · Dakika: {int(r['minutes'])}",
              f"- Model olasılığı: %{100 * r['model_olasilik']:.0f}", "",
              "## Yörünge", MT.yorunge_cumlesi(r), "", "## Emsal",
              emsal_cumle({**r, "n": r["emsal_n"], "olumlu": r["emsal_olumlu"]})
              if r.get("yeterli") else "Yetersiz grup.", "",
              "## Riskler"] + [f"- {x}" for x in rs] + ["", "## Ne izlemelisin"] \
            + [f"- {x}" for x in kor]
        st.download_button("Dosyayı markdown olarak indir", "\n".join(md),
                           file_name=f"scout_{r['player_name'].replace(' ', '_')}.md",
                           mime="text/markdown")

# ================================================================== PROFİL
RADAR = {
    "Goalkeeper": ["saves", "goals_conceded", "passes", "duels_won", "rating"],
    "Defender": ["duel_win_pct", "def_actions", "tackles", "interceptions",
                 "passes", "key_passes", "dribbles_won", "fouls_made"],
    "Midfielder": ["passes", "key_passes", "def_actions", "duels_won",
                   "dribbles_won", "np_ga", "interceptions", "fouls_drawn"],
    "Attacker": ["np_goals", "assists", "shots", "key_passes", "dribbles_won",
                 "duels_won", "def_actions", "fouls_drawn"],
}

with tab_profil:
    k = st.columns(5)
    k[0].metric("Mevki", sh.MEVKI_TR.get(p.position, p.position or "—"))
    k[1].metric("Dakika", f"{int(p.minutes)}")
    k[2].metric("Maç", f"{int(p.apps)}")
    k[3].metric("Reyting", f"{p.rating:.2f}" if pd.notna(p.rating) else "—")
    k[4].metric("Boy", f"{int(p.height_cm)} cm" if pd.notna(p.height_cm) else "—")

    if "market_value_eur" in feats.columns and (
            pd.notna(p.get("market_value_eur")) or pd.notna(p.get("contract_until"))):
        m = st.columns(5)
        mv, pk, cu = (p.get("market_value_eur"), p.get("peak_market_value_eur"),
                      p.get("contract_until"))
        m[0].metric("Piyasa değeri (bugün)",
                    f"€{int(mv):,}".replace(",", ".") if pd.notna(mv) else "—")
        m[1].metric("Zirve değer",
                    f"€{int(pk):,}".replace(",", ".") if pd.notna(pk) else "—")
        m[2].metric("Sözleşme", str(cu)[:10] if pd.notna(cu) else "—")
        m[3].metric("Ayak", p.get("foot") or "—")
        m[4].metric("Milli maç", int(p.international_caps)
                    if pd.notna(p.get("international_caps")) else "—")
        st.caption(f"Transfermarkt eşleşmesi: {p.get('match_confidence')} seviyesi.")
    elif "market_value_eur" in feats.columns:
        st.caption("Doğrulanmış Transfermarkt eşleşmesi yok — piyasa değeri ve "
                   "sözleşme bilgisi gösterilmiyor. Oyuncunun kalitesiyle "
                   "ilgili bir şey söylemez.")

    sh.coverage_warning([p.league_id])
    sh.veri_kalitesi_uyarisi([p.league_id])

    left, right = st.columns(2)
    with left:
        st.markdown("**Metrik profili** (kendi lig+sezon+mevki havuzunda percentile)")
        vals, names = [], []
        for mt in RADAR.get(p.pos_group, RADAR["Midfielder"]):
            col = column_for(mt)
            if col in feats.columns and pd.notna(p.get(col)):
                vals.append(float(p[col]))
                names.append(sh.metric_label(mt))
        if vals:
            fig = go.Figure(go.Scatterpolar(
                r=vals + vals[:1], theta=names + names[:1], fill="toself",
                name=p.player_name, line=dict(color=ui.COLORS["primary"], width=2),
                fillcolor="rgba(30,64,175,.15)",
                hovertemplate="%{theta}: %{r:.0f}. percentile<extra></extra>"))
            ui.apply_plotly(fig)
            fig.update_layout(
                polar=dict(bgcolor="rgba(0,0,0,0)",
                           radialaxis=dict(visible=True, range=[0, 100],
                                           tickvals=[25, 50, 75, 100],
                                           gridcolor=ui.COLORS["border"],
                                           tickfont=dict(size=10)),
                           angularaxis=dict(gridcolor=ui.COLORS["border"])),
                showlegend=False, height=420, margin=dict(l=70, r=70, t=24, b=24))
            st.plotly_chart(fig, width="stretch")
            st.caption("50 = kendi lig/sezon/mevki havuzunun ortancası.")
        else:
            ui.empty_state("Radar için yeterli metrik yok")

    mine = scores[(scores.player_id == p.player_id)
                  & (scores.league_id == p.league_id)
                  & (scores.season == p.season)].sort_values("score", ascending=False)
    with right:
        st.markdown("**Rol skorları** — hangi role en çok uyuyor?")
        if mine.empty:
            st.info("Skor bulunamadı.")
        else:
            st.dataframe(
                mine[["role_name", "score", "score_age", "coverage"]].rename(
                    columns={"role_name": "Rol", "score": "Skor",
                             "score_age": "Yaşıtlarına göre",
                             "coverage": "Kapsam"}).round(1),
                hide_index=True, width="stretch",
                column_config={"Skor": st.column_config.ProgressColumn(
                    "Skor", min_value=0, max_value=100, format="%.1f")})

    st.markdown("**Skor neden bu?** — her metriğin katkısı (§5.4)")
    if not mine.empty:
        role_pick = st.selectbox("Rol", mine.role_name.tolist())
        row = mine[mine.role_name == role_pick].iloc[0]
        try:
            contrib = json.loads(row.contrib) if isinstance(row.contrib, str) else {}
        except (json.JSONDecodeError, TypeError):
            contrib = {}
        if contrib:
            cdf = (pd.DataFrame({"metrik": list(contrib),
                                 "katki": list(contrib.values())})
                   .assign(metrik=lambda x: x.metrik.map(sh.metric_label))
                   .sort_values("katki", ascending=True))
            fig = go.Figure(go.Bar(
                x=cdf.katki, y=cdf.metrik, orientation="h",
                marker_color=ui.COLORS["primary"], text=cdf.katki.round(1),
                textposition="outside",
                hovertemplate="%{y}: %{x:.1f} puan<extra></extra>"))
            ui.apply_plotly(fig)
            fig.update_layout(height=max(300, 30 * len(cdf)),
                              xaxis_title="skora katkı (puan)", yaxis_title="",
                              margin=dict(l=10, r=40, t=8, b=32))
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Çubukların toplamı skoru verir: **{row.score:.1f}**. "
                       f"Kapsam {row.coverage:.2f} — ağırlığın bu oranı "
                       "hesaplanabildi.")
        else:
            ui.empty_state("Katkı bilgisi yok")

# ================================================================ BENZERLER
with tab_benzer:
    st.caption(
        "**Stil** benzerliği — ne yaptığı, ne kadar iyi yaptığı değil. "
        "Ölçüldü: stil komşularının skor farkı 15,3, rastgele oyuncuların 17,5; "
        "yani liste kaliteyi değil oyun tarzını yakalıyor. Kaliteyi kendin süz.")
    bc1, bc2, bc3 = st.columns(3)
    b_ayni_sezon = bc1.checkbox("Aynı sezon", True,
                                help="Kapalıysa tüm sezonlardan aday aranır.")
    # Varsayilan SINIRSIZ: gizli varsayilan filtre sonuclari sessizce daraltir.
    b_yas = bc2.slider("Azami yaş", 16.0, 40.0, 40.0, 0.5, format="%.1f")
    b_ucuz = bc3.checkbox(
        "Sadece daha ucuzlar", False,
        help="Transfermarkt değeri bu oyuncununkinden düşük olanlar. Değeri "
             "bilinmeyenler listede kalır — eşleşmemek ucuz olmamak demek değil.")
    havuz = feats.copy()
    if b_ayni_sezon:
        havuz = havuz[havuz.season == p.season]
    havuz = havuz[(havuz.age_season_end <= b_yas) | (havuz.index == p.name)]
    if (b_ucuz and "market_value_eur" in havuz.columns
            and pd.notna(p.get("market_value_eur"))):
        havuz = havuz[havuz.market_value_eur.isna()
                      | (havuz.market_value_eur < p.market_value_eur)
                      | (havuz.index == p.name)]
    benz = sh.benzer_oyuncular(havuz, p.name, n=8)
    if benz.empty:
        ui.empty_state("Benzer oyuncu bulunamadı",
                       "Filtreleri gevşet ya da 'aynı sezon' şartını kaldır.")
    else:
        g = pd.DataFrame({
            "Oyuncu": benz.player_name, "Yaş": benz.age_season_end.round(1),
            "Takım": benz.team_name, "Lig": benz.league_name,
            "Sezon": benz.season.astype(int), "Dakika": benz.minutes.astype(int),
            "Benzerlik": benz.benzerlik.round(0)})
        if "market_value_eur" in benz.columns:
            g["Değer (€)"] = benz.market_value_eur
        st.dataframe(g, hide_index=True, width="stretch", column_config={
            "Benzerlik": st.column_config.ProgressColumn(
                "Benzerlik", min_value=0, max_value=100, format="%.0f",
                help="100 = aynı oyun tarzı. Kohortun kendi ölçeğine göre "
                     "normalize edilmiştir."),
            "Değer (€)": st.column_config.NumberColumn("Değer (€)", format="%d")})
