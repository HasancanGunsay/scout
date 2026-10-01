"""Shortlist ve Scout Raporu - §1.8 geri besleme döngüsü.

Bu sayfa sistemin en önemli parçası: senin kararların buradan sisteme girer.
Yeterli rapor birikince (§5.3 Katman 5) senin beğeni örüntünü öğrenen
kişisel bir model eğitilebilir.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import pandas as pd
import streamlit as st

sh.page_setup("Shortlist ve scout raporu", "İzleme listen ve göz testi notların. Bu sayfa sistemin senden öğrendiği yerdir.", "fact_check")

feats = sh.load_features()
short = sh.get_shortlist()
reports = sh.get_reports()

tab1, tab2, tab3 = st.tabs(["Shortlist", "Rapor yaz", "Rapor geçmişi"])

# ------------------------------------------------------------------ shortlist
with tab1:
    if not short:
        st.info("Shortlist boş. Keşif veya Profil ekranından oyuncu ekle.")
    else:
        sdf = pd.DataFrame(short)
        n_rep = {(r["player_id"], r["season"]) for r in reports}
        sdf["rapor_var"] = sdf.apply(
            lambda r: "✅" if (r.player_id, r.season) in n_rep else "—", axis=1
        )
        disp = sdf.rename(columns={
            "player_name": "Oyuncu", "team_name": "Takım", "age": "Yaş",
            "role_name": "Rol", "score": "Skor", "minutes": "Dakika",
            "season": "Sezon", "rapor_var": "Rapor",
        })[["Oyuncu", "Yaş", "Takım", "Sezon", "Rol", "Dakika", "Skor", "Rapor"]]
        st.dataframe(disp.round(1), hide_index=True, use_container_width=True)

        st.download_button(
            "Shortlist'i indir (CSV)",
            disp.to_csv(index=False).encode("utf-8-sig"),
            f"shortlist_{date.today()}.csv",
            "text/csv",
        )

        st.divider()
        rm = st.selectbox("Listeden çıkar", ["—"] + sdf.player_name.tolist())
        if rm != "—" and st.button("Çıkar"):
            row = sdf[sdf.player_name == rm].iloc[0]
            sh.toggle_shortlist({
                "player_id": int(row.player_id), "league_id": int(row.league_id),
                "season": int(row.season),
            })
            st.rerun()

# ------------------------------------------------------------------ rapor yaz
with tab2:
    st.markdown(
        "İzledikten sonra doldur. **Veriyle ölçülemeyen şeyleri buraya yazıyorsun** — "
        "karakter, oyun zekası, fiziksel görünüm, taktik disiplin (§1.7)."
    )
    if not short:
        st.info("Önce shortlist'e oyuncu ekle.")
    else:
        sdf = pd.DataFrame(short)
        who = st.selectbox(
            "Oyuncu",
            sdf.apply(lambda r: f"{r.player_name} ({r.team_name}, {int(r.season)})",
                      axis=1).tolist(),
        )
        row = sdf.iloc[[f"{r.player_name} ({r.team_name}, {int(r.season)})"
                        for _, r in sdf.iterrows()].index(who)]

        with st.form("scout_report"):
            c1, c2 = st.columns(2)
            with c1:
                watched = st.date_input("İzleme tarihi", date.today())
                minutes_watched = st.number_input("Kaç dakika izledin", 0, 500, 90, 15)
                verdict = st.select_slider(
                    "Genel karar",
                    ["Takip etme", "İzlemeye devam", "İlgilen", "Öncelikli", "Hemen al"],
                    value="İzlemeye devam",
                )
            with c2:
                st.caption("1 = zayıf, 5 = seçkin")
                technique = st.slider("Teknik", 1, 5, 3)
                physical = st.slider("Fizik / atletizm", 1, 5, 3)
                mental = st.slider("Oyun zekası / karar", 1, 5, 3)
                character = st.slider("Karakter / mücadele", 1, 5, 3)

            strengths = st.text_area("Güçlü yönler", height=90)
            weaknesses = st.text_area("Zayıf yönler", height=90)
            notes = st.text_area("Notlar (bağlam, sakatlık, tutum, maç durumu...)", height=90)

            agree = st.radio(
                "Sistemin skoru sana doğru geldi mi?",
                ["Evet, hak ediyor", "Abartmış", "Hafife almış", "Emin değilim"],
                horizontal=True,
                help="Bu cevap, sistemin zamanla senin gözünü öğrenmesini sağlar (§5.3).",
            )

            if st.form_submit_button("Raporu kaydet", type="primary"):
                sh.add_report({
                    "player_id": int(row.player_id), "league_id": int(row.league_id),
                    "season": int(row.season), "player_name": row.player_name,
                    "team_name": row.team_name,
                    "system_score": float(row.score), "role": row.role_name,
                    "watched_date": str(watched), "minutes_watched": int(minutes_watched),
                    "verdict": verdict, "technique": technique, "physical": physical,
                    "mental": mental, "character": character,
                    "strengths": strengths, "weaknesses": weaknesses, "notes": notes,
                    "score_agreement": agree,
                    "created": str(date.today()),
                })
                st.success("Rapor kaydedildi.")
                st.rerun()

# ------------------------------------------------------------------ gecmis
with tab3:
    if not reports:
        st.info("Henüz rapor yok.")
    else:
        rdf = pd.DataFrame(reports)
        st.metric("Toplam rapor", len(rdf))

        disp = rdf[["player_name", "team_name", "season", "watched_date", "verdict",
                    "technique", "physical", "mental", "character",
                    "system_score", "score_agreement"]].rename(columns={
            "player_name": "Oyuncu", "team_name": "Takım", "season": "Sezon",
            "watched_date": "İzleme", "verdict": "Karar", "technique": "Tek",
            "physical": "Fiz", "mental": "Zek", "character": "Kar",
            "system_score": "Sistem skoru", "score_agreement": "Skor doğru mu",
        })
        st.dataframe(disp.round(1), hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Sistem seninle ne kadar uyuşuyor?")
        st.caption(
            "Yeterli rapor birikince bu tablo, sistemin hangi durumlarda yanıldığını "
            "gösterir ve ağırlıkların yeniden kalibrasyonuna temel olur."
        )
        st.dataframe(
            rdf.groupby("score_agreement").agg(
                rapor=("player_name", "count"),
                ort_sistem_skoru=("system_score", "mean"),
            ).round(1).reset_index(),
            hide_index=True, use_container_width=True,
        )

        st.download_button(
            "Raporları indir (CSV)",
            rdf.to_csv(index=False).encode("utf-8-sig"),
            f"scout_raporlari_{date.today()}.csv", "text/csv",
        )

