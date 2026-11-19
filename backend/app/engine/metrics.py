"""Performance statistics for monthly return series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _clean(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


def growth(returns: pd.Series, start_value: float = 1.0) -> pd.Series:
    return start_value * (1 + returns.fillna(0)).cumprod()


def cagr(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return np.nan
    total = float((1 + r).prod())
    years = len(r) / 12
    return total ** (1 / years) - 1 if total > 0 else -1.0


def drawdown(returns: pd.Series) -> pd.Series:
    g = growth(returns)
    peak = np.maximum(g.cummax(), 1.0)
    return g / peak - 1


def annual_returns(returns: pd.Series) -> pd.Series:
    r = returns.dropna()
    return (1 + r).groupby(r.index.year).prod() - 1


def summary(returns: pd.Series, rf: pd.Series, bench: pd.Series | None = None) -> dict:
    """Key numbers. `bench` (same index) enables beta/alpha/tracking error."""
    r = returns.dropna()
    if len(r) < 3:
        return {}
    rf = rf.reindex(r.index).fillna(0)
    ex = r - rf
    vol = float(r.std(ddof=1) * np.sqrt(12))
    downside = float(np.sqrt((np.minimum(ex, 0) ** 2).mean()) * np.sqrt(12))
    dd = drawdown(r)
    c = cagr(r)
    ann = annual_returns(r)
    out = {
        "start": r.index[0].strftime("%Y-%m-%d"),
        "end": r.index[-1].strftime("%Y-%m-%d"),
        "months": int(len(r)),
        "total_return": float((1 + r).prod() - 1),
        "cagr": c,
        "volatility": vol,
        "sharpe": float(ex.mean() * 12 / vol) if vol > 0 else np.nan,
        "sortino": float(ex.mean() * 12 / downside) if downside > 0 else np.nan,
        "max_drawdown": float(dd.min()),
        "max_drawdown_date": dd.idxmin().strftime("%Y-%m-%d"),
        "calmar": float(c / abs(dd.min())) if dd.min() < 0 else np.nan,
        "best_month": float(r.max()),
        "worst_month": float(r.min()),
        "positive_months": float((r > 0).mean()),
        "best_year": float(ann.max()) if len(ann) else np.nan,
        "worst_year": float(ann.min()) if len(ann) else np.nan,
    }
    if bench is not None:
        b = bench.reindex(r.index)
        ok = b.notna()
        if ok.sum() >= 12:
            rr, bb, ff = r[ok], b[ok], rf[ok]
            cov = np.cov(rr - ff, bb - ff, ddof=1)
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
            alpha = ((rr - ff) - beta * (bb - ff)).mean() * 12
            diff = rr - bb
            te = float(diff.std(ddof=1) * np.sqrt(12))
            out.update(
                {
                    "beta": float(beta),
                    "alpha": float(alpha),
                    "correlation": float(np.corrcoef(rr, bb)[0, 1]),
                    "tracking_error": te,
                    "information_ratio": float(diff.mean() * 12 / te) if te > 0 else np.nan,
                    "excess_cagr": cagr(rr) - cagr(bb),
                    "months_beating": float((diff > 0).mean()),
                }
            )
    return {k: (_clean(v) if isinstance(v, (float, np.floating, int)) and not isinstance(v, bool) else v) for k, v in out.items()}
