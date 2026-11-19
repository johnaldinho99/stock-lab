"""Turns a strategy + parameters into the JSON the frontend renders."""

from __future__ import annotations

import threading
from collections import OrderedDict

import numpy as np
import pandas as pd

from . import config
from .data.store import get_store
from .docs import DOCS, GENERAL
from .engine import metrics, uncertainty
from .engine.backtest import run_backtest
from .strategies.registry import FAMILY_ORDER, STRATEGIES

_cache: OrderedDict = OrderedDict()
_lock = threading.Lock()
CACHE_SIZE = 96


def _cached(key, fn):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    value = fn()
    with _lock:
        _cache[key] = value
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _dates(idx) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in idx]


def _num(values, digits: int = 6) -> list:
    arr = np.asarray(values, dtype=float)
    return [None if not np.isfinite(v) else round(float(v), digits) for v in arr]


# ---------------------------------------------------------------------------


def run(strategy_id: str, raw_params: dict):
    """Full-history backtest (cached)."""
    strat = STRATEGIES[strategy_id]
    p = strat.resolve(raw_params)
    key = ("run", strategy_id, tuple(sorted(p.items())))

    def compute():
        store = get_store()
        targets, rets, cash = strat.targets(store, p)
        bt = run_backtest(targets, rets, cash, cost=p["cost"])
        return strat, p, bt

    return _cached(key, compute)


def strategy_list() -> dict:
    store = get_store()
    items = []
    for s in STRATEGIES.values():
        m = s.meta()
        try:
            _, _, bt = run(s.id, {})
            r = bt.returns
            common = r[r.index >= _common_start(store)]
            m["headline"] = {
                "cagr": metrics.cagr(common),
                "sp500_cagr": metrics.cagr(store.benchmark_returns["sp500"].reindex(common.index)),
                "start": common.index[0].strftime("%Y-%m-%d"),
            }
            m["available_from"] = bt.returns.index[0].strftime("%Y-%m-%d")
        except Exception as exc:  # keep the list usable even if one strategy fails
            m["error"] = str(exc)
        items.append(m)
    items.sort(key=lambda m: (FAMILY_ORDER.index(m["family"]), m["name"] if m["family"] == "Referens" else ""))
    return {
        "strategies": items,
        "families": FAMILY_ORDER,
        "benchmarks": [{"id": k, **v} for k, v in config.BENCHMARKS.items()],
        "common_start": _common_start(store).strftime("%Y-%m-%d"),
        "data": data_status(),
        "general": GENERAL,
    }


def _common_start(store) -> pd.Timestamp:
    """First month where the stock strategies (fundamentals) and all benchmarks exist."""
    lv = store.benchmark_levels.dropna()
    return max(lv.index[0], pd.Timestamp("2011-06-30"))


def data_status() -> dict:
    store = get_store()
    return {
        "last_price_date": store.last_date.strftime("%Y-%m-%d"),
        "built_at": store.meta.get("built_at"),
        "stocks": len(store.tickers),
        "alpaca": config.alpaca_enabled(),
    }


def strategy_detail(strategy_id: str, raw_params: dict, start: str | None = None) -> dict:
    strat, p, bt = run(strategy_id, raw_params)
    store = get_store()
    key = ("detail", strategy_id, tuple(sorted(p.items())), start)
    return _cached(key, lambda: _detail(strat, p, bt, store, start))


def _detail(strat, p, bt, store, start: str | None) -> dict:
    r = bt.returns
    if start:
        r = r[r.index > pd.Timestamp(start)]
    if len(r) < 24:
        raise ValueError("För kort period – välj ett tidigare startår.")
    idx = r.index
    t0 = idx[0] - pd.offsets.MonthEnd(1)  # value 1.0 at the start
    rf = store.risk_free
    bench_r = store.benchmark_returns.reindex(idx)
    sp = bench_r["sp500"]

    # Equal-weight universe as an extra reference line for stock strategies.
    ew = None
    if strat.kind == "stocks" and strat.id != "ew_universe":
        _, _, ew_bt = run("ew_universe", {"cost": p["cost"]})
        ew = ew_bt.returns.reindex(idx)

    def growth_line(x: pd.Series):
        g = (1 + x).cumprod()
        # Benchmarks may start later (e.g. ACWI 2008); they then begin at their first value.
        return _num(g.where(x.notna().cummax()), 5)

    series = {
        "dates": _dates([t0, *idx]),
        "strategy": [1.0, *growth_line(r)],
        "benchmarks": {k: [1.0 if bench_r[k].notna().iloc[0] else None, *growth_line(bench_r[k])] for k in bench_r.columns},
        "drawdown": {"strategy": [0.0, *_num(metrics.drawdown(r), 5)], "sp500": [0.0, *_num(metrics.drawdown(sp.fillna(0)), 5)]},
    }
    if ew is not None:
        series["ew_universe"] = [1.0, *growth_line(ew)]

    years = metrics.annual_returns(r)
    annual = {
        "years": [int(y) for y in years.index],
        "strategy": _num(years.values, 5),
        "benchmarks": {
            k: _num(metrics.annual_returns(bench_r[k].dropna()).reindex(years.index).values, 5) for k in bench_r.columns
        },
    }

    stats = {"strategy": metrics.summary(r, rf, sp)}
    for k in bench_r.columns:
        b = bench_r[k].dropna()
        stats[k] = metrics.summary(b, rf, sp if k != "sp500" else None)
    if ew is not None:
        stats["ew_universe"] = metrics.summary(ew.dropna(), rf, sp)

    turnover = [rb.turnover for rb in bt.rebalances if rb.date >= idx[0]]
    n_rebal = len(turnover)
    stats["strategy"]["avg_turnover"] = float(np.mean(turnover)) if turnover else 0.0
    stats["strategy"]["rebalances"] = n_rebal
    stats["strategy"]["annual_turnover"] = float(np.sum(turnover) / (len(r) / 12)) if turnover else 0.0

    unc = {
        "forecast": uncertainty.forecast(r, sp if sp.notna().all() else None),
        "historical": uncertainty.cagr_interval(r, sp if sp.notna().all() else None),
        "rolling12": uncertainty.rolling_12m(r),
        "rolling12_bench": uncertainty.rolling_12m(sp.dropna()),
    }

    detail = {
        "strategy": strat.meta(),
        "params": p,
        "doc": DOCS.get(strat.id, {}),
        "series": series,
        "annual": annual,
        "stats": stats,
        "uncertainty": unc,
        "rebalances": _rebalance_log(strat, bt, store, idx[0]),
        "current": strat.current(store, p),
        "diagnostics": strat.diagnostics(store, p),
        "data": data_status(),
    }
    if strat.kind == "allocation":
        detail["allocation"] = _allocation(bt, idx)
    return detail


def _rebalance_log(strat, bt, store, start: pd.Timestamp, limit: int = 400) -> list[dict]:
    """Every rebalance: what was bought/sold and the resulting portfolio."""
    from .strategies.base import ETF_NAMES

    info = store.info
    rows = []
    prev_value = None
    for rb in bt.rebalances:
        if rb.date < start - pd.offsets.MonthEnd(12):
            continue

        def name(t):
            if strat.kind == "allocation":
                return ETF_NAMES.get(t, t)
            return str(info.at[t, "name"]) if t in info.index else t

        rows.append(
            {
                "date": rb.date.strftime("%Y-%m-%d"),
                "holdings": [
                    {"ticker": t, "name": name(t), "weight": round(w, 5)}
                    for t, w in sorted(rb.weights.items(), key=lambda kv: -kv[1])
                ],
                "buys": rb.buys,
                "sells": rb.sells,
                "turnover": round(rb.turnover, 4),
                "cash": round(1 - sum(rb.weights.values()), 5),
            }
        )
        prev_value = rb
    return rows[-limit:]


def _allocation(bt, idx) -> dict:
    """Weights over time (for allocation strategies): stacked area."""
    dates, rows = [], []
    for rb in bt.rebalances:
        dates.append(rb.date)
        rows.append(rb.weights)
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(dates)).fillna(0.0)
    df["CASH"] = df.get("CASH", 0.0) + (1 - df.sum(axis=1)).clip(lower=0)
    df = df[df.index >= idx[0] - pd.offsets.MonthEnd(1)]
    df = df.loc[:, (df > 1e-9).any()]
    return {"dates": _dates(df.index), "assets": {c: _num(df[c].values, 4) for c in df.columns}}


def compare(start: str | None = None) -> dict:
    """Headline numbers for all strategies over one common period."""
    store = get_store()
    t0 = pd.Timestamp(start) if start else _common_start(store)
    rf = store.risk_free
    rows = []
    for s in STRATEGIES.values():
        try:
            _, _, bt = run(s.id, {})
        except Exception as exc:
            rows.append({"id": s.id, "name": s.name, "family": s.family, "error": str(exc)})
            continue
        r = bt.returns[bt.returns.index > t0]
        if len(r) < 24:
            continue
        sp = store.benchmark_returns["sp500"].reindex(r.index)
        stats = metrics.summary(r, rf, sp)
        rows.append({"id": s.id, "name": s.name, "family": s.family, "kind": s.kind, **stats})
    bench = []
    for k, b in config.BENCHMARKS.items():
        r = store.benchmark_returns[k]
        r = r[r.index > t0].dropna()
        bench.append({"id": k, "name": b["name"], **metrics.summary(r, rf)})
    return {"start": t0.strftime("%Y-%m-%d"), "strategies": rows, "benchmarks": bench}


def warm_ml(force: bool = False) -> None:
    from .strategies.ml import get_ml

    store = get_store()
    for kind in ("gbm", "ridge"):
        res = get_ml(store, kind, force=force)
        print(f"  {kind}: {res.n_models} modeller, IC {res.ic.mean():.4f}")
