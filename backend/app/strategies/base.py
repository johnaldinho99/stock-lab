"""Strategy building blocks.

Two families:
- AllocationStrategy: decides weights between a few ETFs/cash (60/40, trend, dual momentum).
- RankStrategy: gives every stock a score each month; the portfolio holds the top N,
  equal-weighted, rebalanced every k months, optionally in staggered tranches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..data.store import Store
from ..engine.backtest import equal_weight_targets


@dataclass
class Param:
    key: str
    label: str
    options: list[Any]
    default: Any
    labels: list[str] | None = None  # display text per option
    help: str = ""

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "options": self.options,
            "labels": self.labels or [str(o) for o in self.options],
            "default": self.default,
            "help": self.help,
        }


COST_PARAM = Param(
    "cost",
    "Transaktionskostnad",
    [0.0, 0.001, 0.0025, 0.005],
    0.001,
    ["0 %", "0,10 %", "0,25 %", "0,50 %"],
    "Kostnad per handlad krona (courtage + spread), dras vid varje ombalansering.",
)


@dataclass
class Strategy:
    id: str
    name: str
    family: str  # "Klassiska", "Magic Formula", "Maskininlärning", "Referens"
    tagline: str
    params: list[Param] = field(default_factory=list)
    heavy: bool = False  # expensive first run (ML)

    kind = "stocks"  # class attribute: "stocks" | "allocation"

    def all_params(self) -> list[Param]:
        return [*self.params, COST_PARAM]

    def resolve(self, raw: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for p in self.all_params():
            v = raw.get(p.key, p.default)
            # Query params arrive as strings; match against option types.
            match = next((o for o in p.options if str(o) == str(v)), p.default)
            out[p.key] = match
        return out

    def meta(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "family": self.family,
            "tagline": self.tagline,
            "kind": self.kind,
            "heavy": self.heavy,
            "params": [p.to_json() for p in self.all_params()],
        }

    # Implemented by subclasses ------------------------------------------------
    def targets(self, store: Store, p: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
        """-> (target weights at rebalance dates, asset returns, cash returns)"""
        raise NotImplementedError

    def current(self, store: Store, p: dict) -> dict:
        """What the strategy says to hold *today* (latest data)."""
        raise NotImplementedError

    def diagnostics(self, store: Store, p: dict) -> dict | None:
        return None


# ---------------------------------------------------------------------------
# Allocation strategies
# ---------------------------------------------------------------------------

ETF_NAMES = {
    "SPY": "S&P 500 (SPY)",
    "IEF": "Statsobligationer 7–10 år (IEF)",
    "EFA": "Utvecklade marknader exkl. USA (EFA)",
    "AGG": "Amerikanska obligationer, bred (AGG)",
    "ACWI": "Globala aktier (ACWI)",
    "CASH": "Kontanter / statsskuldväxlar (T-bills)",
}


class AllocationStrategy(Strategy):
    kind = "allocation"

    def weights(self, store: Store, p: dict) -> pd.DataFrame:
        """Monthly target weights (dates x assets incl. CASH)."""
        raise NotImplementedError

    def targets(self, store, p):
        w = self.weights(store, p).dropna(how="any")
        rets = store.etf_returns
        cash = rets["CASH"]
        return w, rets, cash

    def current(self, store, p):
        w = self.weights(store, p).dropna(how="any")
        last = w.iloc[-1]
        holdings = [
            {"ticker": a, "name": ETF_NAMES.get(a, a), "weight": float(v), "tradable": a != "CASH"}
            for a, v in last.items()
            if v > 1e-9
        ]
        return {
            "as_of": w.index[-1].strftime("%Y-%m-%d"),
            "holdings": sorted(holdings, key=lambda h: -h["weight"]),
            "columns": [],
            "signal": self.signal_text(store, p),
            "next_rebalance": "Vid nästa månadsskifte",
        }

    def signal_text(self, store: Store, p: dict) -> str:
        return ""


# ---------------------------------------------------------------------------
# Rank strategies
# ---------------------------------------------------------------------------

UNIVERSE_PARAM = Param(
    "universe",
    "Aktieurval",
    ["all", "sp500", "sp400"],
    "all",
    ["Alla (~900)", "Storbolag (S&P 500)", "Medelstora (S&P 400)"],
    "Vilka bolag strategin får välja bland.",
)


def n_param(options: list[int], default: int) -> Param:
    return Param("n", "Antal aktier", options, default, help="Hur många aktier portföljen håller (lika vikt).")


def rebalance_param(options: list[int], default: int) -> Param:
    labels = {1: "Varje månad", 3: "Varje kvartal", 6: "Varje halvår", 12: "En gång per år"}
    return Param("rebalance", "Ombalansering", options, default, [labels[o] for o in options])


def pct_rank(df: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    """Cross-sectional percentile rank per date (0..1, NaN stays NaN)."""
    return df.rank(axis=1, pct=True, ascending=ascending)


class RankStrategy(Strategy):
    kind = "stocks"
    tranches: int = 1
    min_names: int = 10

    def scores(self, store: Store, p: dict) -> pd.DataFrame:
        """dates x tickers, higher = better, NaN = not eligible."""
        raise NotImplementedError

    def display_columns(self, store: Store, p: dict) -> list[tuple[str, str, str, pd.DataFrame]]:
        """Extra columns for the 'buy today' table: (key, label, format, panel)."""
        return []

    # ---- helpers ----
    def eligible_universe(self, store: Store, p: dict) -> pd.Index:
        uni = p.get("universe", "all")
        info = store.info
        if uni == "sp500":
            return info.index[info["index"] == "S&P 500"]
        if uni == "sp400":
            return info.index[info["index"] == "S&P 400"]
        return info.index

    def _scores(self, store: Store, p: dict) -> pd.DataFrame:
        s = self.scores(store, p)
        allowed = self.eligible_universe(store, p)
        s = s.reindex(columns=store.tickers)
        s.loc[:, ~s.columns.isin(allowed)] = np.nan
        # Must have a price today and have joined the index by then.
        return s.where(store.prices.notna() & store.members)

    def coverage(self, store: Store, p: dict, scores: pd.DataFrame) -> pd.Series:
        """Number of scoreable stocks per date; the backtest starts once it is high enough."""
        return scores.notna().sum(axis=1)

    def selection(self, store: Store, p: dict) -> dict[pd.Timestamp, list[str]]:
        s = self._scores(store, p)
        n = p["n"]
        k = p.get("rebalance", 1)
        tranches = self.tranches
        per = math.ceil(n / tranches)
        valid = self.coverage(store, p, s)
        first = valid[valid >= max(self.min_names, min(per, 30))].index
        if first.empty:
            return {}
        dates = s.index[s.index.get_loc(first[0]) :: k]
        active: list[list[str]] = []
        out: dict[pd.Timestamp, list[list[str]]] = {}
        for d in dates:
            row = s.loc[d].dropna().sort_values(ascending=False)
            if tranches == 1:
                active = [row.index[:per].tolist()]
            else:
                if len(active) == tranches:
                    active.pop(0)  # sell the oldest tranche (held tranches*k months)
                held = {t for tr in active for t in tr}
                active.append([t for t in row.index if t not in held][:per])
            out[d] = [list(tr) for tr in active]
        return out

    def targets(self, store, p):
        sel = self.selection(store, p)
        cols = store.tickers
        if self.tranches == 1:
            w = equal_weight_targets({d: tr[0] for d, tr in sel.items()}, cols)
        else:
            rows = {}
            for d, trs in sel.items():
                row = pd.Series(0.0, index=cols)
                trs = [t for t in trs if t]
                for tr in trs:
                    row[tr] += 1.0 / len(trs) / len(tr)
                rows[d] = row
            w = pd.DataFrame(rows).T.sort_index()
        return w, store.returns, store.risk_free

    def current(self, store, p):
        s = self._scores(store, p)
        d = s.index[-1]
        row = s.loc[d].dropna().sort_values(ascending=False)
        n = p["n"]
        picks = row.index[:n].tolist()
        info = store.info
        cols = self.display_columns(store, p)
        holdings = []
        for rank, t in enumerate(picks, start=1):
            h = {
                "ticker": t,
                "name": str(info.at[t, "name"]),
                "sector": str(info.at[t, "sector"]),
                "weight": 1.0 / len(picks),
                "rank": rank,
                "score": float(row[t]),
                "price": _f(store.close.at[d, t]),
                "tradable": True,
            }
            for key, _label, _fmt, panel in cols:
                h[key] = _f(panel.at[d, t]) if t in panel.columns and d in panel.index else None
            holdings.append(h)
        k = p.get("rebalance", 1)
        return {
            "as_of": d.strftime("%Y-%m-%d"),
            "holdings": holdings,
            "columns": [{"key": c[0], "label": c[1], "format": c[2]} for c in cols],
            "signal": f"Rangordning per {d.strftime('%Y-%m-%d')} bland {len(row)} valbara bolag.",
            "next_rebalance": {1: "Varje månad", 3: "Var tredje månad", 6: "Varje halvår", 12: "En gång per år"}[k]
            + (f" ({self.tranches} trancher – köp ~{math.ceil(n / self.tranches)} nya aktier varje gång)" if self.tranches > 1 else ""),
            "eligible": int(len(row)),
        }


def _f(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None
