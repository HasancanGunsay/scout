"""Veri durumu - neyin ne kadar toplandığı, kota, bilinen eksikler."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import pandas as pd
import streamlit as st
import yaml

sh.page_setup("Veri durumu", "Neyin ne kadar toplandığı, API kotası ve sistemin bilinen kör noktaları.", "database")

ROOT = Path(__file__).resolve().parents[2]
QUOTA = ROOT / "data" / "raw" / "apifootball" / "_quota.json"
STATE = ROOT / "data" / "raw" / "apifootball" / "_ingest_state.json"
LEAGUES = ROOT / "config" / "leagues.yaml"

# ------------------------------------------------------------------ son calisma
LOG = ROOT / "data" / "raw" / "daily_log.txt"
st.subheader("Son otomatik çalışma")
if LOG.exists():
    # utf-8-sig: PowerShell'in Out-File -Encoding utf8 ciktisi BOM ile basliyor,
    # duz utf-8 okumada BOM ilk karakteri kaydirip zaman damgasini kirpiyordu.
    lines = LOG.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    starts = [i for i, l in enumerate(lines) if "gunluk calisma basladi" in l]
    block = lines[starts[-1]:] if starts else lines
    ok = any("calisma bitti (tum adimlar basarili)" in l for l in block)
    broke = next((l for l in block if "kirilan adim" in l), None)
    running = not ok and not broke

    when = block[0][:19] if block else "—"
    if ok:
        st.success(f"**Tüm adımlar başarılı** · {when}", icon=":material/check_circle:")
    elif broke:
        st.error(
            f"**Yarıda kaldı** · {when} · kırılan adım: "
            f"`{broke.split('kirilan adim:')[-1].strip(' =')}`",
            icon=":material/error:",
        )
    else:
        st.info(f"**Çalışıyor veya yarıda kesildi** · {when}",
                icon=":material/hourglass_top:")

    steps = [l for l in block if l[21:].startswith(("OK:", "BASARISIZ:", "UYARI:"))]
    if steps:
        rows = []
        for s in steps:
            body = s[21:]
            kind, _, name = body.partition(":")
            rows.append({"Adım": name.strip(),
                         "Sonuç": {"OK": "✔ başarılı", "BASARISIZ": "✖ başarısız",
                                   "UYARI": "! uyarı"}.get(kind, kind)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with st.expander("Ham log (son 60 satır)"):
        st.code("\n".join(block[-60:]), language="text")
else:
    st.info("Henüz otomatik çalışma kaydı yok.")

st.divider()

# ------------------------------------------------------------------ tazelik
c1, c2 = st.columns([3, 1])
c1.caption(f"Analitik tablolar son güncelleme: **{sh.data_age()}**")
if c2.button("Veriyi tazele", use_container_width=True,
             icon=":material/refresh:"):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()

# ------------------------------------------------------------------ kota
st.subheader("API kotası")
if QUOTA.exists():
    q = json.loads(QUOTA.read_text(encoding="utf-8"))
    used, limit = q.get("used", 0), 100
    c1, c2, c3 = st.columns(3)
    c1.metric("Tarih (UTC)", q.get("date", "—"))
    c2.metric("Kullanılan", f"{used}/{limit}")
    c3.metric("Kalan", max(0, limit - used))
    st.progress(min(used / limit, 1.0))
else:
    st.info("Kota dosyası yok.")
st.caption("Ücretsiz plan: 100 istek/gün, 00:00 UTC'de sıfırlanır. "
           "Günlük çekim Görev Zamanlayıcı ile 08:00'de otomatik çalışıyor.")

# ------------------------------------------------------------------ ilerleme
st.divider()
st.subheader("Toplama ilerlemesi")
if STATE.exists() and LEAGUES.exists():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(LEAGUES.read_text(encoding="utf-8"))
    lg_by_id = {l["id"]: l for l in cfg["leagues"]}

    rows = []
    for season in cfg["seasons"]:
        for lg in sorted(cfg["leagues"], key=lambda x: x["priority"]):
            e = state.get("leagues", {}).get(f"{lg['id']}:{season}", {})
            total = len(e.get("team_ids") or [])
            done = sum(1 for v in e.get("teams", {}).values() if v.get("done"))
            rows.append({
                "Öncelik": lg["priority"],
                "Ülke": lg["country"], "Lig": lg["name"], "Sezon": season,
                "Durum": "✅ tamam" if e.get("complete")
                         else (f"{done}/{total} takım" if total else "—"),
            })
    df = pd.DataFrame(rows)
    done_n = (df["Durum"] == "✅ tamam").sum()
    c1, c2 = st.columns(2)
    c1.metric("Tamamlanan lig-sezon", f"{done_n}/{len(df)}")
    c2.metric("Tahmini kalan gün", f"~{max(0, (len(df) - done_n) * 45) // 100 + 1}")
    st.dataframe(df, hide_index=True, use_container_width=True, height=420)
else:
    st.info("Toplama durumu dosyası yok.")

# ------------------------------------------------------------------ tablolar
st.divider()
st.subheader("Tablolar")
feats = sh.load_features()
scores = sh.load_scores()
c1, c2, c3 = st.columns(3)
c1.metric("player_features", f"{len(feats):,}")
c2.metric("player_scores", f"{len(scores):,}")
c3.metric("Göz testi raporu", f"{sum(len(k['raporlar']) for k in sh.takip_listesi()['oyuncular'].values()):,}")

st.dataframe(
    feats.groupby(["country", "league_name", "season"])
    .agg(oyuncu=("player_id", "nunique"),
         dk900=("minutes", lambda s: (s >= 900).sum()),
         ort_dk=("minutes", "mean"))
    .round(0).reset_index(),
    hide_index=True, use_container_width=True,
)

# ------------------------------------------------------------------ eksikler
st.divider()
st.subheader("Bilinen eksikler ve kısıtlar")
st.markdown(
    """
| Konu | Durum |
|---|---|
| **Sezon aralığı** | Ücretsiz plan yalnızca 2022–2024. Güncel sezon yok. |
| **Brezilya kadro kapsamı** | `page<=3` sınırı yüzünden 4 sayfalık kadroların son sayfası alınamıyor. Kayıp rastgele, tahmini %5-10. |
| **İtalya Serie C/D** | Oyuncu istatistiği yok (`stats_players=False`), kapsam dışı. |
| **xG** | Ücretsiz kaynaklarda yok. Şut hacmi + isabet ile telafi ediliyor. |
| **Lig gücü katsayısı** | Henüz kurulmadı → **ligler arası skor kıyası geçersiz.** Aynı lig içi sıralama geçerli. |
| **Yaş eğrisi** | Devre dışı — tek sezon hayatta kalma yanlılığı taşıyor. Yaş bandı percentile'ı kullanılıyor. |
| **Rol ayrımı** | Yalnızca **stoper/bek** ayrımı istatistiksel destek buldu. Orta saha ve forvette dağılımlar tek tepeli — ayrık rol yok, mevki grubu korunuyor. Veri büyüdükçe yeni ayrımlar kendiliğinden devreye girer. |
| **Sezon içi transfer** | API sezon toplamlarını iki kulüpte tekrarlıyor; en çok dakikalı kayıt esas alındı, `multi_team` ile işaretli. |
"""
)

# Piyasa degeri kapsami - canli hesap, elle yazilmis sayi degil
if "player_meta" in [r[0] for r in sh._con().sql(
        "SELECT table_name FROM information_schema.tables").fetchall()]:
    cov = sh._con().sql("""
        SELECT count(DISTINCT f.player_id) AS toplam,
               count(DISTINCT m.player_id) AS eslesen,
               count(DISTINCT m.player_id) FILTER (WHERE m.market_value_eur IS NOT NULL) AS deger,
               count(DISTINCT m.player_id) FILTER (WHERE m.contract_until IS NOT NULL) AS sozlesme
        FROM player_features f LEFT JOIN player_meta m ON m.player_id = f.player_id
    """).df().iloc[0]
    st.markdown(
        f"**Piyasa değeri / sözleşme kapsamı:** {int(cov.eslesen)}/{int(cov.toplam)} oyuncu "
        f"Transfermarkt ile eşleşti (%{100*cov.eslesen/cov.toplam:.0f}); "
        f"{int(cov.deger)} oyuncuda piyasa değeri, {int(cov.sozlesme)} oyuncuda sözleşme "
        "bitişi var. Eşleşmeyenler kötü oyuncu değil — CC0 veri seti alt ligleri "
        "tam kapsamıyor. Belirsiz kalan vakalar **Eşleşme kuyruğu** sayfasında."
    )

