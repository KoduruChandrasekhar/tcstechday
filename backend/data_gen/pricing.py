"""Open (non-targeted) price actions: category markdowns, SKU deals and EOL clearance.

These are what the *whole market* sees at the shelf/website. They are the
price variation from which category elasticities can later be estimated:
local city-week markdowns vary independently of the national calendar.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .config import CATEGORIES
from .geography import CITY_CODES
from . import stories


def build_price_actions(rng, dates, events: pd.DataFrame, sku: dict, sku_ids: list[str], launch_day, eol_day):
    DX, NC, K, P = len(dates), len(CITY_CODES), len(CATEGORIES), len(sku_ids)
    md = np.zeros((DX, NC, K))
    deal = np.zeros((DX, P))
    clear = np.zeros((DX, P))
    d0 = dates[0]
    idx_of = {d: k for k, d in enumerate(dates)}
    # --- local city x category x week promotions (merchandiser discretion)
    week_starts = [k for k, d in enumerate(dates) if d.weekday() == 0]
    rows = []
    for w in week_starts:
        span = slice(w, min(w + 7, DX))
        hit = rng.random((NC, K)) < 0.09
        depth = np.round(rng.uniform(0.04, 0.10, (NC, K)), 3)
        md[span] = np.maximum(md[span], np.where(hit, depth, 0.0)[None])
    # --- retailer sale windows: national depth per category + city noise
    for r in events.itertuples():
        if r.kind != "retailer_sale" and not r.event_id.startswith("EV-DIW"):
            continue
        s, e = idx_of.get(r.start), idx_of.get(r.end)
        if s is None or e is None:
            continue
        if r.kind == "retailer_sale":
            base = rng.uniform(0.06, 0.14, K)
            depth = np.clip(base[None, :] + rng.normal(0, 0.015, (NC, K)), 0.03, 0.2)
        else:  # Diwali: some cities add festive markdowns on big-ticket categories
            depth = np.where(rng.random((NC, K)) < 0.5, rng.uniform(0.03, 0.08, (NC, K)), 0.0)
        md[s:e + 1] = np.maximum(md[s:e + 1], depth[None])
    # --- deal of the week (national, single SKU)
    phys = np.arange(P)
    for w in week_starts:
        live = phys[(launch_day <= w) & (eol_day > w)]
        if len(live) == 0:
            continue
        pick = rng.choice(live, size=min(3, len(live)), replace=False)
        for p in pick:
            deal[w:w + 7, p] = round(float(rng.uniform(0.08, 0.20)), 3)
    p50 = sku_ids.index("TV-AUR-50U5")
    for wk in stories.S5_DEAL_WEEKS:
        k = idx_of[wk]
        deal[k:k + 7, p50] = round(float(rng.uniform(0.15, 0.18)), 3)
    # --- clearance of end-of-life models (except the S2 laptop whose price merchandising held)
    held = sku_ids.index(stories.S2_SKU)
    for p in phys:
        e = eol_day[p]
        if e >= DX:
            continue
        t = np.arange(max(e, 0), DX)
        if p == held:
            clear[t, p] = 0.04
        else:
            clear[t, p] = np.minimum(0.25, 0.08 + 0.17 * (t - e) / 90.0)
    return md, deal, clear


def markdown_calendar_frame(md, deal, clear, dates, sku_ids, h0):
    """Observed weekly price-action calendar (what merchandising actually ran)."""
    rows = []
    NC, K = md.shape[1], md.shape[2]
    for k in range(h0, len(dates)):
        d = dates[k]
        if d.weekday() != 0 and k != h0:
            continue
        for ci in range(NC):
            for ki in range(K):
                v = md[k, ci, ki]
                if v > 0:
                    rows.append(dict(week_start=d, scope="city_category", city_code=CITY_CODES[ci], category=CATEGORIES[ki],
                                     sku_id=None, action="markdown", depth_pct=round(float(v), 3)))
        for p in np.nonzero(deal[k] > 0)[0]:
            rows.append(dict(week_start=d, scope="national_sku", city_code=None, category=None, sku_id=sku_ids[p],
                             action="deal_of_week", depth_pct=round(float(deal[k, p]), 3)))
        for p in np.nonzero(clear[k] > 0)[0]:
            rows.append(dict(week_start=d, scope="national_sku", city_code=None, category=None, sku_id=sku_ids[p],
                             action="clearance", depth_pct=round(float(clear[k, p]), 3)))
    return pd.DataFrame(rows)
