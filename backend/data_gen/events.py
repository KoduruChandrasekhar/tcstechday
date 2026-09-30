"""Festival / season calendar -> daily demand multipliers per city x category.

Reads the editable ``events.csv``. Each event has a category uplift vector, a
pre-window ramp, a post-event dip and regional intensity per city. Effects are
combined additively on the *excess* over 1, so overlapping events (Navratri +
Durga Puja + Dussehra) stack without exploding.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import CATEGORIES, EVENTS_CSV
from .geography import CITY_CODES


def load_events() -> pd.DataFrame:
    ev = pd.read_csv(EVENTS_CSV, dtype=str)
    for c in ("start", "end", "peak"):
        ev[c] = pd.to_datetime(ev[c], errors="coerce").dt.date
    ev["pre_window_days"] = ev["pre_window_days"].astype(int)
    ev["post_dip"] = ev["post_dip"].astype(float)
    return ev


def event_shape(days: list[date], start: date, end: date, peak: date | None, pre: int, post_dip: float) -> np.ndarray:
    """Shape in [-post_dip, 1]: ramps up over the pre-window, peaks, then dips after the event."""
    out = np.zeros(len(days))
    d0 = days[0]
    s, e = (start - d0).days, (end - d0).days
    p = (peak - d0).days if peak is not None else None
    for k in range(len(days)):
        if s - pre <= k < s and pre > 0:
            frac = (k - (s - pre)) / pre
            out[k] = 0.7 * frac ** 1.5
        elif s <= k <= e:
            if p is None:
                out[k] = 1.0
            elif k <= p:
                out[k] = 0.7 + 0.3 * ((k - s) / (p - s) if p > s else 1.0)
            else:
                out[k] = 1.0 - 0.4 * ((k - p) / (e - p) if e > p else 1.0)
        elif e < k <= e + 10 and post_dip > 0:
            out[k] = -post_dip * (1 - (k - e) / 10)
    return out


def build_calendar(days: list[date], events: pd.DataFrame):
    """Returns (season_mult[D,12city,12cat], festival_excess[D,12,12], per-event truth rows)."""
    D, NC, NK = len(days), len(CITY_CODES), len(CATEGORIES)
    season_ex = np.zeros((D, NC, NK))
    fest_ex = np.zeros((D, NC, NK))
    truth = []
    for r in events.itertuples():
        upl = json.loads(r.category_uplift)
        reg = json.loads(r.regional_intensity)
        inten = np.array([reg.get(c, reg.get("default", 1.0)) for c in CITY_CODES])
        u = np.array([upl.get(k, 1.0) for k in CATEGORIES]) - 1.0
        shape = event_shape(days, r.start, r.end, r.peak if (isinstance(r.peak, date) and not pd.isna(r.peak)) else None, r.pre_window_days, r.post_dip)
        if not shape.any():
            continue
        # post-dip should dampen, not invert, categories that fell during the event
        contrib = np.where(shape[:, None, None] >= 0,
                           shape[:, None, None] * inten[None, :, None] * u[None, None, :],
                           shape[:, None, None] * inten[None, :, None] * np.abs(u)[None, None, :])
        if r.kind == "season":
            season_ex += contrib
        else:
            fest_ex += contrib
        for ci, cc in enumerate(CITY_CODES):
            for ki, k in enumerate(CATEGORIES):
                if inten[ci] > 0 and abs(u[ki]) > 1e-9:
                    truth.append(dict(event_id=r.event_id, city_code=cc, category=k,
                                      peak_multiplier=round(1 + inten[ci] * u[ki], 4),
                                      intensity=inten[ci], category_uplift=upl.get(k, 1.0), kind=r.kind))
    season_mult = np.clip(1.0 + season_ex, 0.08, None)
    payday = np.array([1.12 if d.day <= 5 else 1.0 for d in days])
    return season_mult, fest_ex, payday, pd.DataFrame(truth)


def dow_weights(days: list[date], online_profile_sun_first: list[float]):
    """Day-of-week purchase weights: stores peak at weekends; online follows the Instacart profile."""
    store = {0: 0.85, 1: 0.82, 2: 0.86, 3: 0.9, 4: 1.0, 5: 1.25, 6: 1.32}
    online_sun_first = np.array(online_profile_sun_first) / np.mean(online_profile_sun_first)
    # python weekday(): Mon=0 ... Sun=6 ; instacart order_dow 0 is taken as Sunday
    online = {wd: online_sun_first[(wd + 1) % 7] for wd in range(7)}
    return np.array([store[d.weekday()] for d in days]), np.array([online[d.weekday()] for d in days])
