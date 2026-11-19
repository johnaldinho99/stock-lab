# 📈 Aktielabbet

Backtesta investeringsstrategier på ~900 amerikanska aktier och jämför dem med
**S&P 500, globalindex (MSCI ACWI) och OMXS30**. För varje strategi kan du se hur
den fungerar, hur du hade investerat över tid, konfidensintervall för framtida
avkastning och dagens köplista. Kurserna är live via Alpaca.

> Inte investeringsrådgivning. Backtester är alltid optimistiska. Se "Metod, data
> och begränsningar" i appen.

## Strategier

| Familj | Strategi | Idé |
|---|---|---|
| Klassiska | 60/40-portföljen | 60 % aktier, 40 % statsobligationer |
| | Trendföljning (Faber) | Aktier över 10-mån. medelvärde, annars kontanter |
| | Dual Momentum (Antonacci) | Starkaste av USA/internationellt, annars obligationer |
| | Momentum 12–1 | Senaste årets vinnare (exkl. sista månaden) |
| | Låg volatilitet | De lugnaste aktierna |
| Magic Formula | Klassisk | Greenblatt: EBIT/EV + avkastning på kapital, 30 aktier, årsvis |
| | Rullande trancher | Köp en fjärdedel varje kvartal, behåll ett år |
| | + momentum | Magic Formula-kandidater som redan börjat stiga |
| | Kvalitetsfilter | Utan högt belånade bolag och förlustbolag |
| | Acquirer's Multiple | Bara EBIT/EV (Carlisle) |
| Maskininlärning | Gradient boosting | Trädmodell på 15 variabler, walk-forward |
| | Ridge | Linjär, genomskinlig modell på samma variabler |
| Referens | Lika vikt – universum | Rättvis jämförelse (samma bias som aktiestrategierna) |

Varje strategi har fem flikar: **Översikt** (tillväxt, drawdown, årsavkastning,
nyckeltal), **Så fungerar den** (utförlig förklaring, formler, forskning och risker,
för ML även variabelbetydelse och träffsäkerhet), **Så hade du investerat**
(sparsimulator, varje ombalansering med köp och sälj), **Framtid & osäkerhet**
(block-bootstrap: solfjäder, intervall per horisont, var avkastningen tur?) och
**Köp idag** (dagens innehav, antal aktier för ditt belopp, live-kurser).

## Kom igång

Kräver Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # fyll i Alpaca-nycklar (valfritt)
python -m scripts.build_data    # hämtar all data, ca 5–10 min första gången
uvicorn backend.app.main:app --reload
```

Öppna <http://localhost:8000>. Första sidladdningen räknar alla backtester (cirka 30–60 s).
Därefter går det snabbt.

**Uppdatera kurserna** (t.ex. dagligen): `python -m scripts.build_data --prices`
(tränar också om ML-modellerna). Nyckeltal: `--fundamentals`. Starta sedan om servern.

## Alpaca (live-kurser)

1. Skapa ett gratis konto på <https://alpaca.markets> och välj **Paper Trading**.
2. I paper-dashboarden: **API Keys → Generate New Keys**.
3. Lägg in dem i `.env`:
   ```
   ALPACA_API_KEY_ID=PK...
   ALPACA_API_SECRET_KEY=...
   ```
4. Starta om servern. Chippet uppe till höger visar "Alpaca paper · börsen öppen/stängd",
   och fliken **Köp idag** uppdaterar kurser var 15:e sekund (IEX-flödet).

Nycklarna används bara i backend och skickas aldrig till webbläsaren. `.env` är gitignorerad.

## Data

| Källa | Vad | Not |
|---|---|---|
| Wikipedia | S&P 500 + S&P 400, sektorer, inträdesdatum | Aktier blir valbara först vid indexinträdet |
| SEC | Ticker → CIK | |
| Yahoo Finance (yfinance) | Dagliga kurser från 2000, index, ETF:er, USD/SEK, T-bill-ränta | Inofficiellt API |
| SEC EDGAR XBRL | Nyckeltal med inlämningsdatum (point-in-time) | Från 2009–2011 |
| Alpaca | Live-kurser, paper-konto | Valfritt |

**Kända begränsningar:** överlevnadsbias (bolag som försvunnit saknas), OMXS30 är
ett prisindex utan utdelningar, inga skatter, och yfinance-data kan ha fel.

## Arkitektur

```
scripts/build_data.py ──▶ data/*.parquet (kurser, nyckeltal, universum)
                                │
Webbläsare ◀── frontend/ ◀── FastAPI (backend/app) ──▶ Alpaca (live)
```

| Fil | Ansvar |
|---|---|
| `backend/app/data/store.py` | Laddar data, bygger månadspaneler (kurser, momentum, volatilitet, nyckeltal, indexmedlemskap) |
| `backend/app/data/fundamentals.py` | SEC-hämtning och point-in-time-logik |
| `backend/app/engine/backtest.py` | Månadssimulator med drift, kostnader och kontanter |
| `backend/app/engine/metrics.py` | CAGR, Sharpe, drawdown, beta/alfa … |
| `backend/app/engine/uncertainty.py` | Block-bootstrap: solfjäder, horisonttabell, konfidensintervall |
| `backend/app/strategies/` | Strategierna (`classic.py`, `magic.py`, `ml.py`) |
| `backend/app/docs.py` | Förklaringstexterna i "Så fungerar den" |
| `backend/app/service.py` | Sätter ihop API-svaren, cache |
| `frontend/js/` | `app.js` (state, routing, live), `views.js` (flikarna), `charts.js` (ECharts) |

### Lägga till en strategi

Ärv `RankStrategy` (aktier: returnera en poäng per aktie och månad) eller
`AllocationStrategy` (vikter mellan ETF:er), lägg in den i `build()` i en av
strategimodulerna och skriv en förklaring i `docs.py`. Frontend plockar upp den
automatiskt.

### API

| Endpoint | Beskrivning |
|---|---|
| `GET /api/strategies` | Alla strategier med parametrar och nyckeltal |
| `GET /api/strategies/{id}?n=30&rebalance=12&start=2011-06-30` | Allt för en strategi |
| `GET /api/compare` | Alla strategier över samma period |
| `GET /api/live?symbols=AAPL,MSFT` | Live-kurser från Alpaca |
| `GET /api/status` | Datastatus och Alpaca-konto |
| `GET /docs` | Swagger |

## Tester

```powershell
pytest
```

Testerna körs på syntetisk data, så de kräver varken internet eller nedladdad data.
