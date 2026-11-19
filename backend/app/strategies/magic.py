"""Joel Greenblatt's Magic Formula and variants.

Earnings yield  = EBIT / Enterprise value        (cheap?)
Return on capital = EBIT / (Net working capital + Net PP&E)   (good business?)
Rank all eligible companies on both, add the ranks, buy the best combined rank.
"""

from __future__ import annotations

import pandas as pd

from .. import config
from .base import Param, RankStrategy, UNIVERSE_PARAM, n_param, pct_rank, rebalance_param


class MagicBase(RankStrategy):
    min_names = 200  # wait until SEC XBRL coverage is broad (~2010-2011)

    def eligible_universe(self, store, p):
        base = super().eligible_universe(store, p)
        sectors = store.info.loc[base, "sector"]
        return base[~sectors.isin(config.MF_EXCLUDED_SECTORS)]

    def coverage(self, store, p, scores):
        # Start when enough companies have SEC fundamentals, regardless of extra filters.
        return self.mf_rank(store, p).where(store.members).notna().sum(axis=1)

    def mf_rank(self, store, p) -> pd.DataFrame:
        """Combined Magic Formula rank among *eligible* companies, as a 0..1 score (1 = best)."""
        f = store.fundamentals
        ey, roc = f["earnings_yield"], f["roc"]
        allowed = ey.columns.isin(self.eligible_universe(store, p))
        ok = ey.notna() & roc.notna() & f["mcap"].notna() & allowed & store.members
        combined = pct_rank(ey.where(ok)) + pct_rank(roc.where(ok))
        return combined.where(ok) / 2

    def display_columns(self, store, p):
        f = store.fundamentals
        return [
            ("earnings_yield", "Earnings yield (EBIT/EV)", "pct", f["earnings_yield"]),
            ("roc", "Avkastning på kapital", "pct", f["roc"]),
            ("mcap", "Börsvärde", "usd", f["mcap"]),
        ]


class MagicClassic(MagicBase):
    def scores(self, store, p):
        return self.mf_rank(store, p)


class MagicStaggered(MagicClassic):
    tranches = 4


class MagicMomentum(MagicBase):
    """Magic Formula shortlist, then pick the ones the market already rewards."""

    def scores(self, store, p):
        mf = self.mf_rank(store, p)
        shortlist = mf.rank(axis=1, ascending=False) <= p["n"] * p["shortlist"]
        mom = store.momentum(6, skip=1)
        return mom.where(shortlist & mom.notna())

    def display_columns(self, store, p):
        return [("mom_6_1", "Avkastning 6–1 mån", "pct", store.momentum(6, skip=1)), *super().display_columns(store, p)]


class AcquirersMultiple(MagicBase):
    """Value only: highest EBIT/EV (Tobias Carlisle's "Acquirer's Multiple")."""

    def scores(self, store, p):
        f = store.fundamentals
        return f["earnings_yield"].where(f["mcap"].notna())


class MagicQuality(MagicBase):
    """Magic Formula restricted to financially solid companies: low leverage and positive net income."""

    def scores(self, store, p):
        f = store.fundamentals
        solid = (f["debt_to_equity"] < p["max_de"]) & (f["roe"] > 0)
        return self.mf_rank(store, p).where(solid)

    def display_columns(self, store, p):
        f = store.fundamentals
        return [*super().display_columns(store, p), ("debt_to_equity", "Skuld / eget kapital", "x", f["debt_to_equity"])]


def build() -> list:
    return [
        MagicClassic(
            "mf_classic",
            "Magic Formula – klassisk",
            "Magic Formula",
            "Greenblatts original: köp 30 bra bolag till lågt pris, behåll ett år.",
            params=[n_param([10, 20, 30, 50], 30), rebalance_param([3, 6, 12], 12), UNIVERSE_PARAM],
        ),
        MagicStaggered(
            "mf_staggered",
            "Magic Formula – rullande trancher",
            "Magic Formula",
            "Som Greenblatt rekommenderar i boken: köp en ny fjärdedel varje kvartal.",
            params=[n_param([20, 32, 48], 32), rebalance_param([3], 3), UNIVERSE_PARAM],
        ),
        MagicMomentum(
            "mf_momentum",
            "Magic Formula + momentum",
            "Magic Formula",
            "Magic Formula-kandidater, men bara de som redan börjat stiga.",
            params=[
                n_param([20, 30], 30),
                Param("shortlist", "Kandidatlista", [2, 3, 5], 3, ["2× antal", "3× antal", "5× antal"],
                      "Hur många av de bäst rankade Magic Formula-bolagen som får tävla på momentum."),
                rebalance_param([3, 6], 3),
                UNIVERSE_PARAM,
            ],
        ),
        MagicQuality(
            "mf_quality",
            "Magic Formula – kvalitetsfilter",
            "Magic Formula",
            "Magic Formula utan högt belånade bolag och bolag med förlust.",
            params=[
                n_param([20, 30, 50], 30),
                Param("max_de", "Max skuld/eget kapital", [0.5, 1.0, 2.0], 1.0, ["0,5×", "1,0×", "2,0×"]),
                rebalance_param([3, 12], 12),
                UNIVERSE_PARAM,
            ],
        ),
        AcquirersMultiple(
            "acquirers_multiple",
            "Acquirer's Multiple (bara värde)",
            "Magic Formula",
            "Hälften av Magic Formula: bara lägst pris i förhållande till rörelseresultat.",
            params=[n_param([20, 30, 50], 30), rebalance_param([3, 12], 12), UNIVERSE_PARAM],
        ),
    ]
