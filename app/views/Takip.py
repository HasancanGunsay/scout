"""Takip listesi — izlediğin oyuncular, notların, göz testi raporların (FAZ 8.2).

Kullanıcı isteği (1 Eki 2026): "oyuncuları takibe alabildiğim bir sistem".
Oyuncu Havuz kartından (ya da Keşif / Profil'den) takibe alınır; burada
durumu, zaman damgalı notları ve yapılandırılmış göz testi raporu tutulur.

Kişi anahtarı Transfermarkt kimliği: API 2024'ten eklenen oyuncu ile TM
2025/26 havuzundaki aynı kişi tek satırdır, havuz geçmişi birlikte görünür.

Eski "Shortlist & rapor" sayfasının yerine (o liste hiç kullanılmamıştı;
rapor formu buraya taşındı).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _havuz as HV
import _metrikler as MK
import _shared as sh
import _style as ui
import _takip_ui as TU
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout import takip as TK  # noqa: E402
from scout.features.tm_tarih import INCE_MEVKI  # noqa: E402
from scout.model.siralama import sonra_metni_kodu  # noqa: E402

sh.page_setup(
    "Takip listesi",
    "İzlediğin oyuncular. Durumlarını, maç notlarını ve göz testi "
    "raporlarını burada tut; ayrıntılı güncel istatistik Sofascore'da.",
    "bookmarks",
)

liste = sh.takip_listesi()
oy = liste["oyuncular"]
if not oy:
    ui.empty_state("Takip listen boş",
                   "Havuz'da bir oyuncunun satırına tıkla, kartında "
                   "'Takibe al'a bas.")
    if st.button("Havuza git", icon=":material/waves:", type="primary"):
        st.switch_page("views/Havuz.py")
    st.stop()


@st.cache_data(ttl=300)
def _tm_bilgi(tm_idler: tuple[int, ...]) -> pd.DataFrame:
    if not tm_idler:
        return pd.DataFrame()
    return sh._con().sql(f"""
        SELECT player_id AS tm_id, name AS tm_ad, url AS tm_url,
               current_club_name AS simdi_kulup,
               market_value_in_eur AS simdi_deger, date_of_birth,
               sub_position, foot, height_in_cm
        FROM tm_players WHERE player_id IN ({",".join(map(str, tm_idler))})
    """).df()


# ------------------------------------------------------------- birleştir
def _secim(d: pd.DataFrame) -> pd.DataFrame:
    return d[d.kisi.isin(oy)] if "kisi" in d else pd.DataFrame()


api, tm = _secim(sh.havuz_api()), _secim(sh.havuz_tm())
gecmis = pd.concat([
    api.assign(sezon_ad=api.season.astype(str)) if len(api) else api,
    tm.assign(sezon_ad=tm.season.map(lambda s: f"{s}/{str(s + 1)[-2:]}"))
    if len(tm) else tm,
], ignore_index=True)
if gecmis.empty:
    gecmis = pd.DataFrame(columns=["kisi", "season", "kaynak", "sezon_ad"])
# en güncel havuz satırı: sezon büyük olan; eşitse TM (daha yeni anlık görüntü)
gecmis["_tm_once"] = (gecmis.kaynak == HV.KAYNAK_TM).astype(int)
son = (gecmis.sort_values(["season", "_tm_once"], ascending=False)
       .drop_duplicates("kisi").set_index("kisi"))
tmb = _tm_bilgi(tuple(sorted(int(k[3:]) for k in oy if k.startswith("tm:"))))
tmb = tmb.set_index(tmb.tm_id.map(lambda i: f"tm:{i}")) if len(tmb) else tmb

DURUM_SIRA = {d: i for i, d in enumerate(["oncelikli", "ilgilen", "izle",
                                          "birakildi"])}
bugun = pd.Timestamp(date.today())
satirlar = []
for kisi, k in oy.items():
    s = son.loc[kisi] if kisi in son.index else None
    b = tmb.loc[kisi] if len(tmb) and kisi in tmb.index else None
    dog = b.date_of_birth if b is not None else None
    ince = (INCE_MEVKI.get(b.sub_position, (None, None))[0]
            if b is not None and isinstance(b.sub_position, str) else None)
    son_not = k["notlar"][-1]["metin"] if k["notlar"] else ""
    satirlar.append({
        "kisi": kisi, "durum": k["durum"],
        "Durum": TU.DURUM_ADI[k["durum"]],
        "Oyuncu": k["ad"],
        "Yaş": ((bugun - pd.Timestamp(dog)).days / 365.25
                if dog is not None and pd.notna(dog) else None),
        "Şimdi": (b.simdi_kulup if b is not None and isinstance(b.simdi_kulup, str)
                  else (s.kulup if s is not None else "—")),
        "Değer bugün (M €)": (b.simdi_deger / 1e6 if b is not None
                              and pd.notna(b.simdi_deger) else None),
        "Mevki": (HV.INCE_MEVKI_ADI.get(ince, ince) if ince else
                  (MK.MEVKI_ADI.get(s.pos_group) if s is not None else "—")),
        "Son havuz": (f"{s.sezon_ad} · {s.havuz_puani:.0f}" if s is not None
                      else "—"),
        "Model % (eklerken)": (100 * k["ilk"]["model_olasilik"]
                               if k["ilk"]["model_olasilik"] is not None else None),
        "Eklendi": pd.Timestamp(k["eklendi"]).date(),
        "Not": len(k["notlar"]),
        "Son not": son_not[:70] + ("…" if len(son_not) > 70 else ""),
        "_sira": DURUM_SIRA[k["durum"]], "_eklendi": k["eklendi"],
    })
L = (pd.DataFrame(satirlar)
     .sort_values(["_sira", "_eklendi"], ascending=[True, False])
     .reset_index(drop=True))

# ------------------------------------------------------------- özet + liste
k1, k2, k3, k4 = st.columns(4)
k1.metric("Takipte", len(L))
k2.metric("Öncelikli", int((L.durum == "oncelikli").sum()))
ileri = sum(1 for k in oy.values() if not k["ilk"]["sonuc_gorunur"])
k3.metric("Göz testi sayılan", ileri,
          help="Sonucu henüz belli olmayan sezondan (2025/26) seçtiklerin. "
               "15 Haziran 2027'den sonra hesap defterinde puanlanacak. "
               "Sonucu ekranda görünürken seçilenler sayılmaz.")
k4.metric("Not", int(L.Not.sum()))

sec_durum = st.pills("Durum filtresi", TK.DURUMLAR, selection_mode="multi",
                     format_func=TU.DURUM_ADI.get, key="tk_durum",
                     help="Boş = hepsi.")
G = L[L.durum.isin(sec_durum)] if sec_durum else L
GOSTER = ["Durum", "Oyuncu", "Yaş", "Şimdi", "Değer bugün (M €)", "Mevki",
          "Son havuz", "Model % (eklerken)", "Eklendi", "Not", "Son not"]
ev = st.dataframe(
    G[GOSTER], hide_index=True, width="stretch",
    height=min(560, 38 + 35 * max(len(G), 1)),
    on_select="rerun", selection_mode="single-row",
    key=f"tk_tablo_{HV.ozet_anahtar(G.kisi)}",   # bkz. Havuz: konumla seçim
    column_config={
        "Yaş": st.column_config.NumberColumn(format="%.1f",
                                             help="Bugünkü yaşı."),
        "Şimdi": st.column_config.TextColumn(
            help="Transfermarkt'a göre bugünkü kulübü (Temmuz 2026)."),
        "Değer bugün (M €)": st.column_config.NumberColumn(format="%.2f"),
        "Son havuz": st.column_config.TextColumn(
            help="En güncel havuz sezonu ve o sezondaki havuz puanı."),
        "Model % (eklerken)": st.column_config.NumberColumn(
            format="%d%%", help="Takibe aldığın andaki sistem iddiası. "
                                "Sonradan güncellenmez."),
        "Eklendi": st.column_config.DateColumn(format="D MMM YYYY"),
        "Not": st.column_config.NumberColumn(format="%d"),
    })
st.caption("Bir satıra tıkla: notlar, durum, havuz geçmişi ve göz testi "
           "raporu aşağıda açılır.")

# CSV: liste + bütün notlar (yedek / paylaşım)
notlar = pd.DataFrame([{"Oyuncu": k["ad"], "Zaman": n["zaman"], "Not": n["metin"]}
                       for k in oy.values() for n in k["notlar"]])
c1, c2, _ = st.columns([1, 1, 3])
c1.download_button("Listeyi CSV indir",
                   L[GOSTER].to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"takip_{date.today()}.csv", mime="text/csv")
if len(notlar):
    c2.download_button("Notları CSV indir",
                       notlar.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"takip_notlari_{date.today()}.csv",
                       mime="text/csv")


# ------------------------------------------------------------- ayrıntı
def _rapor_formu(kisi: str, k: dict) -> None:
    with st.form(f"rapor_{kisi}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            izlenen = st.date_input("İzleme tarihi", date.today())
            dk = st.number_input("Kaç dakika izledin", 0, 500, 90, 15)
            karar = st.select_slider(
                "Genel karar", ["Takip etme", "İzlemeye devam", "İlgilen",
                                "Öncelikli", "Hemen al"], value="İzlemeye devam")
            mac = st.text_input("Maç / rakip", placeholder="ör. Ajax (D), 2-1")
        with c2:
            st.caption("1 = zayıf, 5 = seçkin")
            teknik = st.slider("Teknik", 1, 5, 3)
            fizik = st.slider("Fizik / atletizm", 1, 5, 3)
            zeka = st.slider("Oyun zekası / karar", 1, 5, 3)
            karakter = st.slider("Karakter / mücadele", 1, 5, 3)
        guclu = st.text_area("Güçlü yönler", height=80)
        zayif = st.text_area("Zayıf yönler", height=80)
        uyum = st.radio("Sistemin değerlendirmesi sana doğru geldi mi?",
                        ["Evet", "Abartmış", "Hafife almış", "Emin değilim"],
                        horizontal=True,
                        help="Zamanla sistemin nerede senin gözünden "
                             "ayrıştığını gösterir.")
        if st.form_submit_button("Raporu kaydet", type="primary"):
            TK.rapor_ekle(kisi, {
                "izleme_tarihi": str(izlenen), "izlenen_dk": int(dk),
                "mac": mac, "karar": karar, "teknik": teknik, "fizik": fizik,
                "zeka": zeka, "karakter": karakter, "guclu": guclu,
                "zayif": zayif, "sistem_uyumu": uyum})
            st.toast("Rapor kaydedildi.", icon=":material/task_alt:")
            st.rerun()


def _sil_cb(kisi: str) -> None:
    TK.sil(kisi)
    st.toast("Listeden çıkarıldı (günlükte kaydı duruyor).",
             icon=":material/bookmark_remove:")


def _ayrinti(kisi: str) -> None:
    k = oy[kisi]
    r = L[L.kisi == kisi].iloc[0]
    g = gecmis[gecmis.kisi == kisi].sort_values(["season", "_tm_once"],
                                                ascending=False)
    with st.container(border=True):
        st.markdown(f"### {k['ad']}")
        rozet = [(TU.DURUM_ADI[k["durum"]], TU.DURUM_RENK[k["durum"]]),
                 (f"Eklendi: {TU.tarih(k['eklendi'])}", "mute")]
        if r["Mevki"] and r["Mevki"] != "—":
            rozet.append((r["Mevki"], "info"))
        if pd.notna(r["Yaş"]):
            rozet.append((f"{r['Yaş']:.1f} yaş", "mute"))
        rozet.append((f"Şimdi: {r['Şimdi']}", "mute"))
        ui.badges(*rozet)

        sol, sag = st.columns([1, 1.15])
        with sol:
            TU.durum_secici(kisi, k["durum"], "takip")
            TU.not_girisi(kisi, "takip")
            st.markdown("**Notlar**")
            if not k["notlar"]:
                st.caption("Henüz not yok. İzlediğin maçtan bir cümle yeter.")
            for n in reversed(k["notlar"]):
                st.markdown(f"<div style='border-left:3px solid var(--c-border-strong);"
                            f"padding:2px 10px;margin:6px 0'>"
                            f"<div style='font-size:.75rem;color:var(--c-fg-subtle)'>"
                            f"{TU.tarih(n['zaman'])}</div>{_html(n['metin'])}</div>",
                            unsafe_allow_html=True)
        with sag:
            st.markdown("**Havuz geçmişi**")
            if g.empty:
                st.caption("Bu oyuncu hiçbir havuzda yok (U23 / 450 dk dışı "
                           "bir sezondan eklenmiş olabilir).")
            else:
                h = pd.DataFrame({
                    "Sezon": g.sezon_ad, "Kulüp": g.kulup, "Lig": g.lig,
                    "Dk": g.dk, "Model %": (100 * g.model_olasilik).round(0),
                    "Havuz puanı": g.havuz_puani.round(0),
                    "Sonuç (12 ay)": [HV.SONRA_ADI[sonra_metni_kodu(x)]
                                      if x.kaynak == HV.KAYNAK_API else "2027'de"
                                      for _, x in g.iterrows()]})
                st.dataframe(h, hide_index=True, width="stretch", column_config={
                    "Dk": st.column_config.NumberColumn(format="%d"),
                    "Model %": st.column_config.NumberColumn(format="%d%%"),
                    "Havuz puanı": st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%d")})
            ilk = k["ilk"]
            parca = []
            if ilk["model_olasilik"] is not None:
                parca.append(f"model %{100 * ilk['model_olasilik']:.0f}")
            if ilk["havuz_puani"] is not None:
                parca.append(f"havuz puanı {ilk['havuz_puani']:.0f}")
            if ilk["deger"] is not None:
                parca.append(f"değer {ilk['deger'] / 1e6:.2f} M €")
            st.caption("**Eklerken sistem:** " + (", ".join(parca) or "—")
                       + ". " + ("Sonuç o anda belliydi — göz testi sayılmaz."
                                 if ilk["sonuc_gorunur"] else
                                 "Sonuç henüz belli değil — göz testi sayılır."))
            b1, b2 = st.columns(2)
            if len(g) and b1.button("Havuzda aç", icon=":material/waves:",
                                    key=f"havuz_{kisi}", width="stretch"):
                st.switch_page("views/Havuz.py",
                               query_params={"oyuncu": g.iloc[0].anahtar})
            b_ = tmb.loc[kisi] if len(tmb) and kisi in tmb.index else None
            son_g = g.iloc[0] if len(g) else None
            TU.baglantilar(
                (b_.tm_ad if b_ is not None and isinstance(b_.tm_ad, str)
                 else (son_g.tam_ad if son_g is not None else k["ad"])),
                (b_.simdi_kulup if b_ is not None and isinstance(b_.simdi_kulup, str)
                 else (son_g.arama_kulup if son_g is not None else None)),
                b_.tm_url if b_ is not None else None)
            api_g = g[g.kaynak == HV.KAYNAK_API]
            if len(api_g) and b2.button("Scout dosyası", icon=":material/assignment:",
                                        key=f"dosya_{kisi}", width="stretch"):
                x = api_g.iloc[0]
                st.switch_page("views/Scout_Dosyasi.py", query_params={
                    "pid": int(x.player_id), "lid": int(x.league_id),
                    "sezon": int(x.season)})

        with st.expander(f"Göz testi raporu ({len(k['raporlar'])})"):
            for rp in reversed(k["raporlar"]):
                st.markdown(
                    f"**{rp.get('izleme_tarihi', '')} · {rp.get('karar', '')}** "
                    f"— {rp.get('mac') or 'maç belirtilmemiş'}, "
                    f"{rp.get('izlenen_dk', 0)} dk  \n"
                    f"Teknik {rp['teknik']} · Fizik {rp['fizik']} · "
                    f"Zekâ {rp['zeka']} · Karakter {rp['karakter']} · "
                    f"Sistem: {rp.get('sistem_uyumu', '—')}")
                for et, alan in [("Güçlü", "guclu"), ("Zayıf", "zayif")]:
                    if rp.get(alan):
                        st.caption(f"{et}: {rp[alan]}")
            _rapor_formu(kisi, k)

        with st.expander("Listeden çıkar"):
            st.caption("Çıkarmak yerine durumu **Bıraktım** yapabilirsin: "
                       "listede kalır, sonra ne olduğunu görürsün. Çıkarsan "
                       "notların takip günlüğünde durmaya devam eder.")
            onay = st.checkbox("Eminim", key=f"sil_onay_{kisi}")
            st.button("Listeden çıkar", key=f"sil_{kisi}", disabled=not onay,
                      on_click=_sil_cb, args=(kisi,),
                      icon=":material/bookmark_remove:")


def _html(s: str) -> str:
    import html
    return html.escape(s).replace("\n", "<br>")


secili = ev.selection.rows if ev is not None else []
hedef = st.query_params.get("kisi")
if secili and secili[0] < len(G):
    _ayrinti(G.iloc[secili[0]].kisi)
elif hedef and hedef in oy:
    _ayrinti(hedef)
else:
    ui.empty_state("Bir satıra tıkla",
                   "Notlar, durum, havuz geçmişi ve göz testi raporu burada "
                   "açılır.")
