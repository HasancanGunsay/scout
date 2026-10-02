"""Gorsel sistem: tasarim token'lari, CSS ve paylasilan UI bilesenleri.

TASARIM KARARLARI ("Saha Analitik", 2 Eki 2026 - Google Stitch ile
tasarlandi, PLAN §64)
  Ruh       : Linear'in sakin kesinligi + Sofascore'un veri yogunlugu.
              Renk suslemek icin degil, DURUM ve HIYERARSI bildirmek icin.
  Tipografi : Inter (govde, basliklar) + JetBrains Mono (sayilar, etiketler).
              Sayi sutunlarinda TABULAR rakam sart - aksi halde her satirda
              rakam genisligi degisir ve tablo titrer.
  Yuzey     : #F8FAFC zemin, beyaz kartlar, 1px #E2E8F0 kenarlik, 12px kose;
              golge yok denecek kadar hafif. Gezinme paneli lacivert
              (tema: .streamlit/config.toml [theme.sidebar]).
  Yuzdelik  : <50 gri · 50-74 mavi · >=75 yesil (Sofascore kademesi).
              Kirmizi-yesil DEGIL; deger her zaman yazili (renk tek basina
              bilgi tasimaz, §10).
  Yogunluk  : 8/10 - veri araci. Bosluk olcegi 4/8/12/16/24/32.
  Hareket   : 2/10 - yalnizca durum gecisleri, dekoratif animasyon yok.
"""

from __future__ import annotations

import html as _html

import streamlit as st

# --------------------------------------------------------------- token'lar
COLORS = {
    "primary": "#1D4ED8",
    "primary_soft": "#EFF6FF",
    "secondary": "#3B82F6",
    "accent": "#D97706",
    "accent_soft": "#FEF3C7",
    "bg": "#F8FAFC",
    "surface": "#FFFFFF",
    "fg": "#0F172A",
    "fg_muted": "#475569",
    "fg_subtle": "#64748B",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "danger": "#DC2626",
    "danger_soft": "#FEE2E2",
    "success": "#059669",
    "success_soft": "#D1FAE5",
    "nav": "#213145",
}

# Percentile/skor icin sirali mavi skala (isi haritalari, radar dolgusu).
# Kirmizi-yesil skala bilincli olarak KULLANILMIYOR (§10 color-guidance).
SCORE_SCALE = [
    [0.00, "#F1F5F9"],
    [0.25, "#DBEAFE"],
    [0.50, "#93C5FD"],
    [0.75, "#3B82F6"],
    [1.00, "#1E3A8A"],
]


def yuzdelik_renk(p: float) -> str:
    """Yuzdelik cubugu kademesi (Stitch/Sofascore): <50 gri, 50-74 mavi,
    >=75 yesil. Deger her zaman cubugun yaninda yazili."""
    if p is None or p != p:
        return "#CBD5E1"
    return "#059669" if p >= 75 else ("#3B82F6" if p >= 50 else "#94A3B8")


PLOTLY_TEMPLATE = {
    "layout": {
        "font": {"family": "Inter, system-ui, sans-serif", "size": 13,
                 "color": COLORS["fg"]},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": ["#1D4ED8", "#D97706", "#059669", "#7C3AED", "#0891B2"],
        "xaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border_strong"],
                  "linecolor": COLORS["border_strong"], "tickfont": {"size": 12}},
        "yaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border_strong"],
                  "linecolor": COLORS["border_strong"], "tickfont": {"size": 12}},
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "hoverlabel": {"font": {"family": "Inter", "size": 13},
                       "bgcolor": COLORS["surface"], "bordercolor": COLORS["border_strong"]},
        "legend": {"orientation": "h", "y": -0.16, "x": 0},
    }
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
/* Material Symbols - emoji yerine gercek ikon seti (§4 no-emoji-icons).
   <link> etiketi Streamlit tarafindan temizlendigi icin @import kullaniliyor. */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');

.material-symbols-outlined {
  font-family:'Material Symbols Outlined'; font-weight:normal; font-style:normal;
  line-height:1; letter-spacing:normal; text-transform:none; display:inline-block;
  white-space:nowrap; word-wrap:normal; direction:ltr;
  -webkit-font-feature-settings:'liga'; -webkit-font-smoothing:antialiased;
}

:root {
  --c-primary:#1D4ED8; --c-primary-soft:#EFF6FF; --c-accent:#D97706;
  --c-bg:#F8FAFC; --c-surface:#FFFFFF; --c-fg:#0F172A; --c-fg-muted:#475569;
  --c-fg-subtle:#64748B; --c-border:#E2E8F0; --c-border-strong:#CBD5E1;
  --c-danger:#DC2626; --c-success:#059669; --c-nav:#213145;
  --f-mono:'JetBrains Mono','SF Mono',Menlo,monospace;
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-6:24px; --s-8:32px;
  --r-sm:6px; --r-md:8px; --r-lg:12px;
  --t:160ms cubic-bezier(.4,0,.2,1);
}

html, body, [class*="css"], .stApp {
  font-family:'Inter', system-ui, -apple-system, sans-serif;
  color:var(--c-fg);
  font-feature-settings:"cv02","cv03","cv04","tnum";
}

/* --- tipografi olcegi: 12 13 14 16 20 26 30 --------------------------- */
h1, h2, h3, h4 { font-family:'Inter', sans-serif; letter-spacing:-.02em; color:var(--c-fg); }
h1 { font-size:1.85rem !important; font-weight:600 !important; line-height:1.25 !important; }
h2 { font-size:1.25rem !important; font-weight:600 !important; margin-top:var(--s-6) !important; }
h3 { font-size:1.02rem !important; font-weight:600 !important; }
p, li, .stMarkdown { font-size:.92rem; line-height:1.6; }

/* SAYILAR: tabular rakam - sutunlar hizali kalsin, tablo titremesin */
[data-testid="stMetricValue"], .stDataFrame, code, pre,
[data-testid="stTable"], .num {
  font-family:var(--f-mono) !important;
  font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1;
}

/* --- sayfa govdesi ---------------------------------------------------- */
.block-container { padding-top:var(--s-6) !important; padding-bottom:var(--s-8) !important;
                   max-width:1500px; }

/* --- sayfa basligi ---------------------------------------------------- */
.pg-head { padding-bottom:var(--s-2); margin-bottom:var(--s-4); }
.pg-head .t { display:flex; align-items:center; gap:var(--s-2);
              font-size:1.85rem; font-weight:600; line-height:1.2;
              letter-spacing:-.02em; }
.pg-head .s { color:var(--c-fg-muted); font-size:.92rem; margin-top:6px;
              max-width:80ch; line-height:1.55; }

/* --- KPI kutulari (Stitch: buyuk mono deger, kucuk buyuk-harf etiket) -- */
[data-testid="stMetric"] {
  background:var(--c-surface); border:1px solid var(--c-border);
  border-radius:var(--r-lg); padding:14px 18px;
  box-shadow:0 1px 2px rgba(15,23,42,.04);
}
[data-testid="stMetricLabel"] p {
  font-family:var(--f-mono) !important;
  font-size:.7rem !important; font-weight:500 !important; letter-spacing:.06em;
  text-transform:uppercase; color:var(--c-fg-subtle) !important;
}
[data-testid="stMetricValue"] { font-size:1.6rem !important; font-weight:600 !important;
                                color:var(--c-fg) !important; letter-spacing:-.02em; }

/* --- rozetler: renk TEK BASINA bilgi tasimaz, hep metin var ----------- */
.bdg { display:inline-flex; align-items:center; gap:5px;
       font-family:var(--f-mono); font-size:.7rem; font-weight:500;
       padding:2px 8px; border-radius:5px;
       border:1px solid transparent; white-space:nowrap; line-height:1.5; }
.bdg-ok   { background:#ECFDF5; color:#047857; border-color:#A7F3D0; }
.bdg-warn { background:#FFFBEB; color:#B45309; border-color:#FCD34D; }
.bdg-risk { background:#FEF2F2; color:#B91C1C; border-color:#FECACA; }
.bdg-info { background:var(--c-primary-soft); color:#1E40AF; border-color:#BFDBFE; }
.bdg-mute { background:#F1F5F9; color:#475569; border-color:#E2E8F0; }

/* --- oyuncu basligi (8.4 + Stitch): bas harf avatari + ad + rozetler --- */
.oy-bas { display:flex; gap:14px; align-items:flex-start; margin:2px 0 12px; }
.oy-bas .av { flex:0 0 auto; width:48px; height:48px; border-radius:10px;
              background:#EFF6FF; border:1px solid #BFDBFE; color:#1D4ED8;
              display:flex; align-items:center; justify-content:center;
              font-weight:700; font-size:1rem; letter-spacing:.02em; }
.oy-bas .ad { font-size:1.45rem; font-weight:600; line-height:1.2;
              letter-spacing:-.02em; color:var(--c-fg); }
.oy-bas .alt { color:var(--c-fg-muted); font-size:.86rem; margin-top:3px; }
.oy-bas .rz { display:flex; gap:6px; flex-wrap:wrap; margin-top:9px; }

/* --- istatistik kutulari (Stitch karti): dar sutunda da sigar -------- */
.stk { display:grid; grid-template-columns:repeat(auto-fit, minmax(96px, 1fr));
       gap:8px; margin:6px 0 12px; }
.stk .k { border:1px solid var(--c-border); border-radius:10px;
          background:var(--c-surface); padding:10px 12px 9px; min-width:0; }
.stk .e { font-family:var(--f-mono); font-size:.64rem; letter-spacing:.07em;
          text-transform:uppercase; color:var(--c-fg-subtle);
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stk .v { font-family:var(--f-mono); font-size:1.28rem; font-weight:600;
          color:var(--c-fg); margin-top:3px; letter-spacing:-.02em;
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stk .v small { font-size:.7rem; color:var(--c-fg-subtle); font-weight:500;
                margin-left:2px; }
.stk .b { height:3px; border-radius:2px; background:#F1F5F9; margin-top:7px;
          overflow:hidden; }
.stk .b i { display:block; height:100%; border-radius:2px; }

/* --- gezinme paneli (renkler tema'dan; burada yalniz tipografi) -------- */
[data-testid="stSidebarNavSeparator"] { border-color:#34475F !important; }
[data-testid="stNavSectionHeader"] {
  font-family:var(--f-mono) !important; font-size:.68rem !important;
  letter-spacing:.1em; text-transform:uppercase; color:#94A3B8 !important;
}
[data-testid="stSidebar"] h2 { font-family:var(--f-mono) !important;
  font-size:.7rem !important; font-weight:500 !important;
  text-transform:uppercase; letter-spacing:.1em; color:#94A3B8 !important;
  margin-top:var(--s-6) !important; margin-bottom:var(--s-2) !important; }
[data-testid="stSidebar"] hr { margin:var(--s-4) 0 !important; border-color:#34475F; }
/* koyu panelde aciklama metni okunur kalsin (varsayilan gri kontrasti dusuk) */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#A9B6C8 !important; }

/* --- kontroller ------------------------------------------------------- */
.stButton button, .stDownloadButton button, .stFormSubmitButton button,
.stLinkButton a {
  font-weight:500; font-size:.85rem;
  transition:background var(--t), border-color var(--t), color var(--t);
  min-height:36px; cursor:pointer;
}
.stButton button:focus-visible, .stDownloadButton button:focus-visible,
input:focus-visible, select:focus-visible, [role="combobox"]:focus-visible {
  outline:2px solid var(--c-primary) !important; outline-offset:2px !important;
}

/* --- tablolar --------------------------------------------------------- */
.stDataFrame { border-radius:var(--r-lg); overflow:hidden; }

/* --- sekmeler --------------------------------------------------------- */
.stTabs [data-baseweb="tab-list"] { gap:var(--s-1); border-bottom:1px solid var(--c-border); }
.stTabs [data-baseweb="tab"] { font-weight:500; font-size:.88rem; padding:var(--s-2) var(--s-4); }

/* --- kartlar (cerceveli kapsayicilar) --------------------------------- */
.stMain [data-testid="stVerticalBlockBorderWrapper"],
.stMain [data-testid="stVerticalBlock"][class*="border"] {
  background:var(--c-surface); border-radius:var(--r-lg) !important; }
[data-testid="stExpander"] details { border:1px solid var(--c-border) !important;
  border-radius:var(--r-md) !important; background:var(--c-surface); }
[data-testid="stAlert"] { border-radius:var(--r-md); font-size:.88rem; }

/* --- kucuk ekran ------------------------------------------------------ */
@media (max-width:768px) {
  .block-container { padding-left:var(--s-3) !important; padding-right:var(--s-3) !important; }
  h1 { font-size:1.5rem !important; }
  .pg-head .t { font-size:1.3rem; }
}

/* --- hareket azaltma tercihi ------------------------------------------ */
@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; }
}

/* Streamlit markasi - is araci, dagitim menusu gereksiz */
[data-testid="stToolbar"] { display:none; }
footer { display:none; }
</style>
"""


def inject() -> None:
    """CSS'i sayfaya bir kez enjekte et."""
    st.markdown(_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------- bilesenler
def page_header(title: str, subtitle: str = "", icon: str | None = None) -> None:
    """Tutarli sayfa basligi. Ikon Material Symbols adi (emoji degil)."""
    ico = (
        f'<span class="material-symbols-outlined" aria-hidden="true" '
        f'style="font-size:26px;color:var(--c-primary)">{icon}</span>' if icon else ""
    )
    st.markdown(
        f'<div class="pg-head"><div class="t">{ico}{title}</div>'
        + (f'<div class="s">{subtitle}</div>' if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "info") -> str:
    """Rozet HTML'i. kind: ok | warn | risk | info | mute"""
    return f'<span class="bdg bdg-{kind}">{text}</span>'


def badges(*items: tuple[str, str]) -> None:
    st.markdown(
        '<div style="display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 12px">'
        + "".join(badge(t, k) for t, k in items)
        + "</div>",
        unsafe_allow_html=True,
    )


def bas_harf(ad: str) -> str:
    """'F. Esposito' -> 'FE', 'Lamine Yamal' -> 'LY', 'Zeca' -> 'ZE'."""
    parca = [p for p in str(ad).replace(".", " ").split() if p]
    if len(parca) >= 2:
        return (parca[0][0] + parca[-1][0]).upper()
    return str(ad)[:2].upper()


def oyuncu_basligi(ad: str, alt: str = "",
                   rozetler: list[tuple[str, str]] | tuple = ()) -> None:
    """Oyuncu kartlarinin ortak basligi (8.4, Stitch): bas harf avatari,
    ad, alt satir, rozetler. Havuz karti, Takip ve Oyuncu ayni gorunur."""
    st.markdown(
        f'<div class="oy-bas"><div class="av">{_html.escape(bas_harf(ad))}</div>'
        f'<div><div class="ad">{_html.escape(str(ad))}</div>'
        + (f'<div class="alt">{_html.escape(str(alt))}</div>' if alt else "")
        + ('<div class="rz">' + "".join(badge(_html.escape(str(t)), k)
                                        for t, k in rozetler) + "</div>"
           if rozetler else "")
        + "</div></div>",
        unsafe_allow_html=True)


def stat_kutulari(kutular: list[tuple]) -> None:
    """Stitch kartindaki istatistik kutulari: (etiket, deger[, birim[, oran]]).
    oran 0-1 verilirse altta ince doluluk cizgisi (yuzdelik renk kademesi).
    st.metric dar sutunda degeri kesiyordu ("3.1…"); bunlar sigar."""
    parca = []
    for k in kutular:
        etiket, deger = k[0], k[1]
        birim = k[2] if len(k) > 2 else ""
        oran = k[3] if len(k) > 3 else None
        bar = ""
        if oran is not None and oran == oran:
            o = max(0.0, min(1.0, float(oran)))
            bar = (f'<div class="b"><i style="width:{100 * o:.0f}%;'
                   f'background:{yuzdelik_renk(100 * o)}"></i></div>')
        parca.append(
            f'<div class="k" data-etiket="{_html.escape(etiket)}">'
            f'<div class="e">{_html.escape(etiket)}</div>'
            f'<div class="v">{_html.escape(str(deger))}'
            + (f"<small>{_html.escape(birim)}</small>" if birim else "")
            + f"</div>{bar}</div>")
    st.markdown(f'<div class="stk">{"".join(parca)}</div>', unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    st.markdown(f"### {title}")
    if hint:
        st.caption(hint)


def empty_state(title: str, hint: str = "") -> None:
    """Bos durum - kullaniciya ne yapacagini soyler."""
    st.markdown(
        f'<div style="text-align:center;padding:48px 24px;border:1px dashed '
        f'var(--c-border-strong);border-radius:12px;background:var(--c-surface)">'
        f'<div style="font-weight:600;color:var(--c-fg-muted);font-size:.95rem">{title}</div>'
        + (f'<div style="color:var(--c-fg-subtle);font-size:.85rem;margin-top:6px">{hint}</div>'
           if hint else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def apply_plotly(fig):
    """Grafige ortak temayi uygula."""
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig
