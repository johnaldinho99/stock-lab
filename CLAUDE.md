# CLAUDE.md

Instruktioner för Claude Code i det här repot.

- Backend: Python + FastAPI i `backend/app`. Frontend: ren HTML/CSS/JS (ES-moduler) i `frontend/`, inget byggsteg, ECharts från CDN.
- UI-texter på svenska, kod och kommentarer på engelska.
- Data hämtas med `python -m scripts.build_data` till `data/` (gitignorerad). Servern läser bara lokala filer, utom Alpaca live.
- **Ingen look-ahead:** nyckeltal används först från inlämningsdatum (`fundamentals.point_in_time`), aktier är valbara först från indexinträde (`Store.members`), ML tränas walk-forward. Ändringar får inte bryta detta.
- Nya strategier: ärv `RankStrategy`/`AllocationStrategy` i `backend/app/strategies/`, registrera i `build()`, skriv förklaring i `docs.py`.
- Diagramfärger kommer från CSS-variablerna i `frontend/css/styles.css`. Färg följer entiteten (strategi = slot 1, S&P 500 = 2, Global = 3, OMXS30 = 4, Lika vikt = 5).
- Alpaca-nycklar bara i `.env`, används bara i backend.
- Kör `pytest` efter backendändringar. Starta lokalt med `uvicorn backend.app.main:app --reload`.
- Cache: `data/cache/` (nyckeltalspaneler och ML-poäng) byggs om automatiskt när datan ändras.
