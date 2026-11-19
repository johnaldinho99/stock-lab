"""Engine tests on synthetic data - no network, no downloaded files needed."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.data import fundamentals as fund
from backend.app.data.store import Store, month_ends
from backend.app.engine import metrics, uncertainty
from backend.app.engine.backtest import run_backtest
from backend.app.strategies.registry import STRATEGIES
from backend.app.strategies.magic import MagicStaggered

MONTHS = pd.date_range("2020-01-31", periods=24, freq="ME")


# ---------------------------------------------------------------------------
# Backtest simulator
# ---------------------------------------------------------------------------

def test_buy_and_hold_matches_asset_return():
    r = pd.DataFrame({"A": 0.01, "B": -0.02}, index=MONTHS)
    targets = pd.DataFrame({"A": [1.0], "B": [0.0]}, index=MONTHS[:1])
    bt = run_backtest(targets, r, pd.Series(0.0, index=MONTHS), cost=0.0)
    assert len(bt.returns) == len(MONTHS) - 1
    assert np.allclose(bt.returns, 0.01)


def test_costs_are_charged_on_turnover_and_cash_is_free():
    r = pd.DataFrame({"A": 0.0, "CASH": 0.0}, index=MONTHS)
    # Month 0: buy A (turnover 1.0). Month 1: move to cash (sell A = 1.0, cash leg free).
    targets = pd.DataFrame({"A": [1.0, 0.0], "CASH": [0.0, 1.0]}, index=MONTHS[:2])
    bt = run_backtest(targets, r, pd.Series(0.0, index=MONTHS), cost=0.01)
    assert [rb.turnover for rb in bt.rebalances] == [1.0, 1.0]
    assert bt.returns.iloc[0] == pytest.approx(-0.01)
    assert bt.returns.iloc[1] == pytest.approx(-0.01)
    assert bt.returns.iloc[2] == pytest.approx(0.0)


def test_weights_drift_between_rebalances():
    r = pd.DataFrame({"A": 1.0, "B": 0.0}, index=MONTHS[:3])  # A doubles every month
    targets = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=MONTHS[:1])
    bt = run_backtest(targets, r, pd.Series(0.0, index=MONTHS[:3]), cost=0.0)
    # Month 1: 0.5*100 % = +50 %. Then A weighs 2/3 -> month 2: +66.7 %.
    assert bt.returns.iloc[0] == pytest.approx(0.5)
    assert bt.returns.iloc[1] == pytest.approx(2 / 3)


def test_unallocated_weight_earns_cash_rate():
    r = pd.DataFrame({"A": 0.0}, index=MONTHS[:2])
    targets = pd.DataFrame({"A": [0.5]}, index=MONTHS[:1])
    bt = run_backtest(targets, r, pd.Series(0.02, index=MONTHS[:2]), cost=0.0)
    assert bt.returns.iloc[0] == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Metrics and uncertainty
# ---------------------------------------------------------------------------

def test_cagr_and_drawdown():
    r = pd.Series([0.1, -0.5, 0.2] + [0.0] * 9, index=MONTHS[:12])
    assert metrics.cagr(r) == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    dd = metrics.drawdown(r)
    assert dd.min() == pytest.approx(-0.5)


def test_summary_beta_of_index_against_itself_is_one():
    rng = np.random.default_rng(0)
    b = pd.Series(rng.normal(0.01, 0.04, 60), index=pd.date_range("2015-01-31", periods=60, freq="ME"))
    s = metrics.summary(b, pd.Series(0.0, index=b.index), b)
    assert s["beta"] == pytest.approx(1.0)
    assert s["alpha"] == pytest.approx(0.0, abs=1e-12)


def test_forecast_percentiles_are_ordered_and_paired():
    rng = np.random.default_rng(1)
    idx = pd.date_range("2010-01-31", periods=120, freq="ME")
    r = pd.Series(rng.normal(0.01, 0.05, 120), index=idx)
    out = uncertainty.forecast(r, r, horizon=60, paths=500)
    for row in out["table"]:
        a = row["annualized"]
        assert a["p5"] <= a["p25"] <= a["p50"] <= a["p75"] <= a["p95"]
        # Same series resampled with the same months can never beat itself.
        assert row["prob_beat_bench"] == 0.0
    ci = uncertainty.cagr_interval(r, r, paths=500)
    assert ci["edge"]["p2_5"] == pytest.approx(0.0) and ci["edge"]["p97_5"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Point-in-time fundamentals: no look-ahead
# ---------------------------------------------------------------------------

def test_point_in_time_uses_only_filed_facts():
    long = pd.DataFrame(
        {
            "cik": [1, 1],
            "field": ["ebit", "ebit"],
            "priority": [0, 0],
            "end": pd.to_datetime(["2019-12-31", "2020-12-31"]),
            "filed": pd.to_datetime(["2020-02-15", "2021-02-20"]),
            "val": [100.0, 200.0],
        }
    )
    dates = pd.DatetimeIndex(pd.to_datetime(["2020-01-31", "2020-03-31", "2021-01-29", "2021-02-26"]))
    values, ends = fund.point_in_time(long, "ebit", dates)
    assert np.isnan(values.iloc[0, 0])  # nothing filed yet
    assert values.iloc[1, 0] == 100.0
    assert values.iloc[2, 0] == 100.0  # FY2020 ended but not yet filed
    assert values.iloc[3, 0] == 200.0


def test_extract_facts_keeps_only_annual_durations():
    doc = {"facts": {"us-gaap": {"OperatingIncomeLoss": {"units": {"USD": [
        {"start": "2020-01-01", "end": "2020-12-31", "filed": "2021-02-01", "val": 10},
        {"start": "2020-10-01", "end": "2020-12-31", "filed": "2021-02-01", "val": 3},  # quarter
    ]}}}}}
    rows = fund.extract_facts(1, doc)
    assert [r["val"] for r in rows] == [10.0]


# ---------------------------------------------------------------------------
# Strategies on a small synthetic market
# ---------------------------------------------------------------------------

def _synthetic_store(n_stocks: int = 40, years: int = 4) -> Store:
    rng = np.random.default_rng(42)
    days = pd.bdate_range("2018-01-01", periods=252 * years)
    tickers = [f"S{i:02d}" for i in range(n_stocks)]
    # Stock i has drift proportional to i -> momentum should prefer high i.
    drift = np.linspace(-0.0005, 0.001, n_stocks)
    rets = rng.normal(drift, 0.01, size=(len(days), n_stocks))
    px = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=days, columns=tickers)
    uni = pd.DataFrame(
        {
            "ticker": tickers,
            "name": tickers,
            "sector": "Industrials",
            "industry": "x",
            "index": "S&P 500",
            "cik": pd.array(range(1, n_stocks + 1), dtype="Int64"),
            # Best stock joins the index late: it must not be bought before that.
            "eligible_from": [pd.NaT] * (n_stocks - 1) + [pd.Timestamp("2020-06-30")],
        }
    )
    market = pd.DataFrame({"SPY": px.mean(axis=1), "^IRX": 2.0}, index=days)
    for etf in ["IEF", "EFA", "AGG", "ACWI"]:
        market[etf] = 100.0
    return Store(
        universe=uni,
        daily_adj=px,
        daily_close=px,
        daily_splits=pd.DataFrame(0.0, index=days, columns=tickers),
        market_adj=market,
        facts=None,
    )


def test_month_ends_are_last_trading_days():
    days = pd.bdate_range("2021-01-01", "2021-03-31")
    me = month_ends(days)
    assert [d.strftime("%Y-%m-%d") for d in me] == ["2021-01-29", "2021-02-26", "2021-03-31"]


def test_momentum_picks_winners_and_respects_index_entry():
    store = _synthetic_store()
    strat = STRATEGIES["momentum"]
    p = strat.resolve({"n": 10, "rebalance": 1})
    targets, rets, cash = strat.targets(store, p)
    late = "S39"
    before = targets.loc[targets.index < pd.Timestamp("2020-06-30"), late]
    assert (before == 0).all()
    assert (targets.loc[targets.index >= pd.Timestamp("2020-07-31"), late] > 0).any()
    # On average the chosen stocks should be the high-drift ones.
    chosen = targets.iloc[-12:].gt(0).sum()
    assert chosen[chosen > 0].index.map(lambda t: int(t[1:])).to_series().mean() > 20
    bt = run_backtest(targets, rets, cash, cost=p["cost"])
    assert len(bt.returns) > 12


def test_staggered_tranches_hold_four_distinct_sleeves():
    store = _synthetic_store()

    class Toy(MagicStaggered):
        min_names = 5

        def scores(self, store, p):  # simple deterministic score instead of fundamentals
            return store.momentum(6)

        def coverage(self, store, p, scores):
            return scores.notna().sum(axis=1)

        def eligible_universe(self, store, p):
            return store.info.index

    strat = Toy("t", "T", "Magic Formula", "")
    sel = strat.selection(store, {"n": 8, "rebalance": 3})
    last = list(sel.values())[-1]
    assert len(last) == 4
    names = [t for tr in last for t in tr]
    assert len(names) == len(set(names)) == 8  # each tranche buys stocks not already held


def test_trend_following_goes_to_cash_below_average():
    store = _synthetic_store()
    strat = STRATEGIES["trend_sma"]
    w = strat.weights(store, strat.resolve({"sma": 6, "off_asset": "CASH"}))
    assert set(w.sum(axis=1).round(6)) == {1.0}
    px = store.market_monthly["SPY"]
    on = (px > px.rolling(6).mean()).reindex(w.index)
    assert ((w["SPY"] == 1.0) == on).all()
