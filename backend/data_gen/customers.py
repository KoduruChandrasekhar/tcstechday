"""Synthetic customer population with continuous latent behavioural traits.

Nothing here is a persona label. Traits are drawn jointly through a Gaussian
copula so that they co-vary plausibly (price-sensitive people also respond more
to promotions and prefer lower tiers, heavy buyers churn less, ...). The only
discrete hidden label is ``uplift_type`` (PLAN §6.3), derived from the traits.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from .config import CATEGORIES, HISTORY_START, WARMUP_DAYS, HISTORY_END
from .geography import CITY_CODES

AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_P = [0.16, 0.36, 0.25, 0.14, 0.09]
BASE_ALPHA = dict(TV=1.0, PHN=1.6, LAP=1.0, TAB=0.45, AC=0.7, REF=0.6, WM=0.55, KIT=0.8, AUD=1.3, WEA=0.8, GAM=0.35, ACC=1.6)
AGE_TILT = {
    "18-24": dict(PHN=1.4, LAP=1.3, AUD=1.5, WEA=1.3, GAM=2.0, ACC=1.4, TAB=1.1, TV=0.5, AC=0.4, REF=0.3, WM=0.3, KIT=0.5),
    "25-34": dict(PHN=1.2, LAP=1.2, AUD=1.1, WEA=1.2, GAM=1.2, TV=0.9, AC=0.9, REF=0.8, WM=0.8, KIT=0.9),
    "35-44": dict(TV=1.3, AC=1.2, REF=1.3, WM=1.3, KIT=1.2, PHN=0.9, GAM=0.8, TAB=1.2),
    "45-54": dict(TV=1.3, AC=1.3, REF=1.4, WM=1.3, KIT=1.3, PHN=0.8, LAP=0.8, GAM=0.4, AUD=0.7, WEA=0.8),
    "55+": dict(TV=1.2, AC=1.2, REF=1.3, WM=1.2, KIT=1.4, PHN=0.8, LAP=0.6, GAM=0.2, AUD=0.6, WEA=0.7, TAB=1.1),
}
# latent order: price_sens, promo_resp, tier_pref, base_rate, churn, online
CORR = np.array([
    [1.00, 0.45, -0.50, -0.05, 0.15, 0.05],
    [0.45, 1.00, -0.15, 0.05, 0.05, 0.10],
    [-0.50, -0.15, 1.00, 0.25, -0.10, 0.15],
    [-0.05, 0.05, 0.25, 1.00, -0.35, 0.10],
    [0.15, 0.05, -0.10, -0.35, 1.00, 0.00],
    [0.05, 0.10, 0.15, 0.10, 0.00, 1.00],
])
UPLIFT_TYPES = ["persuadable", "sure_thing", "lost_cause", "sleeping_dog"]
DURABLE = {"TV", "PHN", "LAP", "TAB", "AC", "REF", "WM", "KIT", "GAM"}


def build_customers(rng: np.random.Generator, stores: pd.DataFrame, cities: pd.DataFrame, brands: list[str],
                    n: int, rate_theta: float):
    # ------------------------------------------------ geography
    st = stores.copy()
    st["w"] = st["attractiveness"] * st["city_code"].map(cities.set_index("city_code")["market_size_index"])
    store_idx = rng.choice(len(st), size=n, p=(st["w"] / st["w"].sum()).values)
    home_store = st["store_id"].values[store_idx]
    city = st["city_code"].values[store_idx]
    city_i = np.array([CITY_CODES.index(c) for c in city])
    cinfo = cities.set_index("city_code")

    age = rng.choice(len(AGE_BANDS), size=n, p=AGE_P)

    # ------------------------------------------------ copula traits
    z = rng.multivariate_normal(np.zeros(6), CORR, size=n)
    u = stats.norm.cdf(z)
    price_sens = stats.beta.ppf(u[:, 0], 2, 3)
    promo_resp = stats.beta.ppf(u[:, 1], 2, 4)
    prem = cinfo.loc[city, "premium_index"].values
    age_tier = np.array([-0.08, 0.0, 0.06, 0.06, 0.02])[age]
    tier_pref = np.clip(stats.beta.ppf(u[:, 2], 2.2, 2.2) + 0.35 * (prem - 1.0) + age_tier, 0.01, 0.99)
    base_rate = stats.gamma.ppf(u[:, 3], a=2.0, scale=rate_theta)
    churn = stats.beta.ppf(u[:, 4], 1.5, 20)
    onl = cinfo.loc[city, "online_index"].values
    age_onl = np.array([0.12, 0.08, 0.0, -0.08, -0.15])[age]
    online_prop = np.clip(stats.beta.ppf(u[:, 5], 2, 2.5) * onl + age_onl, 0.02, 0.97)

    # category affinity: Dirichlet skewed by age band
    alpha = np.array([[BASE_ALPHA[c] * AGE_TILT[AGE_BANDS[a]].get(c, 1.0) for c in CATEGORIES] for a in range(len(AGE_BANDS))])
    aff = np.zeros((n, len(CATEGORIES)))
    for a in range(len(AGE_BANDS)):
        m = age == a
        aff[m] = rng.dirichlet(alpha[a] * 1.2, size=int(m.sum()))
    fatigue_k = rng.uniform(0.08, 0.25, n)
    fest_aff = np.exp(rng.normal(0, 0.35, n))
    fest_aff /= fest_aff.mean()
    browse = np.exp(rng.normal(0, 0.5, n))
    nonprice_resp = rng.beta(2, 3, n)
    retention_sens = rng.beta(2, 5, n)
    brand_util = rng.normal(0, 0.6, (n, len(brands)))

    # ------------------------------------------------ tenure / join dates
    day0 = HISTORY_START - timedelta(days=WARMUP_DAYS)
    pre_existing = rng.random(n) < 0.58
    joined = np.empty(n, dtype=object)
    old_span = (day0 - date(2017, 1, 1)).days
    new_span = (HISTORY_END - timedelta(days=10) - day0).days
    old_days = (old_span * rng.beta(1.6, 1.0, n)).astype(int)
    new_days = rng.integers(0, new_span, n)
    for i in range(n):
        joined[i] = (date(2017, 1, 1) + timedelta(days=int(old_days[i]))) if pre_existing[i] else (day0 + timedelta(days=int(new_days[i])))
    tenure_years = np.array([max(0.05, (HISTORY_END - j).days / 365.0) for j in joined])

    # loyalty tier from latent value (Prometheus Circle); elite = top 3%
    value = base_rate * (0.6 + tier_pref) * np.sqrt(tenure_years) * np.exp(rng.normal(0, 0.25, n))
    q = np.quantile(value, [0.68, 0.88, 0.97])
    tier = np.where(value >= q[2], "elite", np.where(value >= q[1], "gold", np.where(value >= q[0], "silver", "none")))
    nonprice_resp = np.clip(nonprice_resp + np.where(np.isin(tier, ["elite", "gold"]), 0.2, 0.0), 0, 1)

    # ------------------------------------------------ hidden uplift type (quota-based on trait scores)
    zs = (z - z.mean(0)) / z.std(0)
    noise = rng.normal(0, 0.7, (n, 4))
    elite = tier == "elite"
    sd_score = -1.0 * zs[:, 1] + 0.3 * zs[:, 2] + noise[:, 0]
    st_score = 1.0 * zs[:, 3] - 0.6 * zs[:, 0] + 0.3 * zs[:, 2] + 2.2 * elite + noise[:, 1]
    pe_score = 1.0 * zs[:, 1] + 0.6 * zs[:, 0] + noise[:, 2]
    utype = np.full(n, "lost_cause", dtype=object)
    free = np.ones(n, bool)
    for label, score, share in (("sleeping_dog", sd_score, 0.05), ("sure_thing", st_score, 0.22), ("persuadable", pe_score, 0.28)):
        k = int(round(share * n))
        cand = np.where(free)[0]
        pick = cand[np.argsort(-score[cand], kind="stable")[:k]]
        utype[pick] = label
        free[pick] = False

    # ------------------------------------------------ consent / channels (observed)
    consent = rng.random(n) < 0.88
    wa = consent & (rng.random(n) < 0.73)
    dnd = rng.random(n) < 0.06
    app_user = rng.random(n) < np.clip(0.15 + 0.75 * online_prop, 0, 0.95)
    email_ok = consent & (rng.random(n) < 0.9)

    cust_ids = np.array([f"PRM-C-{i:06d}" for i in rng.permutation(np.arange(1, n + 1))])
    df = pd.DataFrame(dict(
        customer_id=cust_ids, home_city=cinfo.loc[city, "city"].values, home_city_code=city, home_store_id=home_store,
        age_band=np.array(AGE_BANDS)[age], loyalty_tier=tier, joined_on=joined,
        marketing_consent=consent, whatsapp_opt_in=wa, email_opt_in=email_ok, app_user=app_user, dnd=dnd,
    ))
    truth = pd.DataFrame(dict(
        customer_id=cust_ids, price_sensitivity=price_sens, promo_responsiveness=promo_resp, tier_preference=tier_pref,
        base_purchase_rate=base_rate, churn_hazard=churn, online_propensity=online_prop, fatigue_k=fatigue_k,
        festival_affinity=fest_aff, browse_intensity=browse, nonprice_responsiveness=nonprice_resp,
        retention_sensitivity=retention_sens, uplift_type=utype,
    ))
    for k, c in enumerate(CATEGORIES):
        truth[f"affinity_{c}"] = aff[:, k]
    arrays = dict(city_i=city_i, age=age, price_sens=price_sens, promo_resp=promo_resp, tier_pref=tier_pref,
                  base_rate=base_rate, churn=churn, online=online_prop, aff=aff, fatigue_k=fatigue_k,
                  fest_aff=fest_aff, browse=browse, nonprice=nonprice_resp, ret_sens=retention_sens,
                  brand_util=brand_util, utype=np.array([UPLIFT_TYPES.index(t) for t in utype]),
                  elite=elite, tier=tier, joined_day=np.array([(j - day0).days for j in joined]),
                  store_idx=store_idx, consent=consent.copy(), wa=wa, dnd=dnd, app=app_user, email=email_ok)
    return df, truth, arrays
