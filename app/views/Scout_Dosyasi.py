"""Scout Dosyası — veri dökümü değil, İDDİA (FAZ 4).

Bu sayfa projenin çıkış noktası: sistem bir iddia üretir, kullanıcı gidip
doğrular. Yedi bölüm — iddia, kanıt, bağlam, yörünge, emsal, riskler,
ve **verinin göremediği**.

Son bölüm kasıtlı: sistem nerede kör olduğunu söylemezse, gözlem sistemin
tekrarı olur. Amaç tersi — gözlem sistemin devamı olsun.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.features.dosya import katki_tablosu, kor_noktalar, riskler  # noqa: E402
from scout.features.emsal import cumle as emsal_cumle  # noqa: E402

import _dosya_metin as MT  # noqa: E402

sh.page_setup(
    "Scout Dosyası",
    "Tek ekranda bir iddia ve onu sınamanın yolu. Sayı değil, gerekçe.",
    "fact_check",
)


@st.cache_data(ttl=300)
def _adaylar() -> pd.DataFrame:
    con = sh._con()
    try:
        return con.sql("""
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


df = _adaylar()
if df.empty:
    ui.empty_state(
        "Model tahminleri yok",
        "Önce `python scripts/build_ranking.py` ve "
        "`python scripts/build_emsal.py` çalıştırılmalı.",
    )
    st.stop()

# ------------------------------------------------------------------ seçim
# Havuz kartından gelinirse (?pid=&lid=&sezon=) o oyuncu seçili açılır (8.1)
try:
    hedef = (int(st.query_params["pid"]), int(st.query_params["lid"]),
             int(st.query_params["sezon"]))
except (KeyError, ValueError):
    hedef = None

with st.sidebar:
    st.header("Aday seç")
    sezonlar = sorted(df.season.unique(), reverse=True)
    sezon = st.selectbox("Sezon", sezonlar,
                         index=sezonlar.index(hedef[2])
                         if hedef and hedef[2] in sezonlar else 0)
    alt = df[df.season == sezon]

    kapsam = st.radio(
        "Lig türü", ["Hepsi", "Düşük görünürlük", "İzlenen ligler"],
        help="'Düşük görünürlük' = Transfermarkt'ta oyuncu bazında "
             "izlenmeyen ligler. Wonderkid avının asıl alanı, ama sonuç "
             "ölçümü orada kısmi (§38.4).",
    )
    if kapsam == "Düşük görünürlük":
        alt = alt[alt.kapsam == "sicrama_only"]
    elif kapsam == "İzlenen ligler":
        alt = alt[alt.kapsam == "tam"]

    max_yas = st.slider("Azami yaş", 17.0, 23.0, 23.0, 0.5)
    alt = alt[alt.yas <= max_yas]

    if alt.empty:
        ui.empty_state("Aday yok", "Filtreleri gevşetin.")
        st.stop()

    alt = alt.sort_values("model_olasilik", ascending=False)
    etiket = (alt.player_name + " · " + alt.league_name
              + " (%" + (100 * alt.model_olasilik).round(0).astype(int).astype(str) + ")")
    konum = 0
    if hedef:
        es = ((alt.player_id == hedef[0]) & (alt.league_id == hedef[1])).to_numpy()
        konum = int(es.argmax()) if es.any() else 0
    sec = st.selectbox("Oyuncu", etiket.tolist(), index=konum)
    r = alt.iloc[etiket.tolist().index(sec)].to_dict()

d = _detay(int(r["player_id"]), int(r["league_id"]), int(r["season"]))
nat = d["nat"]
r["lig_adi"] = r["league_name"]
r["score_age"] = float(nat.score_age.iloc[0]) if len(nat) and pd.notna(
    nat.score_age.iloc[0]) else float("nan")
r["coverage"] = float(nat.coverage.iloc[0]) if len(nat) else float("nan")
r["lig_bozuk"] = d["lig_bozuk"]
r["n_sezon"] = len(d["gecmis"])
pos = nat.pos_group.iloc[0] if len(nat) else ""

# ------------------------------------------------------------------ İDDİA
st.markdown(f"## {r['player_name']}")
# HTML div icinde markdown render OLMUYOR - iddia kalin yazi iceriyor,
# st.info markdown'i isliyor ve gorsel ayrimi da koruyor.
st.info(MT.iddia(r))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Model olasılığı", f"%{100 * r['model_olasilik']:.0f}",
          help=MT.olasilik_notu(r))
c2.metric("Ligin tabanı",
          f"%{100 * r['lig_taban']:.0f}" if pd.notna(r.get("lig_taban")) else "—")
c3.metric("Rol skoru", f"{r['score']:.1f}" if pd.notna(r["score"]) else "—")
c4.metric("Dakika", f"{int(r['minutes'])}")

# ----------------------------------------------------------------- KANIT
ui.section("Kanıt", "Skoru hangi metrikler taşıyor (waterfall özeti).")
if len(nat) and pd.notna(nat.contrib.iloc[0]):
    try:
        katki = katki_tablosu(json.loads(nat.contrib.iloc[0]))
    except (json.JSONDecodeError, TypeError):
        katki = pd.DataFrame()
    if len(katki):
        katki["metrik"] = katki.metrik.map(sh.metric_label)
        st.dataframe(katki.style.format({"katki": "{:+.1f}"}),
                     use_container_width=True, hide_index=True)
        st.caption(
            f"Doğal rol: **{nat.role_name.iloc[0]}** · kapsam "
            f"{nat.coverage.iloc[0]:.2f} (ağırlığın bu oranı hesaplanabildi)")
else:
    st.caption("Katkı ayrıştırması yok.")

# --------------------------------------------------------------- BAĞLAM
ui.section("Bağlam", "Aynı sayı, farklı ligde farklı şey demek.")
b1, b2 = st.columns(2)
with b1:
    if len(nat) and pd.notna(nat.minutes_agepct.iloc[0]):
        st.metric("Yaşıtlarına göre dakika payı",
                  f"%{nat.minutes_agepct.iloc[0]:.0f}",
                  help="19 yaşında %70 dakika almak dikkate değer, "
                       "28 yaşında sıradan.")
    st.caption(f"Takım: {nat.team_name.iloc[0] if len(nat) else '—'}")
with b2:
    sh.lig_zorlugu_notu([int(r["league_id"])])
sh.veri_kalitesi_uyarisi([int(r["league_id"])])

# -------------------------------------------------------------- YÖRÜNGE
ui.section("Yörünge", "Sezon sezon — ve sonradan gerçekten ne olduğu.")
g = d["gecmis"]
if len(g) > 1:
    st.dataframe(g, use_container_width=True, hide_index=True)
else:
    st.caption("Tek sezon verisi var — yörünge çizilemiyor.")

st.markdown(f"**Sonuç:** {MT.yorunge_cumlesi(r)}")
if pd.notna(r.get("gozlem_ay")) and r["gozlem_ay"] < 12:
    st.warning(f"Gözlem penceresi henüz {r['gozlem_ay']:.0f} ay — "
               f"12 aylık sonuç tamamlanmadı.")

# ---------------------------------------------------------------- EMSAL
ui.section("Emsal oranı", "Bu profildekiler ne oldu (§40).")
if r.get("yeterli"):
    # Sorguda e.n / e.olumlu cakismasin diye yeniden adlandirildi;
    # cumle() ham anahtarlari bekliyor.
    st.markdown(emsal_cumle({**r, "n": r["emsal_n"],
                             "olumlu": r["emsal_olumlu"]}))
    if not r.get("taban_ustunde"):
        st.caption(":warning: Güven aralığı ligin tabanını kapsıyor — bu "
                   "profil tabandan ayırt edilemiyor. Vakaların %86'sında "
                   "durum böyle; n=40'ın dürüst sınırı.")
else:
    st.caption("Emsal grubu yetersiz — oran üretilmedi.")

# -------------------------------------------------------------- RİSKLER
ui.section("Riskler", "Otomatik bayraklar. Boş liste 'risk yok' demek DEĞİL.")
rs = [MT.risk_cumlesi(k, b) for k, b in riskler(r)]
if rs:
    for x in rs:
        st.markdown(f"- {x}")
else:
    st.caption("Otomatik bayrak yok.")

# ------------------------------------------------------- NE İZLEMELİSİN
ui.section("Ne izlemelisin",
           "Verinin göremediği. Gözlemin sistemin tekrarı değil, "
           "DEVAMI olması için.")
kor = [MT.kor_cumlesi(k) for k in kor_noktalar(pos)]
for x in kor:
    st.markdown(f"- {x}")

# --------------------------------------------------------------- DIŞA AKTAR
st.divider()
md = [f"# {r['player_name']}", "", f"**İddia:** {MT.iddia(r)}", "",
      f"- Lig: {r['league_name']} {int(r['season'])}",
      f"- Yaş: {r['yas']:.1f} · Dakika: {int(r['minutes'])}",
      f"- Model olasılığı: %{100 * r['model_olasilik']:.0f}", "",
      "## Yörünge", MT.yorunge_cumlesi(r), "",
      "## Emsal",
      emsal_cumle({**r, "n": r["emsal_n"], "olumlu": r["emsal_olumlu"]})
      if r.get("yeterli") else "Yetersiz grup.", "",
      "## Riskler"] + [f"- {x}" for x in rs] + ["", "## Ne izlemelisin"] \
     + [f"- {x}" for x in kor]
st.download_button("Dosyayı markdown olarak indir", "\n".join(md),
                   file_name=f"scout_{r['player_name'].replace(' ', '_')}.md",
                   mime="text/markdown")
