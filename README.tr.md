# Scout

Düşük görünürlüklü liglerde genç yetenek keşfi için veri sistemi.

| Doküman | İçerik |
|---|---|
| **[ROADMAP.md](ROADMAP.md)** | **Buradan başla.** Sistem nerede, ne yapılacak, neler denendi ve reddedildi |
| [PLAN.md](PLAN.md) | Tasarım, gerekçeler, ölçüm bulguları |
| [GELISTIRME.md](GELISTIRME.md) | Profesyonel seviye geliştirme planı: FAZ 9–15 (veri, lig genişlemesi, model, mühendislik, ürün) |

Sistem denetimi: `python scripts/audit.py` — 41 otomatik kontrol · testler: `python -m pytest` — 353 test.

## Kurulum

Zaten kurulu. Yeniden kurmak gerekirse:

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install httpx tenacity duckdb pandas scikit-learn statsmodels streamlit plotly rapidfuzz pydantic pyyaml
```

API anahtarı `.env` dosyasında (repoya girmez). Şablon: `.env.example`.

## Arayüzü başlat

```bash
.venv/Scripts/python.exe -m streamlit run app/Home.py
```

Tarayıcıda `http://localhost:8501` açılır. Sayfalar iş akışına göre gruplu:

**Scout** — okyanustan havuz → takip listesi → oyuncu → göz testi

| Sayfa | Ne için |
|---|---|
| **Havuz** | Giriş sayfası. API 2022–24 (düşük görünürlük dahil) ve TM 2025/26 havuzu; grup içi havuz puanı, istatistik aileleri, oyuncu kartı, Sofascore/TM bağlantısı (PLAN §58, §61) |
| **Takip listesi** | İzlediğin oyuncular: durum, not günlüğü, **göz testi raporu**. Senin kararların sisteme buradan girer (PLAN §59) |
| **Oyuncu** | Tek oyuncu-sezonun bütün görünümü — sekmeler: **Scout dosyası** (iddia, kanıt, yörünge, emsal, riskler, verinin göremediği), **Profil** (radar, rol skorları, skor açıklaması), **Benzer oyuncular** (PLAN §62) |
| **Karşılaştırma** | 2-5 oyuncu yan yana; takip listendekiler hazır gelir |

**Analiz** — farklı merceklerle arama

| Sayfa | Ne için |
|---|---|
| **Keşif (rol şablonu)** | Mevki + rol şablonu sayfanın üstünde; canlı ağırlık slider'ları. **Güven** sütunu skordan bağımsızdır — bkz. aşağı. |
| **Mevki sıralaması** | Her mevkiden liste ve o listenin gerçekte ne kadar tuttuğu (güven aralığıyla) |
| **Yükselenler** | Aynı oyuncunun 2022→2024 değişimi. Skorun kendisi değil **yönü** — sabit rol üzerinden, PLAN §24. |
| **Kadro analizi** | Bir kadronun mevki mevki ihtiyacı |
| **Laboratuvar** | Serbest sorgulama: dağılım grafiği, lig liderleri (metrik aileleri), doğrudan SQL |

**Sistem**

| Sayfa | Ne için |
|---|---|
| **Hesap defteri** | Sistemin karnesi: iddialar, kalibrasyon, senin seçimlerin |
| **Veri** | Otomatik çalışma, kota, toplama ilerlemesi, bilinen kör noktalar; **Eşleşme kuyruğu** sekmesi |

### Skor vs Güven — karıştırma

| Gösterge | Neyi söyler |
|---|---|
| **Skor** | Ne kadar iyi oynadı (rol ağırlıkları × kohort percentile'ları) |
| **Yaş eğrisi düzeltmesi** | Skor eksi yaşında beklenen seviye. **Yalnızca ≤23 yaş filtresinde sunulur** — üstünde ölçüldü ve zararlı (PLAN §26) |
| **Güven** | Kulübü ona ne kadar güvendi (yaşıtları arasında aldığı dakika) |
| **Kapsam** | Ağırlığın ne kadarı hesaplanabildi (1,00 = tüm metrikler var) |

Güven **skora dahil değildir**. Geriye dönük testte U21'de tek başına en
güçlü sinyaldi (PLAN §18.4), ama dakika hem sebep hem sonuç olduğu için
ağırlığa konsaydı listeler "çok oynayan yaşlı oyuncu"ya kayardı.

### Görsel sistem

Tasarım token'ları ve paylaşılan bileşenler [app/_style.py](app/_style.py) içinde,
tema [.streamlit/config.toml](.streamlit/config.toml) içinde.

- **Tipografi:** Fira Sans (gövde) + Fira Code (sayılar, tabular rakam)
- **Renk:** mavi = veri, amber = dikkat, kırmızı = risk, yeşil = olumlu
- **İkonlar:** Material Symbols — emoji kullanılmıyor
- **Skor renkleri:** sıralı mavi skala (kırmızı-yeşil değil, renk körlüğü güvenli);
  renk yalnızca yardımcı, sayı her zaman görünür
- Tüm metin/arkaplan çiftleri WCAG AA (≥4.5:1) doğrulandı
- `prefers-reduced-motion` destekli, 375px'e kadar yatay taşma yok

## Günlük iş akışı

API-Football ücretsiz planı **günde 100 istek** veriyor ve kota 00:00 UTC'de sıfırlanıyor.
Veri toplama bu yüzden günlere yayılıyor. Her gün bir kez:

```bash
.venv/Scripts/python.exe scripts/ingest_players.py
```

Kaldığı yerden devam eder, kota bitince temiz durur. Sonra tabloyu tazele:

```bash
.venv/Scripts/python.exe scripts/build_db.py
```

Durumu istek harcamadan görmek için:

```bash
.venv/Scripts/python.exe scripts/ingest_players.py --plan
```

## Script'ler

| Script | Ne yapar | API maliyeti |
|---|---|---|
| `probe_api_coverage.py` | `/leagues` → lig × sezon kapsam matrisi | 1 (sonra önbellek) |
| `probe_players_shape.py` | `/players` yanıtının alan yapısını inceler | probe başına 1 |
| `analyze_players_fields.py` | Önbellekten metrik doluluk oranı | **0** |
| `ingest_players.py` | Asıl veri toplayıcı, kaldığı yerden devam eder | kota kadar |
| `build_db.py` | Ham JSON → `data/scout.duckdb` | **0** |
| `build_features.py` | per-90, shrinkage, percentile, yaş → `player_features` | **0** |
| `build_links.py` | TM ↔ API eşleşmesi → `player_links` (`tm_id` yalnız doğrulanmışta), `player_meta` | **0** |
| `build_scores.py` | rol şablonlarıyla skorlar → `player_scores` | **0** |
| `build_outcomes.py` / `build_sonra.py` | 12 ay sonrası: izlenen 1. ligde yer edindi mi | **0** |
| `train_model.py` | API modeli; `--kaydet-yalniz` üretim modelini yazar | **0** |
| `build_ranking.py` | dışarıdan tahmin + kalibrasyon → `player_ranking`, `player_tahmin` | **0** |
| `build_emsal.py` | emsal oranları → `player_emsal` | **0** |
| `defter.py --kaydet` | API iddia defteri (append-only) | **0** |
| `build_tm_tarih.py` · `tm_model.py` · `tm_defter.py` | Transfermarkt hattı, 2025/26 ileriye dönük defter | **0** |
| `audit.py` | **sistem denetimi** — 41 kontrol, bozuk olanı bulur | **0** |
| `sanity_u21.py` | veri tutarlılık denetimi | **0** |
| `explore_transfermarkt.py` | Transfermarkt veri setini haritalar | **0** |
| `explore_tm_depth.py` | Transfermarkt kapsam derinliği | **0** |
| `probe_fbref_comps.py` | *(arşiv)* FBref lig envanteri — FBref elendi, bkz. §11.2 | — |

## Veri düzeni

```
data/
├── raw/
│   ├── apifootball/        # ham JSON yanıtlar - kalıcı önbellek, asla silme
│   │   ├── players/        # (oyuncu sayfaları)
│   │   ├── _quota.json     # günlük istek sayacı
│   │   └── _ingest_state.json
│   └── transfermarkt/2026-07-11/   # CC0 veri seti (195 MB)
└── scout.duckdb            # analitik tablo - build_db.py üretir
```

`data/raw` **kutsaldır** — silme. Önbellekteki her sayfa harcanmış kotadır.
`scout.duckdb` her an yeniden üretilebilir.

## Kısıtlar (ücretsiz plan)

- Sezonlar: **yalnızca 2022–2024**. Güncel sezon kapalı.
- **100 istek/gün** + dakikalık hız limiti (istemci 7 sn aralıkla çalışıyor)
- `page` parametresi en fazla 3
- xG yok — `shots` + `rating` ile telafi ediliyor

Detay ve gerekçeler: [PLAN.md](PLAN.md) §11.
