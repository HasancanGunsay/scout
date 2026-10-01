"""Mevki Sıralaması — her mevkiden yatırıma değer oyuncular (FAZ 6.5).

Kullanıcının testi: tarihsel bir sezonu seç, fiyat tavanı koy, listenin en
üstünü incele ve "sonra gerçekte ne oldu"ya bak. Bu sayfa o listeyi, o
listenin GERÇEKTE ne kadar tuttuğunu (güven aralığıyla) ve nerede kör
olduğunu birlikte gösterir.

Tahminler DIŞARIDAN: eğitim verisini görmemiş model (bkz. PLAN §47.3).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _havuz as HV
import _shared as sh
import _style as ui
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.model.siralama import (GUVENLER, OLCUTLER, UYARI_DOGRULANMAMIS,  # noqa: E402
                                  UYARI_IZLENEN, UYARI_KALECI, UYARI_KUCUK_N,
                                  UYARI_ZAYIF, filtrele, ozet, sirala,
                                  sonra_metni_kodu)

sh.page_setup(
    "Mevki Sıralaması",
    "Her mevkiden, fiyatına göre sahada değer üretmesi beklenen oyuncular. "
    "Sıralama bir iddiadır; sonra ne olduğu yanında durur.",
    "leaderboard",
)

MEVKI_SEKME = [("Defender", "Defans"), ("Midfielder", "Orta saha"),
               ("Attacker", "Forvet"), ("Goalkeeper", "Kaleci")]
GUVEN_ADI = {"iyi": "iyi", "zayif": "zayıf", "dogrulanmamis": "doğrulanmamış",
             "dusuk": "düşük"}
SONRA_ADI = HV.SONRA_ADI       # Havuz ekranıyla ortak (8.1)
OLCUT_ADI = {"model": "Model olasılığı (oyun verisi + piyasa)",
             "piyasa_ustu": "Piyasa üstü (model − piyasa)",
             "saf": "Yalnız oyun verisi (piyasa YOK)"}
UYARI_ADI = {
    UYARI_KUCUK_N: "Liste 30 oyuncudan küçük: güven aralığı geniş. Oranı tek "
                   "başına değil, **aralığıyla** birlikte okuyun.",
    UYARI_DOGRULANMAMIS: "Listenin çoğu **doğrulanmamış** (değerleme yok): sonuç "
                         "bu oyuncular için büyük ölçüde kör.",
    UYARI_ZAYIF: "Listenin çoğu **zayıf** bantta (0,5-5M €): burada model, "
                 "dakika+yaştan ayırt edilemiyor; yalnızca üst uç güvenilir.",
    UYARI_KALECI: "Kaleci: n=242, dakika+yaştan ayırt edilemiyor. "
                  "**Düşük güven.**",
    UYARI_IZLENEN: "Bu karma listenin çoğu **izlenen liglerden**. Kalibre "
                   "olasılık, sonucu görünür olan ligleri doğal olarak öne "
                   "çıkarır. Düşük görünürlüklü liglerdeki gizli yetenek için "
                   "soldan **Lig türü → Düşük görünürlük** seçin (orada sıralama "
                   "kalibrasyondan etkilenmez).",
}


@st.cache_data(ttl=300)
def _yukle() -> pd.DataFrame:
    con = sh._con()
    try:
        return con.sql("""
            SELECT r.*, f.team_name,
                   s.mac_lig, s.dk_lig, s.ilk11_lig, s.ga90, s.deger_bas,
                   s.deger_son, s.kulup_degisti, s.pencere_tam
            FROM player_ranking r
            LEFT JOIN player_features f
                   USING (player_id, league_id, season)
            LEFT JOIN player_sonra s
                   USING (player_id, league_id, season)
        """).df()
    except Exception:
        return pd.DataFrame()


df = _yukle()
if df.empty:
    ui.empty_state(
        "Sıralama tablosu yok",
        "Önce `python scripts/build_ranking.py` ve "
        "`python scripts/build_sonra.py` çalıştırılmalı.")
    st.stop()

# ------------------------------------------------------------------ filtreler
with st.sidebar:
    st.header("Filtreler")
    sezon = st.selectbox("Sezon", sorted(df.season.unique(), reverse=True),
                         help="Tarihsel sezon: sıralama, o günün bilgisiyle "
                              "ve eğitim verisini görmemiş modelle yapılır.")
    tur = df.loc[df.season == sezon, "tahmin_turu"].iloc[0]
    TUR_ADI = {"lig-disi CV": "lig dışı çapraz doğrulama",
               "zaman-disi": "zaman dışı (eğitimden sonraki sezon)"}
    st.caption(f"Tahmin türü: **{TUR_ADI.get(tur, tur)}**")

    olcut = st.radio("Sıralama ölçütü", list(OLCUT_ADI),
                     format_func=OLCUT_ADI.get,
                     help="'Piyasa üstü' yalnızca değerlemesi olan oyuncularda "
                          "tanımlı. 'Yalnız oyun verisi' fiyattan bağımsız "
                          "bir bakış verir.")
    n = st.slider("Her mevkiden kaç oyuncu", 5, 50, 30, 5)

    st.divider()
    tavan_m = st.slider("Fiyat tavanı (M €)", 0.25, 20.0, 5.0, 0.25,
                        help="Sezon sonundan 1 ay önceki son piyasa değeri.")
    degersiz = st.checkbox(
        "Değerlemesi olmayanları dahil et", True,
        help="Transfermarkt bu oyuncuya değer biçmemiş. Bu 0 € demek DEĞİL: "
             "genellikle izlenmeyen liglerin oyuncuları. Bu grup için "
             "sonuç ölçümümüz kısmen kör (doğrulanmamış).")
    kapsam_ad = st.radio(
        "Lig türü", ["Hepsi", "Düşük görünürlük", "İzlenen ligler"],
        help="İki grup ayrı ayrı kalibre edildi. Bir grubun kendi içindeki "
             "sıralaması kalibrasyondan etkilenmez; 'Hepsi' seçiliyken "
             "izlenen ligler öne çıkar.")
    kapsam = {"Hepsi": None, "Düşük görünürlük": "sicrama_only",
              "İzlenen ligler": "tam"}[kapsam_ad]
    yas_max = st.slider("Azami yaş", 17.0, 23.0, 23.0, 0.5)
    min_dk = st.slider("Asgari dakika", 450, 2500, 450, 50)
    guv = st.multiselect("Güven etiketi", GUVENLER, default=GUVENLER,
                         format_func=GUVEN_ADI.get)

# --------------------------------------------------------------- üst bant
st.info(
    "**Bu sıralama bir iddiadır, kanıt değil.** Aşağıda her listenin yanında "
    "*gerçekte ne kadarının yer edindiği* güven aralığıyla ve ligin tabanıyla "
    "birlikte durur. **Rating verisi yok** — sonraki dönem için yalnızca "
    "dakika, ilk 11, gol+asist ve değer değişimi ölçülebilir."
)
st.warning(
    "**Modelin seçtikleri sahada daha çok işe yarıyor, ama yeniden satış "
    "değerinin arttığı gösterilemedi** (değer değişimi kontrolden anlamlı "
    "farklı değil, PLAN §48). \"Yatırıma değer\" burada **sahada değer "
    "üretir** demektir, **değeri artar** demek değildir."
)

pencere_tam = bool(df.loc[df.season == sezon, "pencere_tam"].fillna(False).all())
if not pencere_tam:
    st.caption(":warning: Bu sezon için 12 aylık sonuç penceresi tamamlanmadı; "
               "'sonra' sütunları eksik olabilir.")

tavan = tavan_m * 1e6
havuz_hepsi = filtrele(df, sezon=sezon, kapsam=kapsam, fiyat_tavani=tavan,
                       degersiz_dahil=degersiz, guvenler=guv, yas_max=yas_max,
                       min_dakika=min_dk)

SUTUN = ["#", "Oyuncu", "Takım", "Lig", "Yaş", "Dk", "Değer (M €)",
         "Model %", "Ham %", "Piyasa üstü (puan)", "Güven", "Sonuç (12 ay)",
         "Lig dk", "İlk 11", "G+A/90", "Değer Δ%", "Kulüp değiştirdi"]


def _tablo(top: pd.DataFrame) -> pd.DataFrame:
    t = pd.DataFrame(index=top.index)
    t["#"] = np.arange(1, len(top) + 1)
    t["Oyuncu"] = top.player_name
    t["Takım"] = top.team_name.fillna("—")
    t["Lig"] = top.league_name
    t["Yaş"] = top.age_season_end.round(1)
    t["Dk"] = top.minutes.astype(int)
    t["Değer (M €)"] = (top.deger / 1e6).round(2)
    t["Model %"] = (100 * top.model_olasilik).round(0)
    t["Ham %"] = (100 * top.model_ham).round(0) if "model_ham" in top else np.nan
    t["Piyasa üstü (puan)"] = (100 * top.piyasa_ustu).round(0)
    t["Güven"] = top.guven.map(GUVEN_ADI)
    t["Sonuç (12 ay)"] = [SONRA_ADI[sonra_metni_kodu(r)]
                          for _, r in top.iterrows()]
    t["Lig dk"] = top.dk_lig
    t["İlk 11"] = top.ilk11_lig
    t["G+A/90"] = top.ga90.round(2)
    t["Değer Δ%"] = (100 * (top.deger_son / top.deger_bas - 1)).where(
        top.deger_bas > 0).round(0)
    t["Kulüp değiştirdi"] = top.kulup_degisti.map(
        {True: "evet", False: "hayır"}).fillna("—")
    return t[SUTUN]


def _sekme(pg: str, ad: str) -> None:
    havuz = havuz_hepsi[havuz_hepsi.pos_group == pg]
    top = sirala(havuz, olcut, n)
    if top.empty:
        st.caption("Bu filtrelerle oyuncu yok (ya da ölçüt bu oyuncular için "
                   "tanımsız).")
        return
    o = ozet(top, havuz)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Listedeki oyuncu", len(top), help=f"Havuz: {len(havuz)}")
    if "oran" in o:
        c2.metric("Gerçekte yer edinen",
                  f"%{100 * o['oran']:.0f}",
                  help=f"%95 GA: %{100 * o['oran_lo']:.0f}-"
                       f"%{100 * o['oran_hi']:.0f} (n={o['n']})")
    if "taban" in o:
        c3.metric("Havuzun tabanı", f"%{100 * o['taban']:.0f}",
                  delta=(f"{100 * (o['oran'] - o['taban']):+.0f} puan"
                         if "oran" in o else None))
    if o.get("dk_lig_ort") is not None:
        c4.metric("Ort. lig dakikası", f"{o['dk_lig_ort']:.0f}",
                  help=f"Yalnızca sonucu gözlenenler (n={o['dk_lig_n']}). "
                       "İzlenmeyen ligde oynayanlar dahil değil.")

    if "oran" in o:
        durum = ("**tabanın üstünde**" if o.get("ga_tabani_asiyor")
                 else "tabandan **ayırt edilemiyor**")
        st.caption(f"Bu listenin %95 güven aralığı (%{100 * o['oran_lo']:.0f}–"
                   f"%{100 * o['oran_hi']:.0f}) havuz tabanına göre {durum}.")
    for u in o["uyarilar"]:
        st.warning(UYARI_ADI[u])

    t = _tablo(top)
    st.dataframe(
        t, use_container_width=True, hide_index=True,
        column_config={
            "Model %": st.column_config.ProgressColumn(
                "Model %", min_value=0, max_value=100, format="%d",
                help="Kalibre olasılık (lig türüne göre düzeltilmiş)."),
            "Ham %": st.column_config.NumberColumn(
                format="%d",
                help="Kalibrasyon öncesi. Düşük görünürlüklü liglerde "
                     "listenin tepesi için en yeni sezonda (2024) ham değer "
                     "gerçeğe daha yakın çıktı; kalibre değer orada kötümser "
                     "(PLAN §50)."),
            "Piyasa üstü (puan)": st.column_config.NumberColumn(format="%+d"),
            "Değer Δ%": st.column_config.NumberColumn(format="%+d"),
            "Lig dk": st.column_config.NumberColumn(format="%d"),
            "İlk 11": st.column_config.NumberColumn(format="%d"),
        })
    st.download_button(
        f"{ad} listesini CSV indir", t.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"siralama_{sezon}_{pg}.csv", mime="text/csv", key=f"csv_{pg}")


sekmeler = st.tabs([ad for _, ad in MEVKI_SEKME])
for sek, (pg, ad) in zip(sekmeler, MEVKI_SEKME):
    with sek:
        _sekme(pg, ad)

with st.expander("Bu sayfa neyi söylemiyor?"):
    st.markdown(
        "- **İz yok\\*** — menşe lig Transfermarkt'ta oyuncu bazında "
        "izlenmiyorsa, oyuncu kendi ülkesinde yükselse bile bunu göremeyiz. "
        "**Başarısız demek değil.**\n"
        "- **Doğrulanmamış** — değerlemesi olmayan oyuncularda sonuç "
        "ölçümümüz kısmen kör; yalnızca tek pencerede olumlu işaret var "
        "(PLAN §45.3, §46.4).\n"
        "- **Zayıf** — 0,5-5M € bandında model, dakika+yaştan ayırt "
        "edilemiyor; sıralamanın *ucu* dolu, *ortası* belirsiz (§45.2, §47.5).\n"
        "- **Kaleci** — küçük örneklem (242); dakika+yaştan ayırt edilemiyor.\n"
        "- **Model %** — lig türüne göre kalibre (§50). Ham model izlenen "
        "liglerde ~9 puan kötümser, düşük görünürlükte iyimserdi. Düşük "
        "görünürlükteki iyimserlik sezondan sezona azalıyor (liste tepesinde "
        "2022 +20, 2023 +8, 2024 +4 puan). Sabit düzeltme en yeni sezonda "
        "fazla geliyor: 2024'te düşük görünürlüklü listenin tepesinde "
        "**kalibre değer ~12 puan kötümser, ham değer ~4 puan iyimser**. "
        "Orada ham değeri esas alın.\n"
        "- **Olasılığın seviyesi sezondan sezona oynar, sıralama daha "
        "sağlamdır.** Transfermarkt'ın 10 yılı (§54): model az sezonla "
        "eğitildiğinde bir sezonun genel olasılık seviyesi ±4–6 puan "
        "kayabiliyor ve bu kayma bir önceki sezondan kestirilemiyor (COVID "
        "sezonu gibi). Bu sayfadaki model 2–3 sezonla eğitildi. \"%62\" ile "
        "\"%58\" arasındaki farka değil, oyuncunun **listedeki yerine** "
        "güvenin.\n"
        "- **Gol+asist/90** yalnızca ≥450 dk oynayanlarda hesaplanır "
        "(seçilim etkisi).\n"
        "- **Değer Δ%** modelin öngördüğü bir şey değil; sonradan gözlenen. "
        "Model bunu kontrolden daha iyi yakalamıyor (§48.9).\n"
        "- **Görmediğimiz şeyler:** fizik, karakter, baskı altında karar, "
        "sakatlık. Sıralama bir gözlem başlangıcıdır, kararı değil.")
