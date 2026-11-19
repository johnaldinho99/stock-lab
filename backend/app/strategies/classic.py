"""Classic rule-based strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import AllocationStrategy, Param, RankStrategy, n_param, rebalance_param


class EqualWeightUniverse(RankStrategy):
    """Every stock in the universe, equal weight - the fair internal benchmark
    (same survivorship bias as the stock strategies)."""

    def scores(self, store, p):
        has_history = store.prices.notna() & store.prices.shift(12).notna() & store.members
        return has_history.astype(float).where(has_history)

    def selection(self, store, p):
        p = {**p, "n": 10_000}
        return super().selection(store, p)

    def current(self, store, p):
        out = super().current(store, {**p, "n": 10_000})
        out["holdings"] = sorted(out["holdings"], key=lambda h: h["ticker"])
        return out


class SixtyForty(AllocationStrategy):
    def weights(self, store, p):
        r = store.etf_returns
        w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
        w["SPY"], w["IEF"] = p["stock_share"], 1 - p["stock_share"]
        return w[store.market_monthly["IEF"].notna()]

    def signal_text(self, store, p):
        s = p["stock_share"]
        return f"Fast fördelning: {s:.0%} aktier (SPY) och {1 - s:.0%} statsobligationer (IEF). Återställs varje månad."


class TrendFollowing(AllocationStrategy):
    """Faber (2007): hold stocks when price is above its 10-month moving average."""

    def _signal(self, store, p):
        px = store.market_monthly["SPY"]
        sma = px.rolling(p["sma"]).mean()
        return px, sma, (px > sma)

    def weights(self, store, p):
        px, sma, on = self._signal(store, p)
        r = store.etf_returns
        w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
        w["SPY"] = on.astype(float)
        w[p["off_asset"]] = (~on).astype(float)
        w = w[sma.notna()]
        if p["off_asset"] == "IEF":
            w = w[store.market_monthly["IEF"].notna()]
        return w

    def signal_text(self, store, p):
        px, sma, on = self._signal(store, p)
        d = px.index[-1]
        diff = px.iloc[-1] / sma.iloc[-1] - 1
        state = "över" if on.iloc[-1] else "under"
        return (
            f"Per {d:%Y-%m-%d} ligger S&P 500 (SPY) {abs(diff):.1%} {state} sitt {p['sma']}-månaders glidande medelvärde "
            f"→ {'håll aktier' if on.iloc[-1] else 'gå ur till ' + ('kontanter' if p['off_asset'] == 'CASH' else 'obligationer')}."
        )


class DualMomentum(AllocationStrategy):
    """Antonacci's Global Equities Momentum (GEM)."""

    def _lookback(self, store, p):
        m = store.market_monthly
        L = p["lookback"]
        us = m["SPY"] / m["SPY"].shift(L) - 1
        intl = m["EFA"] / m["EFA"].shift(L) - 1
        rf = (1 + store.risk_free).rolling(L).apply(np.prod, raw=True) - 1
        # risk_free[t] is the return *during* t; at t the past L months are known.
        return us, intl, rf

    def weights(self, store, p):
        us, intl, rf = self._lookback(store, p)
        r = store.etf_returns
        w = pd.DataFrame(0.0, index=r.index, columns=r.columns)
        best_is_us = us >= intl
        best = us.where(best_is_us, intl)
        risk_on = best > rf
        w["SPY"] = (risk_on & best_is_us).astype(float)
        w["EFA"] = (risk_on & ~best_is_us).astype(float)
        w["AGG"] = (~risk_on).astype(float)
        ok = us.notna() & intl.notna() & rf.notna() & store.market_monthly["AGG"].notna()
        return w[ok]

    def signal_text(self, store, p):
        us, intl, rf = self._lookback(store, p)
        L = p["lookback"]
        a, b, c = us.iloc[-1], intl.iloc[-1], rf.iloc[-1]
        winner = "USA (SPY)" if a >= b else "Internationellt (EFA)"
        if max(a, b) > c:
            act = f"håll {winner}"
        else:
            act = "gå till obligationer (AGG)"
        return (
            f"Senaste {L} mån: USA {a:+.1%}, internationellt {b:+.1%}, statsskuldväxlar {c:+.1%} → {act}."
        )


class Momentum(RankStrategy):
    """Jegadeesh & Titman: buy past 12-month winners, skipping the latest month."""

    def scores(self, store, p):
        return store.momentum(12, skip=1)

    def display_columns(self, store, p):
        return [
            ("mom_12_1", "Avkastning 12–1 mån", "pct", store.momentum(12, skip=1)),
            ("mom_1", "Senaste månaden", "pct", store.momentum(1)),
            ("vol", "Volatilitet", "pct", store.volatility),
        ]


class LowVolatility(RankStrategy):
    """Low-volatility anomaly: the calmest stocks have historically delivered
    market-like returns with clearly lower risk."""

    def scores(self, store, p):
        return -store.volatility

    def display_columns(self, store, p):
        return [
            ("vol", "Volatilitet 12 mån", "pct", store.volatility),
            ("mom_12_1", "Avkastning 12–1 mån", "pct", store.momentum(12, skip=1)),
        ]


def build() -> list:
    return [
        EqualWeightUniverse(
            "ew_universe",
            "Lika vikt – hela universumet",
            "Referens",
            "Alla ~900 aktier med lika stor vikt. Rättvis jämförelse för aktiestrategierna.",
            params=[rebalance_param([1, 12], 1)],
        ),
        SixtyForty(
            "sixty_forty",
            "60/40-portföljen",
            "Klassiska",
            "Den klassiska blandportföljen: 60 % aktier, 40 % obligationer.",
            params=[Param("stock_share", "Andel aktier", [0.4, 0.6, 0.8], 0.6, ["40 %", "60 %", "80 %"])],
        ),
        TrendFollowing(
            "trend_sma",
            "Trendföljning (10-mån. medelvärde)",
            "Klassiska",
            "Äg aktier när marknaden ligger över sitt glidande medelvärde – annars kontanter.",
            params=[
                Param("sma", "Medelvärde (månader)", [6, 10, 12], 10, ["6 mån", "10 mån", "12 mån"]),
                Param("off_asset", "Placering vid sälj", ["CASH", "IEF"], "CASH", ["Kontanter", "Statsobligationer"]),
            ],
        ),
        DualMomentum(
            "dual_momentum",
            "Dual Momentum (Antonacci)",
            "Klassiska",
            "Välj starkaste av USA/internationellt – men bara om det slår räntan, annars obligationer.",
            params=[Param("lookback", "Mätperiod", [6, 12], 12, ["6 mån", "12 mån"])],
        ),
        Momentum(
            "momentum",
            "Momentum 12–1",
            "Klassiska",
            "Köp aktierna som gått bäst senaste året (exklusive sista månaden).",
            params=[n_param([10, 20, 30, 50, 100], 30), rebalance_param([1, 3], 1)],
        ),
        LowVolatility(
            "low_vol",
            "Låg volatilitet",
            "Klassiska",
            "Köp de lugnaste aktierna – historiskt nästan marknadens avkastning till lägre risk.",
            params=[n_param([30, 50, 100], 50), rebalance_param([1, 3], 3)],
        ),
    ]
