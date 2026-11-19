"""Monthly portfolio simulator.

A strategy hands over *target weights* on its rebalance dates. Between rebalances
the holdings drift with the market. At each rebalance we pay transaction costs on
the traded value (turnover). Weight not allocated to any asset sits in cash and
earns the T-bill rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Rebalance:
    date: pd.Timestamp
    weights: dict[str, float]  # target after trading
    buys: list[str]
    sells: list[str]
    turnover: float  # one-way, share of portfolio traded (0..2)


@dataclass
class BacktestResult:
    returns: pd.Series  # net monthly returns, indexed by month-end
    gross_returns: pd.Series
    rebalances: list[Rebalance] = field(default_factory=list)

    @property
    def start(self) -> pd.Timestamp:
        return self.returns.index[0]


def run_backtest(
    targets: pd.DataFrame,
    returns: pd.DataFrame,
    cash_returns: pd.Series,
    cost: float = 0.001,
) -> BacktestResult:
    """
    targets: rebalance dates x assets, target weights (rows may sum to < 1 -> rest is cash)
    returns: dates x assets, return earned *during* month t (NaN counts as 0 %)
    cash_returns: return of cash during month t
    cost: transaction cost per traded dollar (0.001 = 0.1 %)
    """
    targets = targets.dropna(how="all").fillna(0.0)
    targets = targets[targets.index.isin(returns.index)]
    if targets.empty:
        raise ValueError("Strategin gav inga innehav i perioden.")
    assets = list(targets.columns)
    R = returns.reindex(columns=assets).fillna(0.0).to_numpy()
    rc = cash_returns.reindex(returns.index).fillna(0.0).to_numpy()
    dates = returns.index
    target_pos = {d: i for i, d in enumerate(targets.index)}
    T = targets.to_numpy()
    # An explicit "CASH" column (allocation strategies) is not a trade when it changes.
    traded = np.array([a != "CASH" for a in assets], dtype=float)

    start = dates.get_loc(targets.index[0])
    h = np.zeros(len(assets))  # current weights (drifted)
    out_net, out_gross, out_dates = [], [], []
    rebals: list[Rebalance] = []
    pending_cost = 0.0

    for i in range(start, len(dates)):
        d = dates[i]
        if d in target_pos:
            w = T[target_pos[d]]
            trade = w - h
            # Traded value in stocks/ETFs; moving money in/out of cash is free.
            turnover = float((np.abs(trade) * traded).sum())
            pending_cost = turnover * cost
            prev_held = {assets[j] for j in np.flatnonzero(h > 1e-9)}
            now_held = {assets[j] for j in np.flatnonzero(w > 1e-9)}
            rebals.append(
                Rebalance(
                    date=d,
                    weights={assets[j]: float(w[j]) for j in np.flatnonzero(w > 1e-9)},
                    buys=sorted(now_held - prev_held),
                    sells=sorted(prev_held - now_held),
                    turnover=turnover,
                )
            )
            h = w.copy()
        if i + 1 >= len(dates):
            break
        r = R[i + 1]
        cash_w = 1.0 - h.sum()
        gross = float(h @ r + cash_w * rc[i + 1])
        net = (1 - pending_cost) * (1 + gross) - 1
        pending_cost = 0.0
        # drift
        grown = h * (1 + r)
        h = grown / (1 + gross) if (1 + gross) > 0 else grown
        out_dates.append(dates[i + 1])
        out_gross.append(gross)
        out_net.append(net)

    idx = pd.DatetimeIndex(out_dates)
    return BacktestResult(
        returns=pd.Series(out_net, index=idx, name="strategy"),
        gross_returns=pd.Series(out_gross, index=idx, name="gross"),
        rebalances=rebals,
    )


def equal_weight_targets(selection: dict[pd.Timestamp, list[str]], columns: list[str]) -> pd.DataFrame:
    rows = {}
    for d, names in selection.items():
        row = pd.Series(0.0, index=columns)
        if names:
            row[names] = 1.0 / len(names)
        rows[d] = row
    return pd.DataFrame(rows).T.sort_index()
