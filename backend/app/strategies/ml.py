"""Machine-learning stock ranking with strict walk-forward training.

Every month each stock is described by 15 features (momentum, volatility, value,
quality, size...). Features are converted to cross-sectional percentile ranks, so
the model learns *relative* patterns ("cheaper than peers") that are stable over
time rather than absolute levels. The target is next month's return rank.

Walk-forward: once a year the model is retrained on everything known up to that
date (labels require one more month, so the last month is excluded) and used
for the following 12 months. A prediction never uses data from its own future.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge

from .. import config
from ..data.store import Store
from .base import RankStrategy, UNIVERSE_PARAM, n_param, rebalance_param

FEATURES = {
    "mom_1": "Avkastning senaste månaden",
    "mom_3": "Avkastning 3 mån",
    "mom_6_1": "Avkastning 6–1 mån",
    "mom_12_1": "Avkastning 12–1 mån",
    "vol": "Volatilitet 12 mån",
    "dist_high": "Avstånd till 52-veckorshögsta",
    "size": "Börsvärde (storlek)",
    "earnings_yield": "Earnings yield (EBIT/EV)",
    "roc": "Avkastning på kapital (ROC)",
    "roe": "Avkastning på eget kapital (ROE)",
    "gp_assets": "Bruttovinst / tillgångar",
    "book_to_market": "Eget kapital / börsvärde",
    "pe_yield": "Vinst / börsvärde (E/P)",
    "debt_to_equity": "Skuld / eget kapital",
    "asset_growth": "Tillväxt i tillgångar",
}

MIN_TRAIN_MONTHS = 60
RETRAIN_EVERY = 12


def feature_panels(store: Store) -> dict[str, pd.DataFrame]:
    f = store.fundamentals
    return {
        "mom_1": store.momentum(1),
        "mom_3": store.momentum(3),
        "mom_6_1": store.momentum(6, skip=1),
        "mom_12_1": store.momentum(12, skip=1),
        "vol": store.volatility,
        "dist_high": store.close / store.high_52w - 1,
        "size": np.log(f["mcap"]),
        "earnings_yield": f["earnings_yield"],
        "roc": f["roc"],
        "roe": f["roe"],
        "gp_assets": f["gp_assets"],
        "book_to_market": f["book_to_market"],
        "pe_yield": f["pe_yield"],
        "debt_to_equity": f["debt_to_equity"],
        "asset_growth": f["asset_growth"],
    }


def build_dataset(store: Store) -> pd.DataFrame:
    """Long table: (date, ticker) -> ranked features + target (next-month return rank)."""
    panels = feature_panels(store)
    member = store.members
    cols = {}
    for name, panel in panels.items():
        # Rank only among stocks that were in the index at the time.
        cols[name] = panel.where(member).rank(axis=1, pct=True).stack(future_stack=True)
    fwd = store.returns.shift(-1).where(member)
    cols["target"] = fwd.rank(axis=1, pct=True).stack(future_stack=True)
    cols["fwd_return"] = fwd.stack(future_stack=True)
    df = pd.DataFrame(cols)
    df.index.names = ["date", "ticker"]
    # Must have a price and at least a year of history to be considered.
    df = df[df["mom_12_1"].notna()]
    return df


@dataclass
class MLResult:
    scores: pd.DataFrame  # dates x tickers
    ic: pd.Series  # monthly Spearman information coefficient
    importance: dict[str, float]
    trained_until: str
    n_models: int
    n_rows: int


def _make_model(kind: str):
    if kind == "gbm":
        return HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=400,
            l2_regularization=1.0, random_state=0,
        )
    return Ridge(alpha=50.0)


def _prep(X: pd.DataFrame, kind: str) -> np.ndarray:
    # Ridge needs complete data: a missing rank is set to the cross-sectional median.
    return X.to_numpy() if kind == "gbm" else X.fillna(0.5).to_numpy() - 0.5


def walk_forward(store: Store, kind: str) -> MLResult:
    data = build_dataset(store)
    feats = list(FEATURES)
    dates = store.dates
    preds = []
    first_label_date = data.index.get_level_values("date").min()
    start = dates.get_loc(first_label_date) + MIN_TRAIN_MONTHS
    model = None
    n_models = 0
    train_X = None
    for i in range(start, len(dates), RETRAIN_EVERY):
        cutoff = dates[i]
        # Labels for month t need the return of t+1 -> train only on t < cutoff.
        train = data[(data.index.get_level_values("date") < cutoff) & data["target"].notna()]
        # Fundamentals only exist from 2009: early models use the features that have data.
        used = [f for f in feats if train[f].nunique() >= 2]
        model = _make_model(kind)
        train_X = train[used]
        model.fit(_prep(train_X, kind), train["target"].to_numpy())
        n_models += 1
        block_dates = dates[i : i + RETRAIN_EVERY]
        block = data[data.index.get_level_values("date").isin(block_dates)]
        if not block.empty:
            preds.append(pd.Series(model.predict(_prep(block[used], kind)), index=block.index))
    pred = pd.concat(preds)
    scores = pred.unstack("ticker").reindex(columns=store.tickers)

    # Information coefficient: rank correlation between prediction and realised next-month return.
    joined = pd.DataFrame({"pred": pred, "fwd": data.loc[pred.index, "fwd_return"]}).dropna()
    ic = joined.groupby(level="date").apply(lambda g: g["pred"].rank().corr(g["fwd"].rank()) if len(g) > 20 else np.nan)

    # Feature importance of the latest model.
    if kind == "gbm":
        sample = train_X.sample(min(30_000, len(train_X)), random_state=0)
        y = data.loc[sample.index, "target"].to_numpy()
        pi = permutation_importance(model, _prep(sample, kind), y, n_repeats=3, random_state=0, scoring="r2")
        imp = pi.importances_mean
    else:
        imp = model.coef_
    importance = {f: float(v) for f, v in zip(used, imp)}
    return MLResult(
        scores=scores,
        ic=ic.dropna(),
        importance=importance,
        trained_until=dates[min(len(dates) - 1, start + (n_models - 1) * RETRAIN_EVERY)].strftime("%Y-%m-%d"),
        n_models=n_models,
        n_rows=int(len(data)),
    )


# ---------------------------------------------------------------------------
# Disk cache (training takes a minute or two)
# ---------------------------------------------------------------------------

def _cache_paths(kind: str):
    return config.CACHE_DIR / f"ml_{kind}_scores.parquet", config.CACHE_DIR / f"ml_{kind}_meta.json"


def _data_stamp(store: Store) -> str:
    return f"{store.last_date:%Y-%m-%d}|{len(store.tickers)}|v3-pit"


_memory: dict[str, MLResult] = {}


def get_ml(store: Store, kind: str, force: bool = False) -> MLResult:
    stamp = _data_stamp(store)
    if not force and kind in _memory and getattr(_memory[kind], "_stamp", None) == stamp:
        return _memory[kind]
    scores_path, meta_path = _cache_paths(kind)
    if not force and scores_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("stamp") == stamp:
            scores = pd.read_parquet(scores_path)
            res = MLResult(
                scores=scores,
                ic=pd.Series(meta["ic"]["values"], index=pd.to_datetime(meta["ic"]["dates"])),
                importance=meta["importance"],
                trained_until=meta["trained_until"],
                n_models=meta["n_models"],
                n_rows=meta["n_rows"],
            )
            res._stamp = stamp
            _memory[kind] = res
            return res
    res = walk_forward(store, kind)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    res.scores.to_parquet(scores_path)
    meta_path.write_text(
        json.dumps(
            {
                "stamp": stamp,
                "ic": {"dates": [d.strftime("%Y-%m-%d") for d in res.ic.index], "values": res.ic.round(5).tolist()},
                "importance": res.importance,
                "trained_until": res.trained_until,
                "n_models": res.n_models,
                "n_rows": res.n_rows,
            }
        ),
        encoding="utf-8",
    )
    res._stamp = stamp
    _memory[kind] = res
    return res


class MLStrategy(RankStrategy):
    model_kind = "gbm"
    min_names = 50

    def scores(self, store, p):
        return get_ml(store, self.model_kind).scores.reindex(index=store.dates)

    def display_columns(self, store, p):
        f = store.fundamentals
        return [
            ("mom_12_1", "Avkastning 12–1 mån", "pct", store.momentum(12, skip=1)),
            ("vol", "Volatilitet", "pct", store.volatility),
            ("earnings_yield", "Earnings yield", "pct", f["earnings_yield"]),
        ]

    def diagnostics(self, store, p):
        res = get_ml(store, self.model_kind)
        ic = res.ic
        imp = sorted(res.importance.items(), key=lambda kv: -abs(kv[1]))
        yearly = ic.groupby(ic.index.year).mean()
        return {
            "model": "Gradient boosting (HistGradientBoostingRegressor)" if self.model_kind == "gbm" else "Ridge-regression (linjär)",
            "importance_kind": "Permutationsbetydelse (minskning i R² när variabeln blandas om)" if self.model_kind == "gbm" else "Koefficient (rankskala, + = högre rank ger högre förväntad avkastning)",
            "importance": [{"feature": k, "label": FEATURES[k], "value": v} for k, v in imp],
            "ic": {
                "dates": [d.strftime("%Y-%m-%d") for d in ic.index],
                "values": ic.round(4).tolist(),
                "mean": float(ic.mean()),
                "positive_share": float((ic > 0).mean()),
                "t_stat": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 2 else None,
                "yearly": {str(k): float(v) for k, v in yearly.items()},
            },
            "trained_until": res.trained_until,
            "n_models": res.n_models,
            "n_rows": res.n_rows,
        }


class GBMStrategy(MLStrategy):
    model_kind = "gbm"


class RidgeStrategy(MLStrategy):
    model_kind = "ridge"


def build() -> list:
    return [
        GBMStrategy(
            "ml_gbm",
            "ML: Gradient boosting",
            "Maskininlärning",
            "Beslutsträd som lär sig vilka kombinationer av 15 nyckeltal som förutsett nästa månads vinnare.",
            params=[n_param([20, 30, 50], 30), rebalance_param([1, 3], 1), UNIVERSE_PARAM],
            heavy=True,
        ),
        RidgeStrategy(
            "ml_ridge",
            "ML: Linjär modell (Ridge)",
            "Maskininlärning",
            "En regulariserad linjär modell som väger ihop samma 15 nyckeltal – enkel och genomskinlig.",
            params=[n_param([20, 30, 50], 30), rebalance_param([1, 3], 1), UNIVERSE_PARAM],
            heavy=True,
        ),
    ]
