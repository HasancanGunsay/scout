"""Kimlik eslestirme - §1.6.

PROBLEM: "Vinícius José Paixão de Oliveira Júnior" (bir kaynak) =
"Vinicius Junior" (baska kaynak) = "Vini Jr." (ucuncu kaynak).
Brezilya'da herkesin lakabi var, isim eslestirmesi tek basina cuvalliyor.

OLCULEN GERCEK (§13.1): eslesmeyenlerin cogu ALGORITMA sorunu degil,
KAPSAM sorunu - Transfermarkt CC0 veri seti Serie B oyuncularinin
%43'unu hic icermiyor. Tavan Serie B'de %56.5, Serie A'da %96.6.

STRATEJI: isimle degil, DOGUM TARIHI + UYRUK ile blokla.
Bu blok son derece ayirt edici - TM'de 43.248 blogun hepsi tek kisilik.
Isim yalnizca blok icinde birden fazla aday varken devreye giriyor.

Boylece "Alemão" = "Ironi Daponte" gibi lakap vakalari da cozuluyor:
isimler hic benzemese bile blok tekse eslesme guvenli.

DIKKAT - 'TEK ADAY' TEK BASINA YETMEZ (§13.2)
Ilk uygulama "blokta tek aday varsa kabul et" diyordu ve YANLIS ESLESMELER
uretti: 'Gabriel Silva' -> 'Matheus Teixeira', 'Pablo Dyego' -> 'Guilherme
Garutti'. Bunlar lakap degil, ayni gun dogmus FARKLI Brezilyalilar.
Oyuncu TM'de yoksa, blok "tek" olur ama o tek kayit baska biridir.

Isim skoru dagilimi olcuIdu ve IKI KUTUPLU cikti:
  376 vaka skor >=90  (gercek eslesme)
   63 vaka skor <60   (tesaduf)
  arada neredeyse hic kutle yok
Bu yuzden 85 esigi temiz bir kesim yapiyor.

ILKE: yanlis piyasa degeri, eksik piyasa degerinden BETERDIR. Scout'u
yanlis oyuncunun pesine dusurur veya iyi oyuncuyu eledirir. Supheliyi
otomatik kabul etmek yerine manuel kuyruga aliyoruz.

GUVEN SEVIYELERI
  A  tek aday (dogum+uyruk) VE isim skoru >=85  -> otomatik kabul
  B  coklu aday, isim skoru >=85 ve fark >=10   -> otomatik kabul
  C  isim skoru 65-85                           -> MANUEL ONAY (kabul edilmez)
  D  isim skoru <65 / cakisma                   -> reddedilir
  -  aday yok                                   -> TM'de mevcut degil
"""

from __future__ import annotations

import unicodedata

import pandas as pd
from rapidfuzz import fuzz

# Otomatik kabul icin asgari isim skoru. Olcumle belirlendi - bkz. modul dokumani.
AUTO_ACCEPT_SCORE = 85.0
REVIEW_SCORE = 65.0

# Kimlik olarak KULLANILABILEN eslesmeler: otomatik kabul (A, B) + manuel
# onay (M). C (belirsiz) ve D (reddedildi) kimlik DEGILDIR (PLAN §13.3).
KABUL = ("A", "B", "M")


def kabul_disini_bosalt(links: pd.DataFrame) -> pd.DataFrame:
    """tm_id YALNIZ kabul edilmis eslesmede dolu kalir; aday aday_tm_id'de.

    NEDEN (1 Eki 2026, PLAN §60): build_links her oyuncu icin "en iyi
    adayi" tm_id'ye yaziyordu - reddedilenler dahil. Sonuc olcumu, deger
    ozelligi, 'sonra' tablosu ve arayuz tm_id uzerinden JOIN yapiyordu ve
    guven seviyesine bakmiyordu: sonuc satirlarinin %26'si BASKA BIR
    KISININ kariyerinden olculdu. Filtreyi her tuketiciye tek tek
    eklemek yerine kaynakta bosaltiyoruz: tm_id uzerinden yapilan her
    JOIN kendiliginden dogru olur, yeni kod ayni hatayi yapamaz.
    aday_tm_id yalniz manuel onay kuyrugu icindir.
    """
    out = links.copy()
    out["aday_tm_id"] = out["tm_id"]
    out.loc[~out["confidence"].isin(KABUL), "tm_id"] = None
    return out


def normalize(s: object) -> str:
    """Aksanlari soy, kucult, noktalama temizle."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return " ".join(s.lower().split())


def variants(*parts: object) -> list[str]:
    """Bir kayittan olasi isim yazimlarini uret."""
    norm = [normalize(p) for p in parts if normalize(p)]
    out = set(norm)
    # ad + soyad birlesimleri
    if len(norm) >= 2:
        out.add(f"{norm[0]} {norm[1]}")
        out.add(f"{norm[1]} {norm[0]}")
    # cok parcali isimlerde son kelime cogu zaman ayirt edici
    for n in norm:
        toks = n.split()
        if len(toks) > 1:
            out.add(toks[-1])
            out.add(f"{toks[0]} {toks[-1]}")
    return [v for v in out if len(v) >= 2]


def name_score(a_variants: list[str], b_variants: list[str]) -> float:
    """En iyi eslesen varyant ciftinin skoru (0-100)."""
    best = 0.0
    for a in a_variants:
        for b in b_variants:
            s = max(fuzz.token_set_ratio(a, b), fuzz.WRatio(a, b))
            if s > best:
                best = s
                if best >= 100:
                    return 100.0
    return best


def build_links(api: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    """API oyuncularini Transfermarkt kayitlariyla esle.

    api : player_id, player_name, firstname, lastname, birth_date, nationality
    tm  : tm_id, name, first_name, last_name, date_of_birth, country_of_citizenship
    """
    api = api.copy()
    tm = tm.copy()
    api["_bd"] = pd.to_datetime(api["birth_date"], errors="coerce").dt.date
    tm["_bd"] = pd.to_datetime(tm["date_of_birth"], errors="coerce").dt.date
    api["_nat"] = api["nationality"].map(normalize)
    tm["_nat"] = tm["country_of_citizenship"].map(normalize)

    # dogum tarihine gore indeksle (uyruk esitligi blok icinde kontrol edilir)
    by_bd: dict = {}
    for rec in tm.dropna(subset=["_bd"]).to_dict("records"):
        by_bd.setdefault(rec["_bd"], []).append(rec)

    rows = []
    for a in api.to_dict("records"):
        pool = by_bd.get(a["_bd"], [])
        # once uyruk esleseni dene, yoksa tum dogum tarihi blogu
        same_nat = [t for t in pool if t["_nat"] and t["_nat"] == a["_nat"]]
        cands, nat_matched = (same_nat, True) if same_nat else (pool, False)

        base = {
            "player_id": a["player_id"],
            "player_name": a["player_name"],
            "birth_date": a["_bd"],
            "n_candidates": len(cands),
            "nat_matched": nat_matched,
        }

        if not cands:
            rows.append({**base, "tm_id": None, "tm_name": None,
                         "name_score": None, "club_score": None, "tm_club": None,
                         "confidence": "-",
                         "reason": "TM veri setinde aday yok"})
            continue

        av = variants(a["player_name"], a["firstname"], a["lastname"])
        a_club = normalize(a.get("team_name"))
        scored = []
        for t in cands:
            tv = variants(t["name"], t["first_name"], t["last_name"])
            s = name_score(av, tv)
            # KULUP KANITI: isim berabere kaldiginda kulup ayirt edici olur.
            # 'Zeca' gibi kisa lakaplarda birden fazla aday 100 alabiliyor;
            # oyuncunun 2024'te oynadigi takim TM'deki kulubuyle tutuyorsa
            # o aday one cikar. Sadece TIE-BREAK olarak kullaniliyor,
            # isim skorunun yerine gecmiyor.
            club = 0.0
            t_club = normalize(t.get("current_club_name"))
            if a_club and t_club:
                club = max(fuzz.token_set_ratio(a_club, t_club),
                           fuzz.partial_ratio(a_club, t_club))
            scored.append((s, club, t))

        # once isim, esitlikte kulup
        scored.sort(key=lambda x: (-x[0], -x[1]))
        top_score, top_club, top = scored[0]
        margin = top_score - (scored[1][0] if len(scored) > 1 else 0.0)
        # isim berabereyse ama kulup net ayirt ediyorsa marji kulupten devral
        if margin < 10 and len(scored) > 1 and top_club >= 85:
            club_margin = top_club - scored[1][1]
            if club_margin >= 30:
                margin = 10.0

        if len(cands) == 1 and nat_matched and top_score >= AUTO_ACCEPT_SCORE:
            conf = "A"
            reason = f"tek aday + isim skoru {top_score:.0f}"
        elif top_score >= AUTO_ACCEPT_SCORE and margin >= 10:
            conf = "B"
            reason = f"isim skoru {top_score:.0f}, fark {margin:.0f}"
        elif top_score >= REVIEW_SCORE:
            conf = "C"
            reason = f"belirsiz - isim skoru {top_score:.0f}, manuel onay gerekli"
        else:
            conf = "D"
            reason = (
                f"reddedildi - isim skoru {top_score:.0f}; "
                + ("blokta tek aday ama isim tutmuyor (muhtemelen ayni gun dogmus baskasi)"
                   if len(cands) == 1 else f"{len(cands)} aday arasindan ayirt edilemedi")
            )

        rows.append({**base, "tm_id": top["tm_id"], "tm_name": top["name"],
                     "name_score": round(top_score, 1),
                     "club_score": round(top_club, 1),
                     "tm_club": top.get("current_club_name"),
                     "confidence": conf, "reason": reason})

    links = pd.DataFrame(rows)

    # 1:1 zorla - ayni TM kaydina birden fazla API oyuncusu baglanmasin
    accepted = links[links.confidence.isin(["A", "B"])].copy()
    order = {"A": 0, "B": 1}
    accepted["_rank"] = accepted.confidence.map(order)
    accepted = accepted.sort_values(["_rank", "name_score"], ascending=[True, False])
    dupes = accepted.duplicated(subset=["tm_id"], keep="first")
    losers = set(accepted[dupes].player_id)
    links.loc[links.player_id.isin(losers), ["confidence", "reason"]] = [
        "D", "cakisma - ayni TM kaydina baska oyuncu baglandi"
    ]
    return links
