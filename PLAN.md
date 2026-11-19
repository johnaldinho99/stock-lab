# PLAN – Aktielabbet

## Mål
Lokal webbapp som backtestar investeringsstrategier, förklarar dem utförligt, visar hur
man hade investerat över tid, ger konfidensintervall för framtida avkastning och en
köplista för idag, jämfört med S&P 500, globalindex och OMXS30.

## Beslut
| Område | Val |
|---|---|
| Aktieuniversum | S&P 500 + S&P MidCap 400 (~900 bolag), valbara från indexinträde |
| Kurser | yfinance (från 2000), lokalt i parquet |
| Nyckeltal | SEC EDGAR XBRL companyfacts, point-in-time via inlämningsdatum |
| Live | Alpaca (paper-konto, IEX-flöde) via backend |
| Valuta | USD (OMXS30 växlas från SEK) |
| Frekvens | Månadsvis signal och ombalansering, dagsdata för volatilitet |
| Osäkerhet | Block-bootstrap (12 mån), parad mot S&P 500 |
| ML | HistGradientBoosting + Ridge, rangade features, walk-forward årlig omträning |
| Frontend | HTML/CSS/JS + ECharts, samma designsystem som scb-dashboard |

## Steg
1. Datakällor: utforska och verifiera ✅
2. Datanedladdning: universum, kurser, SEC-nyckeltal ✅
3. Motor: backtest, nyckeltal, bootstrap ✅
4. Strategier: klassiska, Magic Formula (5 varianter), ML (2) ✅
5. Bias-kontroll: point-in-time-medlemskap, PP&E-begrepp ✅
6. Frontend: 5 flikar + jämförelsevy, live-kurser ✅
7. Tester, README ✅

## Möjliga nästa steg
- **Papperstrading:** knapp "Lägg order på paper-kontot" för dagens köplista (Alpaca orders-API), med bekräftelsesteg.
- **Automatisk ombalansering:** schemalagt jobb som kör strategin varje månad mot paper-kontot och loggar resultatet.
- **Historiska indexmedlemmar inkl. avregistrerade bolag** (t.ex. via betald data som Norgate/Sharadar) för att ta bort överlevnadsbias helt.
- **Svenska aktier** via Börsdata-API (Magic Formula på Stockholmsbörsen).
- **SEK-läge** för att se avkastning som svensk investerare.
- **Egna strategier** i UI:t: kombinera faktorer med reglage.
