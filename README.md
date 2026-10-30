# Scout

A leakage-safe system that forecasts which young footballers will establish themselves in a
top-flight league, and checks honestly whether it works.

**Case study:** https://scout-hasancangunsay.vercel.app · *(design log and UI are in Turkish; this
page is the English entry point)*

## The question

> Given everything known about an under-23 player at the end of a season, will he play at least
> 900 league minutes in one of 14 tracked top-flight leagues in the next 12 months?

The model has to beat two baselines people already use: **minutes + age** (the scout's rule of
thumb) and **market value** (the market's aggregated opinion). Evaluation is within league
(AUC per league-season, weighted by positives) with a paired, player-clustered bootstrap.

## Headline results

Sealed test 2018–2021, opened once, hypotheses committed before opening (n = 3,097):

| | AUC | Δ vs model, 95% CI |
|---|---|---|
| **Model** (play data + value) | **0.742** | |
| Minutes + age | 0.696 | model +0.046 [+0.027, +0.064] |
| Market value | 0.686 | model +0.057 [+0.042, +0.072] |

Two of the five pre-registered hypotheses **failed** (defensive context adds nothing; the model's
top-20 lists do not reliably beat a minutes list in the cheap band). Both are reported.

Other findings recorded in the design log:
- Six calibration-update rules tested in a forward chain; none beat "all history". Season-to-season
  drift is noise, not trend.
- A linking bug meant 26% of outcomes were measured on the wrong player's career. Fixed at the
  source; cross-validated AUC fell 0.744 → 0.732 and the low-visibility-league edge in 2024
  disappeared. The lower numbers are the published ones.
- In tracked leagues, adding API event features to the Transfermarkt model adds nothing
  (−0.009 [−0.019, +0.001]).
- 891 forecasts for 2025/26 are frozen in an append-only ledger and will be scored after
  15 June 2027.

## Data

- **API-Football** (free tier): 37,890 player-seasons × 304 features, 24 leagues, 2022–2024.
- **Transfermarkt open dataset**: 92,958 player-seasons, 14 European top flights, 2012–2026.

Raw data is not in this repository (licensing and size). The ingestion scripts rebuild it with
your own API key (`.env.example`).

## Layout

```
src/scout/      ingest · features · entity resolution · scoring · model · calibration · ledger
scripts/        daily chain (ingest → build_* → ledger → audit), model training, sealed test
app/            Streamlit UI (11 pages, Turkish)
tests/          381 tests
portfolio/      the case-study site (static HTML) and the scripts that build its figures
PLAN.md         design log: every decision, measurement and rejected idea (Turkish, 66 sections)
ROADMAP.md      current state and next steps (Turkish)
README.tr.md    Turkish usage guide
```

## Run

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install httpx tenacity duckdb pandas scikit-learn statsmodels streamlit plotly rapidfuzz pydantic pyyaml
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m streamlit run app/Home.py
```

---
Hasancan Günsay · [LinkedIn](https://www.linkedin.com/in/hasancangunsay) · hasancangunsay16@gmail.com
