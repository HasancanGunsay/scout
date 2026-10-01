# Scout — Yol Haritası ve Uygulama Rehberi

**Son güncelleme:** 29 Ağustos 2026

> **Bu dosya ne için?**
> Projenin *operasyonel hafızası*. Sistem şu an nerede, hangi kararlar
> verildi, neler denendi ve **neden reddedildi**, sırada ne var.
>
> Yeni bir oturuma başlarken **önce burayı oku**. Özellikle §4 ve §5 —
> orada yazılı olan işi tekrar yapmak zaman kaybıdır ve daha önce
> ölçülmüş sonuçları görmezden gelmek demektir.
>
> Diğer dosyalar: [PLAN.md](PLAN.md) tasarım gerekçeleri ve ölçüm bulguları ·
> [GELISTIRME.md](GELISTIRME.md) denetim sonuçları · [README.md](README.md) kullanım

---

## 1. Sistem şu an nerede

Boru hattı uçtan uca çalışıyor: **API → ham JSON → DuckDB → özellikler → skorlar → arayüz**

### Veri (29 Ağustos 2026)
| Tablo | Satır |
|---|---|
| `player_season` | 32.588 |
| `player_features` | 32.588 × 267 sütun |
| `player_scores` | 108.669 (oyuncu × rol) |
| `player_natural_role` | 31.678 |
| `player_links` | 18.965 (TM eşleşmesi) |
| `player_meta` | 12.689 |

### Toplama durumu
**64/75 lig-sezon tam.** 2024: 24 lig · 2022: 24 lig · **2023: 14 lig**.
Kalan ~495 istek ≈ **~5 gün**.

### Kalite kapıları
- `python -m pytest` → **72 test**
- `python scripts/audit.py` → **32 kontrol** (27 geçiyor; 5 bilinen, §6)
- Günlük iş her sabah denetimi de çalıştırıp log'a yazıyor

### Sistemin doğruluğu ÖLÇÜLDÜ — ve 29 Ağustos'ta DENETLENDİ (§31)

Veri bilimi denetimi bootstrap güven aralıklarıyla yapıldı. Sonuç:

**✅ Ayakta kalan tek güçlü iddia — sistem rastgeleden anlamlı biçimde iyi:**

| Kohort · sonuç | SİSTEM − rastgele | %95 GA |
|---|---|---|
| U23 · değer | +9,0 puan | [+2,2 , +16,9] |
| U23 · terfi | +8,6 | [+2,7 , +14,7] |
| Tüm yaşlar · değer | +7,5 | [+2,5 , +12,3] |
| Tüm yaşlar · terfi | +9,1 | [+4,3 , +13,7] |

**❌ Tabanlarla yapılan tüm kıyaslar gürültü içindeymiş.** "Gol sistemi
geçiyor" (−5,0 puan, GA [−13,4 , +4,1]), "dakika U21'de en iyi",
"kalibrasyon +0,07 kazandırıyor" — hiçbiri desteklenmiyor.

**❌ Yaş eğrisi düzeltmesi gürültüye dayanarak ürüne alınmıştı** (§31.4).
Özellik kaldırılmadı ama üstünlük iddiası arayüzden silindi.

**⚠️ Lig gücü kapısı sağlam kanıt değil:** rho 0,654 ama GA [0,188 , 0,890],
üstelik varyant seçimi de aynı ölçüyle yapıldı (§31.5).

**Sistemik düzeltme:** `backtest.py` artık **eşleştirilmiş bootstrap %95 GA**
ve **lig içi AUC** basıyor. Güven aralığı olmayan bir kıyastan ürün kararı çıkmaz.

**✅ Yeni araç gizli bir başarı buldu (§31.8):** sistem, değer büyümesini
öngörmekte **piyasa değerini anlamlı biçimde geçiyor** (+0,120 AUC,
GA [0,078 , 0,161]). Terfiyi öngörmekte ise piyasa üstün (−0,110). İkisi
birlikte wonderkid avının tanımı: *piyasa fark etmemişken değer kazanacak
oyuncuyu bulmak.*

---

## 2. Mimari harita

```
config/
  leagues.yaml        Hedef ligler, öncelik sıralı, sezon sırası
  roles.yaml          14 rol şablonu + ağırlıklar (+ cluster kısıtı)
src/scout/
  ingest/apifootball.py   Kota korumalı, önbellekli, hız sınırlı API istemcisi
  features/metrics.py     per-90 + oran metrikleri, mevki eşlemesi
  features/shrinkage.py   Empirical Bayes (Gamma-Poisson, Beta-Binom)
  features/percentile.py  Kohort içi 0-100 dönüşümü
  features/age.py         Yaş bandı + KESITSEL yaş eğrisi (devre dışı, §19)
  features/age_long.py    BOYLAMSAL yaş eğrisi - fark yöntemi (kullanımda, §26)
  features/development.py Sezonlar arası gelişim (§24)
  features/similarity.py  Stil benzerliği, CLR (§25)
  features/position.py    Eksik mevki çıkarımı
  roles/cluster.py        Doğrulanmış rol ayrımı (çift tepelilik testi)
  resolve/matcher.py      Kimlik eşleştirme (TM ↔ API)
  scoring/engine.py       Ağırlıklı skor + katkı ayrıştırması
scripts/
  ingest_players.py   Veri toplayıcı (kaldığı yerden devam eder)
  build_db.py         Ham JSON → player_season
  build_features.py   → player_features (rol ayrımı burada)
  build_links.py      → player_links, player_meta
  build_scores.py     → player_scores, player_natural_role
  audit.py            28 doğrulama kontrolü
  eta.py              Toplama tahmini
  daily_run.ps1       Günlük zincir (Görev Zamanlayıcı bunu çağırır)
app/
  Home.py             st.navigation girişi
  _style.py           Tasarım token'ları + CSS + bileşenler
  _shared.py          Veri yükleme, uyarılar, havuz, takip
  views/*.py          7 sayfa
```

**Boru hattı sırası kritik:**
`ingest → build_db → build_features → build_links → build_scores → audit`

`build_features` içinde: metrikler → **rol ayrımı** → shrinkage → percentile → yaş.
Rol ayrımı per-90'lardan sonra, percentile'dan önce olmak zorunda (kohortu o belirliyor).

---

## 3. Günlük operasyon

Otomatik. Görev Zamanlayıcı: **`Scout - Gunluk Veri Cekimi`**
- Tetikleyiciler: oturum açıldığında (+3 dk) **ve** günlük 08:00
- Pilde çalışır, kaçan çalışmayı telafi eder, hata olursa 2 kez dener
- Log: `data/raw/daily_log.txt`

Elle çalıştırma:
```bash
.venv/Scripts/python.exe scripts/ingest_players.py --plan   # istek harcamadan durum
.venv/Scripts/python.exe -m streamlit run app/Home.py       # arayüz
.venv/Scripts/python.exe scripts/eta.py                     # tahmin
```

**`data/raw` kutsaldır** — silme. Her önbellek dosyası harcanmış kotadır.
`scout.duckdb` her an yeniden üretilebilir.

---

## 4. Verilmiş kararlar — yeniden tartışılmayacak

| Karar | Gerekçe |
|---|---|
| Veri kaynağı: **API-Football + Transfermarkt CC0** | İzinli, anahtarlı, ToS açık |
| Arayüz: **Streamlit** | Veri bilimi koduyla aynı dil, hızlı |
| Kapsam: **düşük görünürlüklü ligler** | Big-5 yetenekleri zaten piyasaya yayılıyor |
| İtalya Serie C/D: **kapsam dışı** | `stats_players=False` — oyuncu istatistiği fiilen yok (ölçüldü) |
| Ağırlıklar **futbolca** verilir, güvenilirliğe göre değil | Gürültüyü shrinkage hallediyor; ayrım bilinçli |
| Lig gücü **ölçülür ama skora uygulanmaz** | Uygulamak geriye dönük testte sonucu kötüleştirdi — değer *büyümesi* arıyoruz, *seviyesi* değil (PLAN §23). Zorluk arayüzde bağlam olarak gösteriliyor |
| Yaş eğrisi: **kesitsel devre dışı, BOYLAMSAL kullanımda** | Kesitsel fit hayatta kalma yanlılığı taşıyor (§19). Boylamsal fit (aynı oyuncunun sezonlar arası farkı) tepe 25 yaşta çıkıyor ve U23'te sistemi birinci yapıyor; yalnızca **≤23 yaş** filtresinde sunuluyor (§26) |
| Yarım toplanmış ligler arayüzde **gizli** | Kümeli örnekten hesaplanan percentile sapmalı |
| Şüpheli TM eşleşmesi **reddedilir** | Yanlış piyasa değeri, eksik olandan beterdir |
| Skor renkleri **mavi sıralı skala** | Kırmızı-yeşil renk körlüğünde okunmaz |

---

## 5. ⛔ Denendi ve REDDEDİLDİ — tekrar denemeyin

Bunların hepsi uygulandı, ölçüldü, başarısız oldu. Kanıtlarıyla birlikte.

### FBref (birincil kaynak olarak)
- Dönen sayfalar **kırpılmış**: Ligue 1'de bile `data-stat="xg"` sayısı sıfır
- Erişim ancak `undetected-chromedriver` + otomatik CAPTCHA/Cloudflare
  çözümüyle mümkün (`soccerdata/_common.py:587,608,613`)
- → Elendi. Lig envanteri hâlâ referans: `data/raw/fbref_comps.csv`

### Serbest GMM rol kümeleme
- Paylar → CLR → PCA → GMM/BIC hattı kuruldu
- silhouette **0,13–0,28**; iki kümeye aynı isim düştü; profiller özdeş
  ("Kanat" şut payı 0,050 vs "Santrfor" 0,053)
- Çift tepelilik testi sebebi gösterdi: **orta saha ve forvette ayrık rol
  yapısı YOK** (tek tepeli dağılım). Mekânsal veri olmadan ayrılamıyor.
- → Yerine **doğrulanmış ayrım**: yalnızca kanıtlanan ayrım uygulanıyor.
  Şu an tek geçerli ayrım: **Defender → Stoper / Bek** (bimodalite 0,588)

### Moment yöntemiyle shrinkage
- `var_toplam − var_örnekleme` kohortta düşük dakikalı oyuncu çokken
  **negatif τ²** üretti (−0,002), sıfıra kırpıldı, **herkes ortalamaya çöktü**
- Guilherme (2390 dk, 17 g+a) ile Porfírio (37 dk, 1 gol) aynı skoru aldı
- → Yerine **maksimum olabilirlik** (Gamma-Poisson / Beta-Binom marjinal)

### Eşiksiz "tek aday" eşleştirmesi
- "Doğum tarihi + uyruk bloğunda tek aday varsa kabul et" kuralı %66,8
  eşleşme veriyordu ama **yanlış**: `Gabriel Silva` → `Matheus Teixeira` (skor 45),
  `Pablo Dyego` → `Guilherme Garutti` (36) — aynı gün doğmuş farklı Brezilyalılar
- → İsim skoru **≥85** eşiği zorunlu. Kabul %54,9'a düştü ama doğru.

### "Exaggerated Minimalism" tasarım stili
- Tasarım skill'i önerdi (dev tipografi, `clamp(3rem,10vw,12rem)`)
- Veri yoğun bir araca uymuyor → yalnızca renk paleti ve Fira Sans/Fira Code
  tipografisi alındı

---

## 6. Sert kısıtlar — değişmeyecek

| Kısıt | Detay |
|---|---|
| **API sezonları 2022–2024** | Ücretsiz plan güncel sezonu vermiyor (30 Ağu 2026'da yeniden sınandı, hâlâ kapalı). AMA **sonuç ölçümü için artık gerekli değil**: Transfermarkt CC0 `appearances` tablosu 2026-05'e kadar dakika/gol veriyor (Bölüm 7). Zengin metrikler (pas, ikili mücadele, top çalma) yine 2022–2024 ile sınırlı |
| **100 istek/gün** | + dakikalık hız limiti (istemci 7 sn aralıkla çalışıyor) |
| **`page` ≤ 3** | Bu yüzden `/players?league=X&team=T&season=Y` rotası kullanılıyor |
| **Brezilya kadro kaybı %5-10** | 4 sayfalık kadroların son sayfası alınamıyor; kayıp rastgele |
| **xG yok** | Şut hacmi + isabet + rating ile telafi |
| **Possession verisi yok** | Vekil olarak takım pas hacmi kullanılıyor (§32.2). Savunma metrikleri `_padj` sürümleriyle takım bağlamından arındırıldı — 6/6 anlamlı iyileşme. Gerçek possession verisi ek API gerektiriyor |
| **Mekânsal veri yok** | Pas yönü/uzunluğu, dokunuş bölgesi → rol ayrımı sığ kalıyor |
| **TM kapsamı 14 birinci lig** | Serie B'de eşleşme tavanı %56. Sonuç değişkeni için **kritik**: TM kaydının olmaması "başarısız oldu" demek DEĞİL, "izlenen bir lige çıkmadı" demek. Bölüm 7'de açıkça böyle tanımlandı |
| **Fizik/karakter verisi yok** | Göz testine ve scout raporuna devredildi |
| **"Doğal rol" genelciyi seçemez** | Doğal rol = 14 skorun argmax'ı; genelci şablon (`fw_complete`) ötekilerin ortalaması olduğu için (r=0,91) argmax'a %3,7 çıkıyor. Komple bir forvet "Bitirici" etiketi alır. Yapısal, düzeltilebilir değil — rol skorunun kendisi sabit rol aramasında hâlâ geçerli (§36.3) |

**Bilinen 2 denetim uyarısı (kabul edilmiş):**
1. 1 oyuncuda doğum tarihi eksik (30 dk) → yaş filtrelerinde düşüyor
2. 6 oyuncuda API mevki alanı boş (1.823 dk) → kohortsuz, skorsuz → **Adım 1**

---

## 7. Yol haritası — SCOUT EKİBİ GİBİ (30 Ağu 2026'da yeniden yazıldı)

### Amaç değişti

Eski hedef: "iyi oyuncuları sırala."
**Yeni hedef: sistem bir İDDİA üretsin, sen onu gidip doğrula.**

Fark şu: bir tablo "bu oyuncu 87 puan" der ve seni yalnız bırakır. Bir scout
ekibi şunu der: *"19 yaşında, Eerste Divisie'de yaşıtlarının %94'ünden iyi,
iki sezondur yükseliyor, bu profildeki 61 oyuncudan 14'ü üst lige çıktı —
git bak, özellikle baskı altında ilk dokunuşuna."* İkincisi bir araştırma
başlangıcıdır; birincisi veri dökümüdür.

Bu bölüm o dönüşümün planı. Ücretli veri **yok** — hepsi elimizdeki veriyle.

---

### 🔓 BULGU: 2025/26 verisi zaten elimizde (30 Ağu 2026)

Aylardır "ücretsiz plan 2022-2024 veriyor, güncel sezonu göremiyoruz" diye
plan yapıyorduk. Transfermarkt CC0 veri setini yeniden inceledim —
**hiç kullanmadığımız dört tablo** var:

| Tablo | Satır | Ne var |
|---|---|---|
| `appearances` | **1.894.350** | **Maç bazında** dakika, gol, asist, kart — **2026-05-24'e kadar** |
| `game_lineups` | 3.179.016 | İlk 11 / yedek |
| `game_events` | 1.274.469 | Gol, kart, oyuncu değişikliği (dakikasıyla) |
| `games` | 88.958 | Sonuç, tur, tarih, dizilişler, hakem |

API'nin bize vermediği **2025 ve 2026 sezonları burada**. Ücretsiz, diskte,
yedi haftalık.

**Neden bu her şeyi değiştiriyor:** şimdiye kadar bütün doğrulama geriye
dönük testti — 2022'den 2023/24'ü tahmin et. Artık **gerçek bir ileriye
dönük pencere** var:

| Skorladığımız sezon | U23 oyuncu | 2025/26 sonucu ölçülebilir | ≥900 dk oynamış |
|---|---|---|---|
| 2022 | 1.855 | **1.013 (%54,6)** | 694 |
| 2023 | 1.258 | 555 (%44,1) | 317 |
| 2024 | 2.046 | **1.090 (%53,3)** | 688 |

Ve düşük görünürlüklü liglerden gerçek terfi oranları:

| Lig | 2024'te skorlanan | 2025/26'da TM ligine çıkıp 450+ dk | Oran |
|---|---|---|---|
| Ligue 2 | 357 | 97 | **%27,2** |
| Challenger Pro League | 290 | 68 | %23,4 |
| Eerste Divisie | 416 | 92 | %22,1 |
| Serie B (BRA) | 849 | 104 | %12,2 |
| Superettan | 290 | 34 | %11,7 |
| Primera A (COL) | 381 | 16 | %4,2 |

Bunlar taban oranlar. Bir scout ekibinin ilk sorduğu sayı budur:
*"bu ligden kaç kişi yukarı çıkıyor ki?"*

**⚠️ Dürüstlük şartı — bu sonuç değişkeninin sınırı:**
TM 14 birinci ligi ve Avrupa kupalarını izliyor. Kaydın **olmaması**
"başarısız oldu" demek DEĞİL — Kolombiya'da gayet iyi oynuyor ama izlenmiyor
olabilir. Yani bu değişken **"iyi oldu mu"yu değil, "izlenen bir seviyeye
sıçradı mı"yı** ölçüyor. Wonderkid avı için doğru hedef bu, ama cümleyi
böyle kurmak zorundayız.

---

### FAZ 1 — Gerçek sonuç tablosu · ✅ **TAMAMLANDI** (30 Ağu 2026, PLAN §38)

Diğer her şey buna dayanıyor.

1. `appearances`, `games`, `game_lineups` tablolarını ana veritabanına al
2. **Doğrula:** terfi edenlerin gittiği ligler gerçekten daha güçlü mü?
   (Serie B → Brezilya Serie A mı, yoksa Avrupa mı? Sayıyla göster)
3. `player_outcome` tablosu: skorladığımız her oyuncu-sezon için 12-24 ay
   sonrasında ne olduğu

**Sonuç değişkeni — kademeli, scout mantığıyla:**

| Kademe | Tanım |
|---|---|
| 0 | TM'de iz yok |
| 1 | Göründü, <450 dk |
| 2 | 450-900 dk |
| 3 | **≥900 dk — yer edindi** |
| 4 | ≥900 dk, ilk-5 ligde |

- **Kabul kriteri:** taban oranlar lig bazında raporlanıyor; kademe dağılımı
  ligin gücüyle tutarlı (güçlü ligden gelen daha yüksek kademeye çıkıyor)

---

### FAZ 2 — Modeli EĞİT ve sınırını bul · ✅ **TAMAMLANDI** (30 Ağu 2026, PLAN §39)

Şu an skorlama uzman ağırlıkları (`roles.yaml`) + percentile. Denetlenmiş
(supervised) bir katman hiç eğitilmedi (§5.3 Katman 3, "çoklu sezon
bekliyor" diye ertelenmişti — artık beklemiyor).

**Bölme — sızıntı imkânsız olacak şekilde:**
- **Eğitim:** 2022 ve 2023 pencereleri
- **Test:** 2024 → 2025/26. **Geliştirme boyunca hiç açılmayacak.**
- Eğitim içinde ayrıca lig-dışarıda-bırak (leave-one-league-out) CV

**Yenmesi gereken üç taban — üçünü birden yenmezse REDDEDİLİR:**

| Taban | Neden |
|---|---|
| A. Mevcut uzman ağırlıklı skor | Yeni model eskisinden iyi olmalı |
| B. Piyasa değeri | Piyasayı yenmek projenin tek gerçek iddiası |
| C. **Sadece dakika + yaş** | En aptal makul model. Ölçüldü: "dakika" ve "gol" güçlü sinyaller — bunları yenemeyen model bir şey öğrenmemiştir |

Taban C özellikle önemli. Daha önce bir kez "yükseliş sinyali" güçlü sanıldı,
ölçünce mevcut seviyenin gerisinde kaldı (§27). Aynı hataya düşmeyeceğiz.

**Yöntem:** düzenlileştirilmiş (regularized) sıralama modeli. Karmaşık model
kullanmayacağız — n küçük (U23'te ~1.000 ölçülebilir sonuç), ağaç ensemble'ı
bu boyutta ezberler. Katsayılar okunabilir olmalı, çünkü **scout dosyası o
katsayılara dayanacak.**

- **Kabul kriteri:** tutulan test penceresinde üç tabanı da geçmeli,
  eşli bootstrap %95 GA sıfırı dışlamalı
- **Reddedilirse:** uzman ağırlıklarıyla devam eder ve bunu yazarız.
  Model eğitmiş olmak için model kullanmayacağız

---

### FAZ 3 — Emsal oranı · ✅ **TAMAMLANDI** (30 Ağu 2026, PLAN §40)

Profesyonel scout'un en güçlü aracı ve bizde henüz yok.

Bir oyuncu için: aynı yaş bandı + benzer stil (CLR) + benzer skor seviyesi +
benzer lig gücündeki **geçmiş** oyuncuları bul, onların 2025/26 sonuçlarına
bak.

> *"Bu profildeki 61 oyuncudan 14'ü (%23) üst ligde yer edindi.
> Ligin taban oranı %12. Yani bu profil tabanın iki katı."*

Bu bir tahmin değil, **taban oranı**. Scout'un kafasındaki asıl soruyu
yanıtlıyor: "iyi de, ne kadar iyi?"

- **Kabul kriteri:** emsal grubu ≥30 kişi olmalı, altındaysa oran GÖSTERİLMEZ
  (küçük kohortta percentile üretmeme kuralının aynısı)

---

### FAZ 4 — Scout dosyası · ✅ **TAMAMLANDI** (30 Ağu 2026, PLAN §41)

Sayfa değil, **dosya**. Her aday için tek ekranda:

| Bölüm | İçerik |
|---|---|
| **İDDİA** | Tek cümle, yanlışlanabilir. "19 yaşında, yaşıtlarının %94'ü üstünde, yükselen" |
| **KANIT** | Hangi metrikler skoru taşıyor (waterfall), her birinin güvenilirliği |
| **BAĞLAM** | Lig zorluğu, takım bağlamı (possession-adjusted), yaşına göre dakika payı |
| **YÖRÜNGE** | Sezon sezon + **2025/26'da gerçekte ne olduğu** |
| **EMSAL ORANI** | Faz 3 |
| **RİSKLER** | Küçük örneklem, bozuk lig verisi, tek sezonluk parlama, yaş şişmesi |
| **NE İZLEMELİSİN** | Verinin göremediği: fizik, karakter, baskı altında karar, sakatlık geçmişi |

Son satır kasıtlı. Sistem nerede kör olduğunu söylemezse, kullanıcı nereye
bakması gerektiğini bilemez. **Senin gözlemin sistemin devamı olmalı,
tekrarı değil.**

- **Kabul kriteri:** dosya markdown/PDF olarak dışa aktarılabilir — sahaya
  telefonla gidilir

---

### FAZ 5 — Hesap defteri · ✅ **TAMAMLANDI** (30 Ağu 2026, PLAN §42)

Sistemin verdiği her iddia tarihiyle kaydedilir. Sonuç geldiğinde puanlanır.

- Sistem geçen yıl ne dedi, ne oldu?
- Hangi lig / yaş / rolde yanılıyor?
- **Senin kararların** (takip listesi, rapor) sistemle ne kadar örtüşüyor?

Bir scout ekibini ekip yapan şey budur: iddianın kaydı tutulur. Şu an
hiçbir iddiamız yazılı değil, dolayısıyla hiçbiri yanlışlanamıyor.

---

### Sıra ve gerekçesi

```
FAZ 1 (sonuç tablosu)  <- her seyin temeli; olcemezsen gelistiremezsin
   |
FAZ 2 (model)          <- FAZ 1 olmadan egitilemez
   |
FAZ 3 (emsal orani)    <- FAZ 1 olmadan hesaplanamaz
   |
FAZ 4 (dosya)          <- FAZ 2+3'un ciktisini sunar
   |
FAZ 5 (hesap defteri)  <- FAZ 4'un iddialarini kaydeder
```

**Toplam ~10-12 gün.** Günlük veri toplama arka planda devam eder.

### Bu planın reddettiği şeyler

- **Ücretli veri** — kullanıcı kararı: önce ücretsizle en doğrusunu yap
- **Derin öğrenme / büyük ensemble** — n çok küçük, ezberler
- **Daha çok lig eklemek** — doğrulanmamış sistemi yaymak işe yaramaz;
  kapsam genişletme FAZ 2'nin sonucundan sonra
- **Yeni arayüz sayfaları** — dosya, var olan sayfaların yerine geçmeli,
  yanına değil

### FAZ 6 — Mevki sıralaması ve "sonra ne yaptı" doğrulaması · **TAMAM** (30 Eyl 2026, PLAN §43–§50)

Hedef: her mevkiden **piyasanın değerinin altında fiyatlanan** oyuncuları sırala,
kullanıcı "şimdi ne yapmış" diye kendisi incelesin. Pahalı oyuncular ilgi dışı.

| Alt faz | İş | Süre |
|---|---|---|
| 6.1 ✅ | Modeli tam veriyle yeniden eğit + kayan başlangıç (§44) | tamam |
| 6.2 ✅ | Fiyat-koşullu değerlendirme (§45) + **6.2b** ikinci sonuç (§46) | tamam |
| 6.3 ✅ | Mevki mevki sıralama tablosu (§47) | tamam |
| 6.4 ✅ | "Sonra ne yaptı" + eşleştirilmiş kontrol (§48) | tamam |
| 6.5 ✅ | Arayüz: Mevki sıralaması (§49) | tamam |
| 6.6 ✅ | Kapsam-koşullu kalibrasyon (§50) | tamam |

**6.2 sonucu planın geri kalanını belirler.** Model ucuz bantta ek bilgi vermiyorsa
6.3–6.5 "oyun verisi piyasadan fazlasını söylemiyor" gerçeğine göre yeniden kurulur.
Rating (API) sonraki dönem için yok — "kaç puanla oynadı" olçülemez, yerine TM verisi.

### FAZ 7 — Eldeki verinin maksimumu · **TAMAM** (1 Eki 2026, PLAN §51–§56)

API ücretsiz planı yalnızca 2022–2024'ü veriyor ve 2025'in ne zaman açılacağı
bilinmiyor. 2024 held-out'u beş bakışla tükendi. Ama ham Transfermarkt
dosyasında hiç kullanılmamış **2012–2021** (10 sezon, ~7.600 U23 oyuncu-sezon)
ve **2025/26** var. Sınır: yalnızca TM'nin oyuncu bazında izlediği 14 birinci
lig. Düşük görünürlüklü ligler orada yok.

| Alt faz | İş | Durum |
|---|---|---|
| 7.0 ✅ | Tek doğruluk kaynağı `player_tahmin`; zincire `build_sonra` + `build_ranking` (§51) | tamam |
| 7.1 ✅ | TM tarihsel tablo 2012–2025 + savunma bağlamı (artı-eksi); mevcut sistemle kademe %100 aynı (§52) | tamam |
| 7.2 ✅ | Mühürlü test 2018–2021: model > dakika+yaş (+0,046) ve > piyasa (+0,057) ✅; savunma bağlamı ❌; ucuz top-20 ❌ (§53) | tamam |
| 7.3 ✅ | Kalibrasyon kayması: güncelleme kuralı işe yaramıyor, kayma gürültü; "tüm geçmiş" kalır (§54) | tamam |
| 7.4 ✅ | İzlenen liglerde API vs TM: TM önde (−0,030*), birleştirmek katkı vermiyor; defansta fark en büyük (§55) | tamam |
| 7.5 ✅ | 2025/26 havuzu (891 U23, 14 lig) ileriye dönük deftere yazıldı; puanlama 2027-06-15 sonrası (§56) | tamam |

### FAZ 8 — Arayüz: havuz + takip (kullanıcı isteği, 1 Eki 2026)

Kullanıcı sistemin **tek bir isim** vermesini istemiyor: okyanustan bir
**havuz** çıkarsın, istatistikler **liste üzerinden** incelenebilsin,
oyuncular **takibe** alınabilsin. Güncel sezonun ayrıntıları Sofascore'da
izlenecek; bizim arayüz de "keyif veren" olmalı.

| | İş |
|---|---|
| 8.0 ✅ | Laboratuvar Liderler: metrik aileleri, ilişkili metrikler yan yana; API "pas isabeti" yüzde değil (§57) |
| 8.1 ✅ | Havuz ekranı (giriş sayfası): iki kaynak, grup içi havuz puanı (düşük görünürlük payı korunur), istatistik aileleri, oyuncu kartı (§58) |
| 8.2 ✅ | Takip listesi: kişi = TM kimliği (iki havuz tek kayıt), durum, not günlüğü, göz testi raporu; append-only günlük, yalnız sonucu bilinmeyen seçim göz testi sayılır (§59) |
| 8.3 | Sofascore'a hızlı geçiş (ad + kulüp ile arama), TM profili |
| 8.4 | Görsel düzen: sayfa sayısını azalt, tutarlı kartlar, keyifli tasarım |
| 8.5 | Bakım: ROADMAP §1 ("Sistem şu an nerede", hâlâ 72 test diyor) ve README'yi güncelle; `use_container_width` → `width="stretch"` (41 yer, Streamlit kaldıracak) |

---

## 8. Bilinen tuzaklar

Bunlar bizi bir kez ısırdı. Kod düzeltildi ama davranış bilinmeli.

| Tuzak | Ne olur | Nasıl korunuyor |
|---|---|---|
| **API `null` = 0** | Oynamış oyuncuda "0 gol" yerine `null` gelir | Sayım metriklerinde null→0; `rating`/`pass_accuracy` hariç |
| **Sezon içi transferde çift sayım** | Aynı sezon toplamı iki kulüpte tekrarlanır (Dalberson 1350+1350 dk) | Oyuncu-lig-sezon başına tek satır, en çok dakikalı esas; `multi_team` bayrağı |
| **`statistics[0]` boş stub** | İlk giriş çoğu zaman boş; oradan okumak her şeyi `null` gösterir | İlgili `league.id`'ye ait ve `minutes` dolu giriş seçilir |
| **Tutarsız mevki etiketi** | `Forward` tanınmıyordu → 16 oyuncu skorsuz | `POSITION_ALIASES` + tanınmayan etikette uyarı |
| **Çift kodlanmış karakter** | `JoÃ£o` | `fix_mojibake()` |
| **DuckDB kilidi** | Streamlit açıkken build çöker | Arayüz veritabanının kopyasını okur (`scout_ui_snapshot.duckdb`) |
| **Streamlit widget durumu** | Toggle değişince multiselect eski seçimi korur | Widget `key`'i toggle durumuna bağlı |
| **`schtasks` varsayılanları** | Pilde çalışmayı reddeder (`0x800710E0`) | Görev ayarları düzeltildi |
| **Sayfa sırası anlamsız** | `page` sırası dakikayla ilişkili değil → 4. sayfa kaybı rastgele oyuncu kaybı | Arayüzde kısmi kapsam uyarısı |

---

## 9. Kavram sözlüğü

- **Shrinkage** — Az dakikalı oyuncunun şişkin per-90 değerini kohort
  ortalamasına doğru çekme. 6 maçta 4 gol atan çocuğu listenin tepesine
  koymamak için. Ağırlık = kanıtın gücü (0-1).
- **Kohort** — Percentile'ın hesaplandığı karşılaştırma havuzu:
  `(lig, sezon, role_cohort)`. Yanlış kohort = yanlış skor.
- **`role_cluster` / `role_cohort`** — İlki doğrulanmış rol ayrımı etiketi
  (`Defender::Bek`), ikincisi percentile kohortu; kohort 12 kişiden küçükse
  mevki grubuna düşer.
- **Percentile** — Kohort içinde 0-100 sıralama. Ligler arası
  karşılaştırılamaz (lig gücü katsayısı yok).
- **`score` / `score_age`** — Sırasıyla "şimdiki güç" (mevki havuzu içinde)
  ve "yaşıtlarına göre" (yaş bandı içinde). 19'luk bir çocuk birincide 55,
  ikincide 92 alabilir; ikisi de doğru, farklı soruları cevaplar.
- **Rol şablonu** — `roles.yaml`'daki ağırlık seti. Oyuncu kendi mevki
  grubundaki tüm rollere göre puanlanır; en yükseği "doğal rolü".
- **Doğrulanmış ayrım** — Rol ayrımı ancak çift tepelilik kanıtlanırsa
  uygulanır. Veri büyüdükçe yeni ayrımlar kendiliğinden aktifleşir.
- **Kapsam (`coverage`)** — Bir skorda ağırlığın ne kadarının
  hesaplanabildiği. 1,0 = tüm metrikler mevcut.

---

## 10. Sonraki oturum için hızlı başlangıç

```bash
cd C:\Users\hasan\Desktop\Scout
.venv/Scripts/python.exe scripts/eta.py            # toplama nerede?
.venv/Scripts/python.exe scripts/audit.py          # bir şey bozuldu mu?
.venv/Scripts/python.exe -m pytest                 # matematik sağlam mı?
```

Sonra bu dosyanın **§7 ADIM 0**'ından devam et — karar bekliyor ve zamana duyarlı.
