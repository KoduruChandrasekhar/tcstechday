"""Uplift learners and their benchmark.

Shared by the engine (training the production model) and the benchmark below, so both see identical features.

    cd backend && python -m app.uplift        # benchmark -> prints a table and writes docs/UPLIFT_BENCHMARK.md

The benchmark scores every learner out-of-fold (5-fold cross-fitting, stratified by group x outcome), so no row is
scored by a model that saw it, then compares them on the observed treated-vs-control data:
  * Qini coefficient  area between the model's Qini curve and random targeting (higher is better)
  * top-30% uplift    observed T-C conversion gap among the 30% with the highest predicted uplift, with a bootstrap 90% CI
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = ["orders_24m", "log_spend", "recency", "web_active_days_90d", "promo_order_share", "exposures_60d",
            "tier", "app_user"]
SEED = 42


def add_features(cu: pd.DataFrame) -> pd.DataFrame:
    """Model features on the customer table (expects customers merged with customer_behavior_summary)."""
    cu["log_spend"] = np.log1p(cu["spend_24m"].fillna(0))
    cu["recency"] = np.minimum(cu["days_since_last_order"], 730) / 365
    cu["tier"] = cu["loyalty_tier"].map({"none": 0, "silver": 1, "gold": 2, "elite": 3}).fillna(0)
    cu["app_user"] = cu["app_user"].astype(float)
    return cu


def training_frame(cu: pd.DataFrame, ex: pd.DataFrame) -> pd.DataFrame:
    """One row per campaign exposure with customer features, group (T/C) and the 30-day conversion label."""
    X = ex.merge(cu[["customer_id", "segment"] + FEATURES], on="customer_id").dropna(subset=["converted_30d"])
    X["converted_30d"] = X.converted_30d.astype(int)
    return X.reset_index(drop=True)


# ---------------------------------------------------------------- learners
def _lr():
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(max_iter=500, C=0.5)


def _xgb():
    from xgboost import XGBClassifier
    # shallow, regularised trees: the control arm is small (~17k rows, few conversions)
    return XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                         min_child_weight=20, reg_lambda=5.0, eval_metric="logloss", random_state=SEED, n_jobs=4)


class TLearner:
    """Two outcome models, one per arm; uplift = P(buy | treated) - P(buy | control)."""

    def __init__(self, make):
        self.make = make

    def fit(self, X: pd.DataFrame):
        T, C = X[X.group == "T"], X[X.group == "C"]
        self.mt = self.make().fit(T[FEATURES], T.converted_30d)
        self.mc = self.make().fit(C[FEATURES], C.converted_30d)
        return self

    def predict(self, F: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """(p_treat, p_ctrl) for each row of F."""
        return self.mt.predict_proba(F[FEATURES])[:, 1], self.mc.predict_proba(F[FEATURES])[:, 1]


class SLearner:
    """One outcome model with treatment as a feature; uplift = f(x, T=1) - f(x, T=0)."""

    def __init__(self, make):
        self.make = make

    def fit(self, X: pd.DataFrame):
        F = X[FEATURES].assign(treated=(X.group == "T").astype(float))
        self.m = self.make().fit(F, X.converted_30d)
        return self

    def predict(self, F: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        F = F[FEATURES]
        return (self.m.predict_proba(F.assign(treated=1.0))[:, 1], self.m.predict_proba(F.assign(treated=0.0))[:, 1])


LEARNERS = {
    "T-learner · logistic regression (current)": lambda: TLearner(_lr),
    "T-learner · XGBoost": lambda: TLearner(_xgb),
    "S-learner · XGBoost": lambda: SLearner(_xgb),
}


# ---------------------------------------------------------------- metrics
def qini_curve(y: np.ndarray, t: np.ndarray, score: np.ndarray, bins: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative incremental buyers when targeting the top fraction by score, as a share of the population."""
    o = np.argsort(-score, kind="stable")
    y, t = y[o], t[o]
    yt, nt = np.cumsum(y * t), np.cumsum(t)
    yc, nc = np.cumsum(y * (1 - t)), np.cumsum(1 - t)
    q = yt - yc * np.divide(nt, nc, out=np.zeros(len(y)), where=nc > 0)
    idx = np.linspace(0, len(y) - 1, bins).astype(int)
    return np.r_[0, (idx + 1) / len(y)], np.r_[0, q[idx] / len(y)]


def qini_coef(y, t, score) -> float:
    x, q = qini_curve(y, t, score)
    return float(np.trapezoid(q - x * q[-1], x))


def top_uplift(y, t, score, frac: float = 0.3) -> float:
    top = score >= np.quantile(score, 1 - frac)
    return float(y[top & (t == 1)].mean() - y[top & (t == 0)].mean())


def bootstrap_ci(y, t, score, n: int = 200, frac: float = 0.3) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        vals.append(top_uplift(y[i], t[i], score[i], frac))
    return float(np.percentile(vals, 5)), float(np.percentile(vals, 95))


def out_of_fold(make, X: pd.DataFrame, folds: int = 5) -> np.ndarray:
    from sklearn.model_selection import StratifiedKFold
    strata = X.group.astype(str) + X.converted_30d.astype(str)
    pred = np.zeros(len(X))
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=SEED).split(X, strata):
        pt, pc = make().fit(X.iloc[tr]).predict(X.iloc[te])
        pred[te] = pt - pc
    return pred


def benchmark(X: pd.DataFrame) -> pd.DataFrame:
    y, t = X.converted_30d.to_numpy(), (X.group == "T").to_numpy().astype(int)
    rows = []
    for name, make in LEARNERS.items():
        s = out_of_fold(make, X)
        lo, hi = bootstrap_ci(y, t, s)
        rest = s < np.quantile(s, 0.7)
        rows.append({"model": name, "qini": qini_coef(y, t, s), "top30_pts": top_uplift(y, t, s) * 100,
                     "top30_ci": (lo * 100, hi * 100),
                     "rest_pts": (y[rest & (t == 1)].mean() - y[rest & (t == 0)].mean()) * 100})
    return pd.DataFrame(rows)


def _load() -> pd.DataFrame:
    from .engine import _r, _segment
    cu = _r("customers").merge(_r("customer_behavior_summary"), on="customer_id", how="left")
    cu[["orders_24m", "promo_order_share", "web_active_days_90d", "exposures_60d"]] = cu[
        ["orders_24m", "promo_order_share", "web_active_days_90d", "exposures_60d"]].fillna(0)
    cu["days_since_last_order"] = cu["days_since_last_order"].fillna(9999)
    cu["dnd_or_unsub"] = cu["dnd"] | cu["unsubscribed_on"].notna() | ~cu["marketing_consent"]
    cu["segment"] = [_segment(r) for r in cu.itertuples()]
    return training_frame(add_features(cu), _r("exposures"))


def report(res: pd.DataFrame, X: pd.DataFrame) -> str:
    y, t = X.converted_30d, X.group == "T"
    lines = ["# Uplift model benchmark", "",
             f"Data: {len(X):,} campaign exposures ({int(t.sum()):,} treated, {int((~t).sum()):,} holdout control); "
             f"overall observed uplift {(y[t].mean() - y[~t].mean()) * 100:.2f} pts (30-day conversion).",
             "Every score is out-of-fold (5-fold cross-fitting), so no exposure is scored by a model trained on it.", "",
             "| Model | Qini coefficient | Top-30% uplift (pts) | 90% CI | Rest (pts) |", "|---|---|---|---|---|"]
    for r in res.itertuples():
        lines.append(f"| {r.model} | {r.qini * 1000:.3f} ×10⁻³ | {r.top30_pts:.2f} | {r.top30_ci[0]:.2f} – {r.top30_ci[1]:.2f} "
                     f"| {r.rest_pts:.2f} |")
    best = res.loc[res.qini.idxmax(), "model"]
    lines += ["", f"Best Qini: **{best}**.", "",
              "Qini coefficient = area between the model's cumulative-incremental-buyers curve and random targeting, "
              "per customer. Top-30% uplift = observed treated-minus-control conversion among the 30% the model ranks most "
              "persuadable. Overlapping CIs mean the difference is not conclusive at this sample size.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    X = _load()
    res = benchmark(X)
    md = report(res, X)
    print(md)
    out = Path(__file__).resolve().parents[2] / "docs" / "UPLIFT_BENCHMARK.md"
    out.write_text(md, encoding="utf-8")
    print(f"written {out}")
