# Transfermarkt anlik goruntu karsilastirmasi: 2026-07-11 -> 2026-09-05

Uretilen: `scripts/kaynak_karsilastir.py` · zincir hala `2026-07-11` kullaniyor (config/kaynaklar.yaml).

## Tablolar

| tablo | satir 2026-07-11 | en_yeni 2026-07-11 | satir 2026-09-05 | en_yeni 2026-09-05 | fark |
|---|---|---|---|---|---|
| players | 50,149 | — | 50,149 | — | 0 |
| player_valuations | 507,815 | 2026-02-27 | 656,301 | 2026-06-12 | 148,486 |
| appearances | 1,894,350 | 2026-06-28 | 1,894,350 | 2026-06-28 | 0 |
| games | 88,958 | 2026-07-06 | 88,958 | 2026-07-06 | 0 |
| game_lineups | 3,179,016 | 2026-07-06 | 3,179,016 | 2026-07-06 | 0 |
| game_events | 1,274,469 | 2026-07-06 | 1,274,469 | 2026-07-06 | 0 |
| transfers | 35,139 | 2030-06-30 | 175,165 | 2030-06-30 | 140,026 |
| clubs | 796 | — | 796 | — | 0 |
| competitions | 65 | — | 65 | — | 0 |

## Bizim oyuncularimiz

- Kapsam: 13,379 TM oyuncusu (2025/26 havuzu + kabul edilmis eslesmeler).
- Son degeri DAHA YENI tarihli olan: **5,082**.
- Bunlardan degeri degisen: 5,082; yeni/eski oran medyani 0.94 (ceyrekler 0.70-1.25).
- Sozlesme bitis tarihi degisen: 1 / 13,379.

## Ileriye donuk defter (2025/26, 891 tahmin) icin anlami

- Sezon sonu (2026-06-15) itibariyla piyasa degeri farkli olacak oyuncu: **761 / 882**.
- Defter append-only: kayitli tahminler DEGISMEZ. Ama yeni surume gecilirse havuz ve arayuzdeki olasiliklar defterdekinden ayrisir; defter puanlamasi kayitli tahminlerle yapilir (docs/defter_2025_puanlama.md).

## Gecis karari

Zincir otomatik gecmez. Gecis = `config/kaynaklar.yaml` -> `anlik_goruntu` degisikligi + zincirin tam calismasi + denetim + PLAN.md kaydi, kullanici onayiyla.
