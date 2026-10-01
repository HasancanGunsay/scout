"""Eşleşme kuyruğu - §1.6 manuel onay.

Otomatik eşleştirici, emin olamadığı vakaları buraya bırakır. Sen karar
verirsin, karar kalıcı olarak saklanır ve bir daha sorulmaz.

Neden otomatik kabul etmiyoruz: yanlış eşleşme = yanlış piyasa değeri ve
yanlış sözleşme tarihi. Bu, eksik bilgiden daha zararlı — seni yanlış
oyuncunun peşine düşürür.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import pandas as pd
import streamlit as st

sh.page_setup("Eşleşme kuyruğu", "Otomatik eşleştiricinin emin olamadığı vakalar. Kararın kalıcı olarak saklanır.", "link")

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "reports" / "eslesme_kararlari.json"


def load_dec() -> dict:
    if DECISIONS.exists():
        try:
            return json.loads(DECISIONS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_dec(d: dict) -> None:
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


if not sh.table_exists("player_links"):
    st.info("Henüz eşleştirme çalıştırılmamış. `scripts/build_links.py` çalıştır.")
    st.stop()

links = sh._con().sql("SELECT * FROM player_links").df()
dec = load_dec()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam oyuncu", len(links))
c2.metric("Otomatik kabul", int(links.confidence.isin(["A", "B"]).sum()))
c3.metric("Kuyrukta", int((links.confidence == "C").sum()))
c4.metric("Karar verilmiş", len(dec))

st.caption(
    "Transfermarkt CC0 veri seti Brezilya Serie B'nin yalnızca ~%56'sını kapsıyor. "
    "'Aday yok' olarak işaretlenenler algoritma hatası değil — o oyuncu veri setinde "
    "gerçekten mevcut değil ve manuel olarak da bulunamaz."
)

st.divider()

queue = links[(links.confidence == "C") & (~links.player_id.astype(str).isin(dec))]

if queue.empty:
    st.success("Kuyruk boş. Karar bekleyen eşleşme yok.")
else:
    st.subheader(f"Karar bekleyen: {len(queue)}")
    st.caption(
        "Sol taraf API-Football'daki isim, sağ taraf Transfermarkt adayı. "
        "Aynı kişi mi?"
    )

    row = queue.iloc[0]
    box = st.container(border=True)
    with box:
        a, b = st.columns(2)
        with a:
            st.markdown("**API-Football**")
            st.markdown(f"### {row.player_name}")
            st.text(f"doğum: {row.birth_date}")
        with b:
            st.markdown("**Transfermarkt adayı**")
            st.markdown(f"### {row.tm_name}")
            st.text(f"kulüp: {row.get('tm_club') or '—'}")

        st.caption(
            f"isim benzerliği **{row.name_score:.0f}/100** · "
            f"kulüp benzerliği {row.get('club_score') or 0:.0f}/100 · "
            f"aynı doğum tarihinde **{int(row.n_candidates)}** aday"
        )

        x, y, z = st.columns(3)
        if x.button("✅ Aynı kişi", type="primary", use_container_width=True):
            # aday kimligi aday_tm_id'de: tm_id yalniz kabulde dolu (§60)
            aday = row.get("aday_tm_id", row.tm_id)
            dec[str(int(row.player_id))] = {"tm_id": int(aday), "action": "accept"}
            save_dec(dec)
            st.rerun()
        if y.button("❌ Farklı kişi", use_container_width=True):
            dec[str(int(row.player_id))] = {"tm_id": None, "action": "reject"}
            save_dec(dec)
            st.rerun()
        if z.button("⏭️ Şimdilik atla", use_container_width=True):
            st.session_state.setdefault("skipped", set()).add(int(row.player_id))
            st.rerun()

    st.caption(
        "Kararın `reports/eslesme_kararlari.json` dosyasına yazılır ve bir sonraki "
        "`build_links.py` çalışmasında uygulanır. Otomatik sonucu her zaman ezer."
    )

    with st.expander(f"Kuyruğun tamamını gör ({len(queue)})"):
        st.dataframe(
            queue[["player_name", "tm_name", "tm_club", "name_score",
                   "club_score", "n_candidates"]].rename(columns={
                "player_name": "API", "tm_name": "TM adayı", "tm_club": "TM kulüp",
                "name_score": "İsim", "club_score": "Kulüp", "n_candidates": "Aday",
            }),
            hide_index=True, use_container_width=True, height=400,
        )

# ------------------------------------------------------------------ kararlar
if dec:
    st.divider()
    st.subheader(f"Verilmiş kararlar ({len(dec)})")
    drows = []
    for pid, d in dec.items():
        m = links[links.player_id == int(pid)]
        drows.append({
            "Oyuncu": m.iloc[0].player_name if len(m) else pid,
            "Karar": "kabul" if d["action"] == "accept" else "red",
            "TM adayı": m.iloc[0].tm_name if len(m) else "—",
        })
    st.dataframe(pd.DataFrame(drows), hide_index=True, use_container_width=True)
    if st.button("Tüm kararları sıfırla"):
        save_dec({})
        st.rerun()

