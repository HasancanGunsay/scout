"""Havuz — okyanustan süzülmüş oyuncu havuzu (FAZ 8.1).

Kullanıcı isteği (1 Eki 2026): "sistemin bana bir oyuncu ismi vermesini
istemiyorum ... okyanus içerisinde bir havuz yaratmasını bekliyorum.
İstatistikleri liste üzerinden inceleyebildiğim ..."

Sistem havuzu kurar (havuz puanı, bkz. app/_havuz.py), kullanıcı listede
gezer, sıralar, bir satıra tıklayıp oyuncunun kartını açar. Ayrıntılı
güncel istatistik Sofascore'da.

Liste düzeni Laboratuvar > Liderler'den (kullanıcı beğendi): istatistik
aileleri yan yana, ek sütun eklenebilir.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _havuz as HV
import _metrikler as MK
import _shared as sh
import _style as ui
import _takip_ui as TU
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.model.siralama import sonra_metni_kodu  # noqa: E402
from scout.scoring.engine import column_for  # noqa: E402

sh.page_setup(
    "Havuz",
    "Okyanustan süzülmüş oyuncu havuzu. Filtrele, sırala, istatistiklere "
    "liste üzerinden bak; bir satıra tıkla, oyuncunun kartı açılsın.",
    "waves",
)

# ?oyuncu=<anahtar> ile gelindiyse (takip listesinden "Havuzda aç") kaynak ve
# sezonu o satıra ayarla - widget'lar oluşmadan ÖNCE, anahtar başına bir kez.
_hedef = st.query_params.get("oyuncu")
if _hedef and st.session_state.get("hv_hedef_uygulandi") != _hedef:
    _p = _hedef.split("-")
    if len(_p) == 3 and _p[1].isdigit():
        st.session_state["hv_kaynak"] = HV.KAYNAK_API
        st.session_state["hv_sezon"] = int(_p[2])
    elif len(_p) == 3:
        st.session_state["hv_kaynak"] = HV.KAYNAK_TM
    st.session_state["hv_hedef_uygulandi"] = _hedef
# varsayılan session_state'ten: widget'a default verip state'i de yazmak
# Streamlit'te uyarı kutusu çıkarır
st.session_state.setdefault("hv_kaynak", HV.KAYNAK_API)


def _bicim(m: MK.Metrik | None, v) -> str:
    if v is None or pd.isna(v):
        return "—"
    if m is None:
        return f"{v:.2f}"
    return m.bicim % (v * 100 if m.yuzde else v)


# ------------------------------------------------------------------ filtreler
with st.container(border=True):
    a1, a2 = st.columns([1.3, 1])
    kaynak = a1.segmented_control(
        "Kaynak", [HV.KAYNAK_API, HV.KAYNAK_TM], format_func=HV.KAYNAK_ADI.get,
        required=True, key="hv_kaynak")
    dilim = a2.segmented_control(
        "Havuz dilimi", HV.DILIMLER, format_func=HV.DILIM_ADI.get,
        default=25, required=True, key="hv_dilim",
        help="Oyuncunun kendi grubundaki yeri (sezon × mevki × lig türü). "
             "'İlk %25' = grubunun en iyi dörtte biri. Düşük görünürlüklü "
             "ligler kendi aralarında yarışır, izlenen liglerin gölgesinde "
             "kalmaz.")
    a1.caption(HV.KAYNAK_ACIKLAMA[kaynak])

    tum = sh.havuz_api() if kaynak == HV.KAYNAK_API else sh.havuz_tm()
    if tum.empty:
        ui.empty_state("Havuz verisi yok",
                       "Önce `python scripts/build_ranking.py` (API) ya da "
                       "`python scripts/tm_defter.py --kaydet` (TM) çalıştırılmalı.")
        st.stop()

    b1, b2, b3 = st.columns([1.6, 0.8, 1.2])
    mevkiler = b1.pills("Mevki", HV.MEVKILER, selection_mode="multi",
                        format_func=MK.MEVKI_ADI.get, key="hv_mevki",
                        help="Boş = hepsi.")
    kapsam = None
    if kaynak == HV.KAYNAK_API:
        sezonlar = sorted(tum.season.unique().tolist(), reverse=True)
        sezon = b2.selectbox("Sezon", sezonlar, key="hv_sezon",
                             help="2024 = 2024/25 sezonu.")
        tum = tum[tum.season == sezon]
        kapsam = b3.segmented_control(
            "Lig türü", ["sicrama_only", "tam"], format_func=HV.KAPSAM_ADI.get,
            key="hv_kapsam",
            help="Düşük görünürlük = Transfermarkt'ın oyuncu bazında izlemediği "
                 "ligler; gizli yeteneğin asıl alanı. Boş = ikisi de.")
    else:
        sezon = int(tum.season.iloc[0])
        b2.markdown(f"**Sezon**  \n{sezon}/{str(sezon + 1)[-2:]}")

    c1, c2, c3, c4 = st.columns([1.6, 0.9, 0.9, 1.2])
    ligler = c1.multiselect("Lig", sorted(tum.lig.unique()), key=f"hv_lig_{kaynak}",
                            placeholder="Hepsi")
    yas_max = c2.slider("Azami yaş", 17.0, 23.0, 23.0, 0.5, format="%.1f",
                        key="hv_yas")
    min_dk = c3.slider("Asgari dakika", 450, 3000, 450, 50, key="hv_dk")
    TAVAN = [0.5, 1, 2, 3, 5, 10, 20, 50, 0]
    tavan = c4.select_slider(
        "Fiyat tavanı", TAVAN, value=0, key="hv_tavan",
        format_func=lambda v: "sınırsız" if v == 0 else f"{v:g} M €",
        help="Sezon sonundan 1 ay önceki Transfermarkt değeri.")
    degersiz = c4.checkbox(
        "Değeri bilinmeyenler dahil", True, key="hv_degersiz",
        help="Transfermarkt değer biçmemiş. Bu 0 € demek DEĞİL: çoğu "
             "izlenmeyen liglerin oyuncuları. Fiyat tavanı onları elemez.")

    aileler = MK.AILELER if kaynak == HV.KAYNAK_API else HV.TM_AILELER
    katalog = MK.TUMU if kaynak == HV.KAYNAK_API else HV.TM_TUMU
    katalog = {k: m for k, m in katalog.items() if k in tum.columns}
    d1, d2, d3 = st.columns([1, 1.6, 1])
    gorunum = d1.selectbox("İstatistik görünümü", ["Özet"] + list(aileler),
                           key=f"hv_gorunum_{kaynak}",
                           help="Bir aile seçince o ailenin metrikleri yan yana "
                                "gelir (Laboratuvar > Liderler gibi).")
    ek = d2.multiselect("Ek sütunlar", list(katalog), format_func=lambda k: katalog[k].ad,
                        key=f"hv_ek_{kaynak}", placeholder="Metrik ekle…")
    ara = d3.text_input("İsim ara", key="hv_ara", placeholder="ör. ruben")

tavan_eur = None if tavan == 0 else tavan * 1e6
v = HV.filtrele(tum, dilim=dilim, mevkiler=mevkiler, ligler=ligler, kapsam=kapsam,
                yas_max=yas_max, min_dk=min_dk, fiyat_tavani=tavan_eur,
                degersiz_dahil=degersiz, ara=ara)
v = v.sort_values(["havuz_puani", "model_olasilik"], ascending=False).reset_index(drop=True)

if v.empty:
    ui.empty_state("Bu filtrelerle havuz boş",
                   "Havuz dilimini genişlet ya da yaş/dakika/fiyat sınırını gevşet.")
    st.stop()

# ------------------------------------------------------------------ özet bant
k1, k2, k3, k4 = st.columns(4)
k1.metric("Havuzda", f"{len(v):,}".replace(",", "."),
          help=f"Bu sezonun tüm havuzu: {len(tum):,} U23 oyuncu".replace(",", "."))
if kaynak == HV.KAYNAK_API:
    dus = int((v.kapsam == "sicrama_only").sum())
    k2.metric("Düşük görünürlükten", f"{dus} (%{100 * dus / len(v):.0f})")
else:
    k2.metric("Lig", f"{v.lig.nunique()}")
ucuz = int(((v.deger_var.fillna(0) == 1) & (v.deger <= 5e6)).sum())
k3.metric("Değeri ≤5 M €", f"{ucuz}")
k4.metric("Medyan yaş", f"{v.yas.median():.1f}")
ui.badges(*[(f"{MK.MEVKI_ADI[p]} {int((v.pos_group == p).sum())}", "info")
            for p in HV.MEVKILER if (v.pos_group == p).any()])

# ------------------------------------------------------------------ tablo
OZET = {HV.KAYNAK_API: ["rating", "np_ga_p90_sh"],
        HV.KAYNAK_TM: ["dakika_payi", "ga_90"]}[kaynak]
metrikler = OZET if gorunum == "Özet" else [m.kol for m in aileler[gorunum]]
metrikler = [k for k in dict.fromkeys(metrikler + ek) if k in katalog]

takipteki = set(sh.takip_listesi()["oyuncular"])
t = pd.DataFrame({
    "Takip": v.kisi.isin(takipteki).map({True: "★", False: ""}),
    "Oyuncu": v.oyuncu, "Yaş": v.yas.round(1),
    "Kulüp": v.kulup, "Lig": v.lig,
    "Mevki": v.pos_group.map(MK.MEVKI_ADI),
    "Rol": v.mevki, "Dk": v.dk,
    "Değer (M €)": (v.deger / 1e6).where(v.deger_var.fillna(0) == 1),
    "Model %": (100 * v.model_olasilik).round(0),
    "Havuz puanı": v.havuz_puani.round(0),
})
cfg = {
    "Takip": st.column_config.TextColumn(
        "★", width="small", help="Takip listende. Kartı açıp takibe al."),
    "Yaş": st.column_config.NumberColumn(format="%.1f"),
    "Dk": st.column_config.NumberColumn(format="%d"),
    "Değer (M €)": st.column_config.NumberColumn(
        format="%.2f", help="Sezon sonundan 1 ay önceki Transfermarkt değeri. "
                            "Boş = değer biçilmemiş (0 € değil)."),
    "Model %": st.column_config.NumberColumn(
        format="%d%%",
        help="12 ay içinde izlenen bir 1. ligde ≥900 dakika olasılığı. "
             "Seviyesi sezondan sezona ±4-6 puan oynar; listedeki yere "
             "güvenin, iki yakın yüzde arasındaki farka değil."),
    "Havuz puanı": st.column_config.ProgressColumn(
        "Havuz puanı", min_value=0, max_value=100, format="%d",
        help="Grubunun içindeki yeri (sezon × mevki × lig türü): 95 = "
             "grubunun en iyi %5'i. Liste buna göre sıralı."),
}
if kaynak == HV.KAYNAK_API:
    cfg["Rol"] = st.column_config.TextColumn(
        help="Puanlama şablonlarına göre en çok uyduğu rol.")
    t.insert(3, "Görünürlük", v.kapsam.map(
        {"sicrama_only": "düşük", "tam": "izlenen"}))
    t["Şimdi"] = v.simdi_kulup.fillna("—")
    t["Sonuç (12 ay)"] = [HV.SONRA_ADI[sonra_metni_kodu(r)] for _, r in v.iterrows()]
    cfg["Şimdi"] = st.column_config.TextColumn(
        help="Transfermarkt'a göre bugünkü kulübü (Temmuz 2026 anlık "
             "görüntüsü). TM'nin izlemediği bir lige gittiyse eski kalabilir.")
    cfg["Sonuç (12 ay)"] = st.column_config.TextColumn(
        help="Sezon sonrası 12 ayda ne oldu. 'iz yok*' = izlenmeyen ligde, "
             "başarısız demek değil.")
else:
    cfg["Rol"] = st.column_config.TextColumn(
        "Mevki (ince)", help="Sezonun ilk 11'lerinde en çok oynadığı mevki.")
    t["Şimdi"] = ["aynı" if g == k else (g if isinstance(g, str) else "—")
                  for g, k in zip(v.guncel_kulup, v.kulup)]
    cfg["Şimdi"] = st.column_config.TextColumn(
        help="Transfermarkt'a göre bugünkü kulübü (Temmuz 2026).")
for k in metrikler:
    m = katalog[k]
    t[m.ad] = v[k] * (100 if m.yuzde else 1)
    cfg[m.ad] = st.column_config.NumberColumn(m.ad, format=m.bicim,
                                              help=m.aciklama or None)

ev = st.dataframe(t, hide_index=True, width="stretch", height=520,
                  column_config=cfg, on_select="rerun",
                  selection_mode="single-row",
                  # seçim KONUMLA saklanır: süzgeç değişince aynı konum başka
                  # oyuncuyu gösterirdi. Anahtar satır kümesine bağlı.
                  key=f"hv_tablo_{kaynak}_{HV.ozet_anahtar(v.anahtar)}")
st.caption("Sütun başlığına tıklayarak sırala · bir satıra tıkla, kartı aşağıda açılsın")
if any(k == "pass_accuracy" for k in metrikler):
    st.info("**İsabetli pas/maç (API) bir yüzde değil** — maç başına isabetli "
            "pas sayısına yakın; çok pas atan oyuncuda yüksek çıkar.")

st.download_button("Havuzu CSV indir", t.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"havuz_{kaynak}_{sezon}.csv", mime="text/csv")


# ------------------------------------------------------------------ kart
def _profil(r: pd.Series) -> tuple[list[str], list[float], list[str]]:
    """(etiket, yüzdelik, ham değer metni) — yüksek = iyi."""
    ad, yuz, ham = [], [], []
    if r.kaynak == HV.KAYNAK_API:
        for m in HV.API_PROFIL.get(r.pos_group, []):
            kol = column_for(m)
            if kol in r and pd.notna(r[kol]):
                ad.append(sh.metric_label(m))
                yuz.append(float(r[kol]))
                hk = kol[:-len("_pct")]
                # biçim: kendi kaydı yoksa taban metriğinki (duel_win_pct_sh → %)
                ham.append(_bicim(MK.TUMU.get(hk) or MK.TUMU.get(m), r.get(hk)))
    else:
        for k in HV.TM_PROFIL:
            if pd.notna(r.get(f"{k}_hpct")):
                ad.append(HV.TM_TUMU[k].ad)
                yuz.append(float(r[f"{k}_hpct"]))
                ham.append(_bicim(HV.TM_TUMU[k], r.get(k)))
    return ad, yuz, ham


def _kart(r: pd.Series) -> None:
    with st.container(border=True):
        sol, sag = st.columns([1.1, 1])
        with sol:
            st.markdown(f"### {r.oyuncu}")
            sez = f"{int(r.season)}/{str(int(r.season) + 1)[-2:]}"
            st.caption(f"{r.kulup} · {r.lig} · {sez}")
            rozet = [(MK.MEVKI_ADI.get(r.pos_group, r.pos_group), "info"),
                     (f"{r.yas:.1f} yaş", "mute")]
            if r.mevki and r.mevki != "—":
                rozet.append((r.mevki, "mute"))
            if r.kaynak == HV.KAYNAK_API:
                rozet.append((HV.KAPSAM_ADI[r.kapsam],
                              "warn" if r.kapsam == "sicrama_only" else "mute"))
            ui.badges(*rozet)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Havuz puanı", f"{r.havuz_puani:.0f}")
            m2.metric("Model", f"%{100 * r.model_olasilik:.0f}")
            m3.metric("Dakika", f"{int(r.dk):,}".replace(",", "."))
            m4.metric("Değer", f"{r.deger / 1e6:.2f} M €"
                      if r.deger_var == 1 and pd.notna(r.deger) else "—")
            if r.kaynak == HV.KAYNAK_API:
                simdi = r.simdi_kulup if isinstance(r.simdi_kulup, str) else "—"
                deger = (f" · {r.simdi_deger / 1e6:.2f} M €"
                         if pd.notna(r.simdi_deger) else "")
                st.markdown(f"**Şimdi (TM, Tem 2026):** {simdi}{deger}  \n"
                            f"**Sonuç (12 ay):** {HV.SONRA_ADI[sonra_metni_kodu(r)]}")
                if st.button("Scout dosyasında aç", icon=":material/assignment:",
                             key=f"dosya_{r.anahtar}"):
                    st.switch_page("views/Scout_Dosyasi.py", query_params={
                        "pid": int(r.player_id), "lid": int(r.league_id),
                        "sezon": int(r.season)})
            else:
                gk = r.guncel_kulup if isinstance(r.guncel_kulup, str) else "—"
                boy = f"{r.boy:.0f} cm" if pd.notna(r.get("boy")) else "—"
                AYAK = {"right": "sağ", "left": "sol", "both": "iki ayak"}
                st.markdown(f"**Şimdi (TM, Tem 2026):** {gk}  \n"
                            f"**Boy / ayak:** {boy} · {AYAK.get(r.get('ayak'), '—')}")
            st.divider()
            TU.takip_kutusu(r)
        with sag:
            ad, yuz, ham = _profil(r)
            if not ad:
                st.caption("Yüzdelik profil için yeterli metrik yok.")
                return
            st.markdown("**Yüzdelik profil**")
            fig = go.Figure(go.Bar(
                x=yuz[::-1], y=ad[::-1], orientation="h",
                text=[f"{y:.0f} · {h}" for y, h in zip(yuz[::-1], ham[::-1])],
                textposition="outside", cliponaxis=False,
                marker=dict(color=yuz[::-1], colorscale=ui.SCORE_SCALE,
                            cmin=0, cmax=100,
                            line=dict(color=ui.COLORS["border_strong"], width=0.5)),
                hovertemplate="%{y}: %{x:.0f}. yüzdelik<extra></extra>"))
            ui.apply_plotly(fig)
            fig.update_layout(height=50 + 34 * len(ad),
                              xaxis=dict(range=[0, 118], tickvals=[0, 25, 50, 75, 100]),
                              margin=dict(l=8, r=8, t=4, b=8), showlegend=False)
            fig.add_vline(x=50, line=dict(color=ui.COLORS["fg_subtle"], width=1,
                                          dash="dot"))
            st.plotly_chart(fig, width="stretch", key=f"profil_{r.anahtar}")
            st.caption("50 = ortanca. " + (
                "Kendi lig + sezon + mevki havuzunda (tüm yaşlar)."
                if r.kaynak == HV.KAYNAK_API else
                "Aynı mevkideki U23 havuzunda (14 lig). Yenen gol ve kart "
                "ters çevrildi: yüksek = iyi."))


secili = ev.selection.rows if ev is not None else []
if secili:
    _kart(v.iloc[secili[0]])
else:
    # ?oyuncu=<anahtar> ile doğrudan açılabilir (takip listesinden dönüş, test)
    hedef = st.query_params.get("oyuncu")
    if hedef and (tum.anahtar == hedef).any():
        if not (v.anahtar == hedef).any():
            st.caption("Bu oyuncu şu anki filtrelerin dışında; kartı yine de "
                       "açıldı.")
        _kart(tum[tum.anahtar == hedef].iloc[0])
    else:
        ui.empty_state("Bir satıra tıkla",
                       "Oyuncunun kartı — yüzdelik profili ve bugün nerede "
                       "olduğu — burada açılır.")

with st.expander("Havuz nasıl kuruluyor?"):
    st.markdown(
        "- **Havuz puanı** — modelin olasılığının oyuncunun *kendi grubu* "
        "içindeki yüzdeliği. Grup: sezon × mevki × lig türü. Karma listede "
        "olasılıkla sıralamak izlenen ligleri öne çıkarıyor (iki lig türünün "
        "taban oranı çok farklı); grup içi yüzdelik düşük görünürlüklü "
        "liglerin en iyilerine kendi payını verir. Puan, yaş/fiyat "
        "filtrelerinden **önce** hesaplanır — filtre puanı değiştirmez.\n"
        "- **Model %** — 12 ay içinde izlenen bir 1. ligde ≥900 dakika "
        "oynama olasılığı. API havuzunda tahminler eğitim verisini görmemiş "
        "modelden; lig türüne göre kalibre. Seviyesi sezondan sezona ±4-6 "
        "puan oynar; **sıralama daha sağlamdır** (PLAN §54).\n"
        "- **2025/26 havuzu** ileriye dönük defterde kayıtlı (891 U23, "
        "PLAN §56). Sonuç 15 Haziran 2027'den sonra puanlanacak; o zamana "
        "kadar bu havuzun isabeti **bilinmiyor**. Transfermarkt modelinin "
        "mühürlü testteki ayırt ediciliği: AUC 0,742 (2018–21).\n"
        "- **Değeri bilinmeyen** oyuncu ucuz sayılmaz; fiyat tavanı onu "
        "elemez, ayrı kutucukla çıkarılır.\n"
        "- **Görmediğimiz şeyler:** fizik, karakter, sakatlık, baskı altında "
        "karar. Havuz bir izleme başlangıcıdır; ayrıntı Sofascore'da.")
