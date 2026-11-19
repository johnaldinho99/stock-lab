"""Download / refresh all data used by Aktielabbet.

    python -m scripts.build_data              # everything (first run ~10 min)
    python -m scripts.build_data --prices     # only refresh prices (daily update)
    python -m scripts.build_data --ml         # only (re)train ML models
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import pandas as pd

from backend.app import config
from backend.app.data import fundamentals, prices, universe


def step_universe() -> pd.DataFrame:
    print("1/4 Universe (S&P 500 + S&P 400) ...")
    uni = universe.fetch_universe()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    uni.to_parquet(config.DATA_DIR / "universe.parquet")
    print(f"  {len(uni)} stocks, {uni['cik'].notna().sum()} with CIK")
    return uni


def load_universe() -> pd.DataFrame:
    path = config.DATA_DIR / "universe.parquet"
    return pd.read_parquet(path) if path.exists() else step_universe()


def step_prices(uni: pd.DataFrame) -> None:
    print("2/4 Prices (Yahoo Finance) ...")
    stocks = prices.download_prices(uni["ticker"].tolist())
    prices.save_prices(stocks, "stocks")
    print(f"  stocks: {stocks['adj_close'].shape[1]} tickers, {len(stocks['adj_close'])} days")
    market_tickers = sorted(
        {b["ticker"] for b in config.BENCHMARKS.values()} | set(config.ETFS) | {config.FX_USDSEK, config.RISK_FREE}
    )
    market = prices.download_prices(market_tickers, chunk=len(market_tickers))
    prices.save_prices(market, "market")
    print(f"  market: {market['adj_close'].shape[1]} series")


def step_fundamentals(uni: pd.DataFrame) -> None:
    print("3/4 Fundamentals (SEC EDGAR) ...")
    t0 = time.time()
    df = fundamentals.download_fundamentals(uni["cik"].dropna().astype(int).tolist())
    df.to_parquet(config.DATA_DIR / "fundamentals.parquet")
    print(f"  {len(df):,} facts for {df['cik'].nunique()} companies in {time.time() - t0:.0f}s")


def step_ml() -> None:
    print("4/4 Training ML models (walk-forward) ...")
    from backend.app import service

    service.warm_ml(force=True)


def write_meta() -> None:
    adj = pd.read_parquet(config.DATA_DIR / "stocks_adj_close.parquet")
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_price_date": adj.index.max().strftime("%Y-%m-%d"),
    }
    (config.DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", action="store_true", help="only refresh prices")
    ap.add_argument("--fundamentals", action="store_true", help="only refresh fundamentals")
    ap.add_argument("--ml", action="store_true", help="only retrain ML models")
    ap.add_argument("--no-ml", action="store_true", help="skip ML training")
    args = ap.parse_args()
    only = args.prices or args.fundamentals or args.ml

    if not only:
        uni = step_universe()
    else:
        uni = load_universe()
    if not only or args.prices:
        step_prices(uni)
        write_meta()
    if not only or args.fundamentals:
        step_fundamentals(uni)
    if (not only and not args.no_ml) or args.ml or args.prices:
        # ML scores depend on prices, so they are refreshed after a price update.
        step_ml()
    print("Klart.")


if __name__ == "__main__":
    main()
