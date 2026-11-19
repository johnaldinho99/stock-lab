"""Paths and settings. Secrets come from `.env` (never committed)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("STOCKLAB_DATA_DIR", ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
FRONTEND_DIR = ROOT / "frontend"

# Raw history starts here; individual strategies start later when they need warm-up.
HISTORY_START = "2000-01-01"

ALPACA_KEY_ID = os.getenv("ALPACA_API_KEY_ID", "").strip()
ALPACA_SECRET = os.getenv("ALPACA_API_SECRET_KEY", "").strip()
ALPACA_FEED = os.getenv("ALPACA_DATA_FEED", "iex").strip() or "iex"
ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "stock-lab research tool admin@example.com")

# Benchmarks (all in USD). OMXS30 is converted from SEK with the USD/SEK rate.
BENCHMARKS = {
    "sp500": {"name": "S&P 500", "ticker": "^SP500TR", "note": "Totalavkastningsindex (inkl. utdelningar)"},
    "global": {"name": "Globalindex (MSCI ACWI)", "ticker": "ACWI", "note": "iShares MSCI ACWI ETF, inkl. utdelningar"},
    "omxs30": {"name": "OMXS30", "ticker": "^OMX", "note": "Prisindex utan utdelningar, omräknat till USD"},
}
FX_USDSEK = "SEK=X"  # SEK per USD
RISK_FREE = "^IRX"  # 13-week T-bill yield, % per year

# ETFs used by asset-allocation strategies.
ETFS = ["SPY", "IEF", "EFA", "AGG", "ACWI"]

# Sectors Greenblatt excludes from the Magic Formula.
MF_EXCLUDED_SECTORS = {"Financials", "Utilities", "Real Estate"}


def alpaca_enabled() -> bool:
    return bool(ALPACA_KEY_ID and ALPACA_SECRET)
