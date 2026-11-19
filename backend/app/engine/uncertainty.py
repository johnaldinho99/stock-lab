"""Uncertainty estimates via block bootstrap.

Monthly returns are resampled in blocks of consecutive months (default 12), so
that streaks, crashes and volatility clustering survive the resampling. The
strategy and its benchmark are always resampled with *the same* months, which
keeps their correlation intact when we ask "how often does it beat the index?".

All of this assumes the future looks statistically like the backtest period -
the biggest caveat, and it is shown in the UI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PCTS = (5, 25, 50, 75, 95)
HORIZONS = (12, 36, 60, 120)


def block_indices(n: int, length: int, paths: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """(paths x length) month indices made of circular blocks."""
    n_blocks = int(np.ceil(length / block))
    starts = rng.integers(0, n, size=(paths, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]) % n
    return idx.reshape(paths, -1)[:, :length]


def _ann(total: np.ndarray, months: int) -> np.ndarray:
    return np.where(total > 0, total ** (12 / months) - 1, -1.0)


def forecast(
    returns: pd.Series,
    bench: pd.Series | None,
    horizon: int = 120,
    paths: int = 4000,
    block: int = 12,
    seed: int = 7,
) -> dict:
    """Fan chart + horizon table for future returns."""
    r = returns.dropna()
    rng = np.random.default_rng(seed)
    idx = block_indices(len(r), horizon, paths, block, rng)
    sim = r.to_numpy()[idx]
    paths_value = np.cumprod(1 + sim, axis=1)  # paths x horizon

    b_paths = None
    if bench is not None:
        b = bench.reindex(r.index)
        if b.notna().all():
            b_paths = np.cumprod(1 + b.to_numpy()[idx], axis=1)

    fan = {f"p{p}": np.percentile(paths_value, p, axis=0).tolist() for p in PCTS}
    if b_paths is not None:
        fan["bench_p50"] = np.percentile(b_paths, 50, axis=0).tolist()

    table = []
    for h in HORIZONS:
        if h > horizon:
            continue
        tot = paths_value[:, h - 1]
        ann = _ann(tot, h)
        row = {
            "months": h,
            "annualized": {f"p{p}": float(np.percentile(ann, p)) for p in PCTS},
            "total": {f"p{p}": float(np.percentile(tot - 1, p)) for p in PCTS},
            "prob_loss": float((tot < 1).mean()),
            "prob_double": float((tot >= 2).mean()),
        }
        if b_paths is not None:
            row["prob_beat_bench"] = float((tot > b_paths[:, h - 1]).mean())
            row["bench_annualized_p50"] = float(np.percentile(_ann(b_paths[:, h - 1], h), 50))
        table.append(row)
    return {"months": list(range(1, horizon + 1)), "fan": fan, "table": table, "paths": paths, "block": block}


def cagr_interval(returns: pd.Series, bench: pd.Series | None, paths: int = 4000, block: int = 12, seed: int = 11) -> dict:
    """Confidence interval for the *historical* average return (and the edge vs benchmark):
    how sure can we be that the backtest's CAGR was not luck?"""
    r = returns.dropna()
    n = len(r)
    rng = np.random.default_rng(seed)
    idx = block_indices(n, n, paths, block, rng)
    tot = np.prod(1 + r.to_numpy()[idx], axis=1)
    c = _ann(tot, n)
    out = {
        "cagr": {"p2_5": float(np.percentile(c, 2.5)), "p50": float(np.percentile(c, 50)), "p97_5": float(np.percentile(c, 97.5))},
        "prob_positive": float((c > 0).mean()),
    }
    if bench is not None:
        b = bench.reindex(r.index)
        if b.notna().all():
            btot = np.prod(1 + b.to_numpy()[idx], axis=1)
            edge = c - _ann(btot, n)
            out["edge"] = {
                "p2_5": float(np.percentile(edge, 2.5)),
                "p50": float(np.percentile(edge, 50)),
                "p97_5": float(np.percentile(edge, 97.5)),
            }
            out["prob_edge_positive"] = float((edge > 0).mean())
            # Simple t-statistic of the monthly difference (overlapping-free, iid assumption).
            d = (r - b).to_numpy()
            out["t_stat"] = float(d.mean() / (d.std(ddof=1) / np.sqrt(n))) if d.std(ddof=1) > 0 else None
    return out


def rolling_12m(returns: pd.Series, bins: int = 24) -> dict:
    """Distribution of all historical 12-month holding periods (what a purchase made
    on a random month-end returned over the following year)."""
    r = returns.dropna()
    roll = (1 + r).rolling(12).apply(np.prod, raw=True).dropna() - 1
    if roll.empty:
        return {}
    lo, hi = float(roll.min()), float(roll.max())
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(roll, bins=edges)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in roll.index],
        "values": roll.round(5).tolist(),
        "hist": {"edges": edges.tolist(), "counts": counts.tolist()},
        "pcts": {f"p{p}": float(np.percentile(roll, p)) for p in PCTS},
        "prob_loss": float((roll < 0).mean()),
        "n": int(len(roll)),
    }
