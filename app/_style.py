"""Gorsel sistem: tasarim token'lari, CSS ve paylasilan UI bilesenleri.

TASARIM KARARLARI
  Tipografi : Fira Sans (govde) + Fira Code (sayilar).
              Sayi sutunlarinda TABULAR rakam sart - aksi halde her satirda
              rakam genisligi degisir ve tablo titrer.
  Renk      : mavi = veri/notr, amber = dikkat, kirmizi = risk, yesil = olumlu.
              Skor renkleri kirmizi-yesil DEGIL; renk korlugu icin mavi tonlu
              sirali skala + her zaman gorunur sayi (renk tek basina bilgi tasimaz).
  Yogunluk  : 8/10 - veri araci. Bosluk olcegi 4/8/12/16/24/32.
  Hareket   : 2/10 - yalnizca durum gecisleri, dekoratif animasyon yok.
"""

from __future__ import annotations

import streamlit as st

# --------------------------------------------------------------- token'lar
COLORS = {
    "primary": "#1E40AF",
    "primary_soft": "#EFF4FF",
    "secondary": "#3B82F6",
    "accent": "#B45309",
    "accent_soft": "#FEF3C7",
    "bg": "#F8FAFC",
    "surface": "#FFFFFF",
    "fg": "#0F172A",
    "fg_muted": "#475569",
    "fg_subtle": "#64748B",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "danger": "#B91C1C",
    "danger_soft": "#FEE2E2",
    "success": "#047857",
    "success_soft": "#D1FAE5",
}

# Percentile/skor icin sirali mavi skala - renk korlugu guvenli.
# Kirmizi-yesil skala bilincli olarak KULLANILMIYOR (§10 color-guidance).
SCORE_SCALE = [
    [0.00, "#F1F5F9"],
    [0.25, "#DBEAFE"],
    [0.50, "#93C5FD"],
    [0.75, "#3B82F6"],
    [1.00, "#1E3A8A"],
]

PLOTLY_TEMPLATE = {
    "layout": {
        "font": {"family": "Fira Sans, system-ui, sans-serif", "size": 13,
                 "color": COLORS["fg"]},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": ["#1E40AF", "#B45309", "#047857", "#7C3AED", "#0891B2"],
        "xaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border_strong"],
                  "linecolor": COLORS["border_strong"], "tickfont": {"size": 12}},
        "yaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border_strong"],
                  "linecolor": COLORS["border_strong"], "tickfont": {"size": 12}},
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "hoverlabel": {"font": {"family": "Fira Sans", "size": 13},
                       "bgcolor": COLORS["surface"], "bordercolor": COLORS["border_strong"]},
        "legend": {"orientation": "h", "y": -0.16, "x": 0},
    }
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
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
  --c-primary:#1E40AF; --c-primary-soft:#EFF4FF; --c-accent:#B45309;
  --c-bg:#F8FAFC; --c-surface:#FFFFFF; --c-fg:#0F172A; --c-fg-muted:#475569;
  --c-fg-subtle:#64748B; --c-border:#E2E8F0; --c-border-strong:#CBD5E1;
  --c-danger:#B91C1C; --c-success:#047857;
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-6:24px; --s-8:32px;
  --r-sm:6px; --r-md:8px; --r-lg:12px;
  --t:160ms cubic-bezier(.4,0,.2,1);
}

html, body, [class*="css"], .stApp {
  font-family:'Fira Sans', system-ui, -apple-system, sans-serif;
  color:var(--c-fg);
}

/* --- tipografi olcegi: 12 13 14 16 20 26 32 --------------------------- */
h1, h2, h3, h4 { font-family:'Fira Sans', sans-serif; letter-spacing:-.015em; color:var(--c-fg); }
h1 { font-size:1.9rem !important; font-weight:700 !important; line-height:1.2 !important; }
h2 { font-size:1.3rem !important; font-weight:600 !important; margin-top:var(--s-6) !important; }
h3 { font-size:1.05rem !important; font-weight:600 !important; }
p, li, .stMarkdown { font-size:.95rem; line-height:1.6; }

/* SAYILAR: tabular rakam - sutunlar hizali kalsin, tablo titremesin */
[data-testid="stMetricValue"], .stDataFrame, code, pre,
[data-testid="stTable"], .num {
  font-family:'Fira Code','SF Mono',Menlo,monospace !important;
  font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1;
}

/* --- sayfa govdesi ---------------------------------------------------- */
.block-container { padding-top:var(--s-6) !important; padding-bottom:var(--s-8) !important;
                   max-width:1500px; }

/* --- sayfa basligi ---------------------------------------------------- */
.pg-head { border-bottom:1px solid var(--c-border); padding-bottom:var(--s-3);
           margin-bottom:var(--s-6); }
.pg-head .t { display:flex; align-items:center; gap:var(--s-2);
              font-size:1.55rem; font-weight:700; line-height:1.25; }
.pg-head .s { color:var(--c-fg-muted); font-size:.9rem; margin-top:var(--s-1);
              max-width:74ch; line-height:1.55; }

/* --- KPI serisi ------------------------------------------------------- */
[data-testid="stMetric"] {
  background:var(--c-surface); border:1px solid var(--c-border);
  border-radius:var(--r-md); padding:var(--s-3) var(--s-4);
}
[data-testid="stMetricLabel"] p {
  font-size:.72rem !important; font-weight:600 !important; letter-spacing:.04em;
  text-transform:uppercase; color:var(--c-fg-subtle) !important;
}
[data-testid="stMetricValue"] { font-size:1.5rem !important; font-weight:600 !important;
                                color:var(--c-fg) !important; }

/* --- rozetler: renk TEK BASINA bilgi tasimaz, hep metin var ----------- */
.bdg { display:inline-flex; align-items:center; gap:5px; font-size:.72rem;
       font-weight:600; padding:3px 9px; border-radius:999px;
       border:1px solid transparent; white-space:nowrap; line-height:1.4; }
.bdg-ok   { background:#D1FAE5; color:#065F46; border-color:#A7F3D0; }
.bdg-warn { background:#FEF3C7; color:#92400E; border-color:#FDE68A; }
.bdg-risk { background:#FEE2E2; color:#991B1B; border-color:#FECACA; }
.bdg-info { background:var(--c-primary-soft); color:#1E3A8A; border-color:#BFDBFE; }
.bdg-mute { background:#F1F5F9; color:#475569; border-color:#E2E8F0; }

/* --- oyuncu basligi (8.4): Havuz karti, Takip, Oyuncu ayni gorunur ---- */
.oy-bas { margin:2px 0 10px; }
.oy-bas .ad { font-size:1.45rem; font-weight:700; line-height:1.2;
              letter-spacing:-.015em; color:var(--c-fg); }
.oy-bas .alt { color:var(--c-fg-muted); font-size:.86rem; margin-top:3px; }
.oy-bas .rz { display:flex; gap:6px; flex-wrap:wrap; margin-top:9px; }

/* --- kenar cubugu ----------------------------------------------------- */
[data-testid="stSidebar"] { background:var(--c-surface); border-right:1px solid var(--c-border); }
[data-testid="stSidebar"] h2 { font-size:.75rem !important; font-weight:700 !important;
  text-transform:uppercase; letter-spacing:.06em; color:var(--c-fg-subtle) !important;
  margin-top:var(--s-6) !important; margin-bottom:var(--s-2) !important; }
[data-testid="stSidebar"] label p { font-size:.83rem !important; font-weight:500 !important;
  color:var(--c-fg-muted) !important; }
[data-testid="stSidebar"] hr { margin:var(--s-4) 0 !important; border-color:var(--c-border); }

/* --- kontroller ------------------------------------------------------- */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
  border-radius:var(--r-sm); font-weight:600; font-size:.85rem;
  transition:background var(--t), border-color var(--t), color var(--t);
  min-height:38px; cursor:pointer;
}
.stButton button:focus-visible, .stDownloadButton button:focus-visible,
input:focus-visible, select:focus-visible, [role="combobox"]:focus-visible {
  outline:2px solid var(--c-primary) !important; outline-offset:2px !important;
}
[data-baseweb="tag"] { background:var(--c-primary-soft) !important; color:#1E3A8A !important;
                       border-radius:var(--r-sm) !important; }

/* --- tablolar --------------------------------------------------------- */
.stDataFrame { border:1px solid var(--c-border); border-radius:var(--r-md); overflow:hidden; }
/* Baslik rengi #64748B degil #475569 - kucuk buyuk-harf metinde
   #64748B/#F1F5F9 kontrasti 4.34 kaliyordu (AA esigi 4.5). Olculdu. */
.stDataFrame thead th { background:#F1F5F9 !important; font-weight:600 !important;
  font-size:.76rem !important; text-transform:uppercase; letter-spacing:.03em;
  color:var(--c-fg-muted) !important; }

/* --- sekmeler --------------------------------------------------------- */
.stTabs [data-baseweb="tab-list"] { gap:var(--s-1); border-bottom:1px solid var(--c-border); }
.stTabs [data-baseweb="tab"] { font-weight:600; font-size:.88rem; padding:var(--s-2) var(--s-4); }

/* --- kutular ---------------------------------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:var(--r-lg) !important; }
[data-testid="stExpander"] details { border:1px solid var(--c-border) !important;
  border-radius:var(--r-md) !important; background:var(--c-surface); }
[data-testid="stAlert"] { border-radius:var(--r-md); font-size:.88rem; }

/* --- kucuk ekran ------------------------------------------------------ */
@media (max-width:768px) {
  .block-container { padding-left:var(--s-3) !important; padding-right:var(--s-3) !important; }
  h1 { font-size:1.5rem !important; }
  .pg-head .t { font-size:1.25rem; }
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
        f'style="font-size:25px;color:var(--c-primary)">{icon}</span>' if icon else ""
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


def oyuncu_basligi(ad: str, alt: str = "",
                   rozetler: list[tuple[str, str]] | tuple = ()) -> None:
    """Oyuncu kartlarinin ortak basligi (8.4): ad, alt satir, rozetler.
    Havuz karti, Takip ayrintisi ve Oyuncu sayfasi ayni gorunur."""
    import html
    st.markdown(
        f'<div class="oy-bas"><div class="ad">{html.escape(str(ad))}</div>'
        + (f'<div class="alt">{html.escape(str(alt))}</div>' if alt else "")
        + ('<div class="rz">' + "".join(badge(html.escape(str(t)), k)
                                        for t, k in rozetler) + "</div>"
           if rozetler else "")
        + "</div>",
        unsafe_allow_html=True)


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
