"""Causal world simulator for the Prometheus digital twin (PLAN §6.4).

Day-by-day loop (90 warm-up days + 730 history days), vectorised over the
25,000 customers x 12 categories:

  latent traits -> category intent (season x festival x replacement-due x complements x story)
      -> shopping journeys (web intent leads purchase by 3-21 days)
      -> conversion (open markdowns via true elasticity, payday, targeted offers, fatigue)
      -> channel & store -> nested-logit SKU choice (cannibalisation) -> stock check
      -> order + attach (services / accessories) -> inventory depletion -> replenishment
      -> installation / ship-from-store capacity -> returns / reviews -> lifecycle (churn, reactivation)

Only observed facts are written to data/synthetic; hidden parameters go to data/_truth.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import stories
from .campaigns_history import build_campaign_plan, METRO
from .catalog import build_catalog, build_relationships, INSTALL_SERVICE
from .config import (CATEGORIES, CAT_INDEX, HISTORY_START, HISTORY_END, WARMUP_DAYS, FORWARD_DAYS, N_CUSTOMERS,
                     REFERENCE_STATS_PATH)
from .customers import build_customers, UPLIFT_TYPES, AGE_BANDS
from .events import load_events, build_calendar, dow_weights
from .geography import build_geography, CITY_CODES, CITY_INDEX, store_distance_matrix, haversine_km
from .inventory_sim import Inventory
from .pricing import build_price_actions

K = len(CATEGORIES)
ELASTICITY = dict(TV=2.2, PHN=1.6, LAP=1.8, TAB=1.7, AC=2.4, REF=2.0, WM=2.0, KIT=1.5, AUD=1.4, WEA=1.5, GAM=1.3, ACC=1.2)
EPS = np.array([ELASTICITY[c] for c in CATEGORIES])
CONV0 = np.array([0.5 if c == "ACC" else 0.4 for c in CATEGORIES])
CAT_ONLINE = np.array([dict(TV=0.6, PHN=1.2, LAP=1.0, TAB=1.1, AC=0.5, REF=0.5, WM=0.5, KIT=0.9, AUD=1.2, WEA=1.2, GAM=1.1, ACC=1.1)[c] for c in CATEGORIES])
REP_FLOOR = np.array([dict(TV=.10, PHN=.15, LAP=.10, TAB=.15, AC=.20, REF=.08, WM=.08, KIT=.30, AUD=.35, WEA=.35, GAM=.15, ACC=.60)[c] for c in CATEGORIES])
RETURN_BASE = dict(TV=.015, PHN=.03, LAP=.025, TAB=.025, AC=.01, REF=.012, WM=.012, KIT=.03, AUD=.05, WEA=.045, GAM=.02, ACC=.04, SRV=0.0)
COMPLEMENT = {("PHN", "ACC"): 2.5, ("PHN", "AUD"): 1.2, ("PHN", "WEA"): 0.6, ("LAP", "ACC"): 2.0, ("LAP", "AUD"): 0.6,
              ("TAB", "ACC"): 1.5, ("TV", "AUD"): 1.0, ("TV", "GAM"): 0.4, ("GAM", "ACC"): 0.8, ("REF", "KIT"): 0.4, ("WM", "KIT"): 0.3}
U0 = 0.12
NEST_LAMBDA = 0.45
RATE_THETA = 3.9            # Gamma(k=2, theta) purchase-occasion rate; see docs/DECISIONS.md
OPEN_RATE = dict(whatsapp=0.92, sms=0.85, app_push=0.55, email=0.35, in_store=1.0)
CHANNEL_COST = dict(sms=0.15, email=0.05, app_push=0.02, whatsapp=0.80, in_store=0.0)
NONPRICE = {"early_access", "free_service", "loyalty_points"}


def _load_cal() -> dict:
    try:
        return json.loads(REFERENCE_STATS_PATH.read_text(encoding="utf-8"))["calibration"]
    except Exception:  # generator must still run without the raw reference data
        return {"guest_order_share": 0.0776, "sku_popularity_zipf": 0.632, "return_rate_scale": 0.915,
                "online_dow_profile_sun_first": [1.23, 1.2, 0.96, 0.89, 0.87, 0.93, 0.92],
                "online_hour_profile": [1.0] * 24, "late_share": 0.0677,
                "review_score_by_late_band": {"on_time": 4.29, "1-3": 3.29, "4-7": 2.10, "8-14": 1.68, "15+": 1.73},
                "installment_share_by_price_quartile": {"q1": .31, "q2": .45, "q3": .59, "q4": .71},
                "canceled_share": 0.0063, "multi_item_order_share": 0.0994,
                "delivery_days_median_same_region": 6.55, "delivery_days_median_cross_region": 12.79}


class World:
    def __init__(self, seed: int, n_customers: int = N_CUSTOMERS, verbose: bool = True):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
        self.cal = _load_cal()
        self.N = n_customers
        self._build_static()

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # =================================================================== static world
    def _build_static(self):
        rng = self.rng
        self.day0 = HISTORY_START - timedelta(days=WARMUP_DAYS)
        self.D = WARMUP_DAYS + (HISTORY_END - HISTORY_START).days + 1
        self.DX = self.D + FORWARD_DAYS + 40
        self.dates = [self.day0 + timedelta(days=k) for k in range(self.DX)]
        self.h0 = WARMUP_DAYS
        self.di = lambda dt: (dt - self.day0).days

        self.regions, self.cities, self.stores, self.warehouses = build_geography(rng)
        self.products = build_catalog(rng)
        self.relationships = build_relationships(self.products)
        pr = self.products
        self.P = int((~pr["is_service"]).sum())
        self.PT = len(pr)
        self.sku_ids = pr["sku_id"].tolist()
        self.sku_pos = {s: k for k, s in enumerate(self.sku_ids)}
        cat_all = pr["category"].tolist()
        self.s_cat = np.array([CAT_INDEX.get(c, -1) for c in cat_all])
        self.s_sub = pr["subcategory"].astype("category").cat.codes.to_numpy()
        self.sub_names = list(pr["subcategory"].astype("category").cat.categories)
        self.s_grp = pr["substitute_group"].astype("category").cat.codes.to_numpy()
        self.grp_names = list(pr["substitute_group"].astype("category").cat.categories)
        brands = sorted(pr.loc[~pr["is_service"], "brand"].unique().tolist())
        self.brands = brands
        self.s_brand = np.array([brands.index(b) if b in brands else 0 for b in pr["brand"]])
        self.s_launch = np.array([self.di(d) for d in pr["launch_date"]])
        self.s_eol = np.array([self.di(d) if d is not None and not pd.isna(d) else 10 ** 6 for d in pr["eol_date"]])
        self.s_margin = pr["margin_pct"].to_numpy(float)
        self.s_imported = pr["is_imported"].to_numpy(bool)
        tp = np.zeros(self.PT)
        for c, g in pr.groupby("category"):
            tp[g.index] = g["launch_price"].rank(pct=True).to_numpy()
        self.s_tierpos = tp
        zipf = float(self.cal.get("sku_popularity_zipf", 0.632))
        pop = np.zeros(self.PT)
        for c, g in pr.groupby("category"):
            ranks = rng.permutation(len(g)) + 1
            v = -zipf * np.log(ranks)
            pop[g.index] = v - v.mean()
        hero = {"TV-AUR-55U7": 1.3, "TV-AUR-55Q8": 0.9, "TV-AUR-50U5": 0.9, "LAP-KAI-14A25": 0.6, "LAP-KAI-14A26": 0.8,
                "ACC-PRE-BAG15": 1.2, "ACC-PRE-MSE01": 1.0, "ACC-PRE-WMT55": 1.0, "AUD-AUR-SB5": 0.7}
        for s, v in hero.items():
            pop[self.sku_pos[s]] = v + 0.5
        self.s_pop = pop
        self.s_quality = rng.normal(0, 0.3, self.PT)
        # daily list price with price erosion
        months = (np.arange(self.DX)[:, None] - self.s_launch[None, :]) / 30.44
        ero = pr["erosion_per_month"].to_numpy(float)
        self.list_price = (pr["launch_price"].to_numpy(float)[None, :] * np.maximum(0.72, 1 - ero[None, :] * np.maximum(months, 0))).astype(np.float64)
        self.s_mrp = pr["mrp"].to_numpy(float)
        self.cat_skus = [np.nonzero(self.s_cat == k)[0] for k in range(K)]
        self.cat_pref = np.array([np.median(pr.loc[self.cat_skus[k], "launch_price"]) for k in range(K)])
        self.sku_arr = dict(is_imported=self.s_imported[: self.P], case_pack=pr["case_pack"].to_numpy()[: self.P],
                            is_big=np.isin(self.s_cat[: self.P], [CAT_INDEX[c] for c in ("TV", "AC", "REF", "WM")]),
                            cat_is_acc=self.s_cat[: self.P] == CAT_INDEX["ACC"])
        # subcategory table per category
        self.cat_subs = []
        for k in range(K):
            subs = sorted(set(self.s_sub[self.cat_skus[k]].tolist()))
            pos = np.array([self.s_tierpos[self.cat_skus[k][self.s_sub[self.cat_skus[k]] == s]].mean() for s in subs])
            self.cat_subs.append((np.array(subs), pos))

        # calendar
        self.events = load_events()
        self.season, self.fest, self.payday, self.fest_truth = build_calendar(self.dates, self.events)
        self.launch_flag = np.zeros(self.DX, bool)
        for r in self.events.itertuples():
            if r.kind == "launch":
                a, b = self.di(r.start), self.di(r.end)
                self.launch_flag[max(a - 5, 0):max(b + 1, 0)] = True
        self.dow_store, self.dow_online = dow_weights(self.dates, self.cal.get("online_dow_profile_sun_first", [1] * 7))
        self.md, self.deal, self.clear = build_price_actions(rng, self.dates, self.events, self.sku_arr, self.sku_ids[: self.P],
                                                             self.s_launch[: self.P], self.s_eol[: self.P])
        # pad deal/clear to include services (never discounted by open actions)
        self.deal = np.concatenate([self.deal, np.zeros((self.DX, self.PT - self.P))], 1)
        self.clear = np.concatenate([self.clear, np.zeros((self.DX, self.PT - self.P))], 1)

        # stores
        st = self.stores
        self.S = len(st)
        self.store_ids = st["store_id"].tolist()
        self.st_city = np.array([CITY_INDEX[c] for c in st["city_code"]])
        self.st_region = st["region"].to_numpy()
        self.st_attr = st["attractiveness"].to_numpy(float)
        self.st_install = st["install_slots_per_day"].to_numpy(int)
        self.st_demo = np.maximum(st["demo_slots_per_day"].to_numpy(int), 4)
        self.st_sfs = st["ship_from_store"].to_numpy(bool)
        self.st_sfs_cap = np.maximum(st["sfs_orders_per_day"].to_numpy(int), 1)
        self.st_local = np.array([[json.loads(j)[c] for c in CATEGORIES] for j in st["local_mult_json"]])
        self.dist = store_distance_matrix(st)
        self.city_stores = [np.nonzero(self.st_city == c)[0] for c in range(len(CITY_CODES))]
        # fulfilment candidates: ship-from-store stores in the same region, nearest first
        self.fulfil = []
        for s in range(self.S):
            cand = [t for t in np.argsort(self.dist[s], kind="stable") if self.st_sfs[t] and self.st_region[t] == self.st_region[s]]
            self.fulfil.append(np.array(cand[:6], dtype=int))
        self._build_ranging()

        # customers
        cdf, ctruth, ca = build_customers(rng, st, self.cities, brands, self.N, RATE_THETA)
        self.cust_df, self.cust_truth, self.ca = cdf, ctruth, ca
        self.cust_ids = cdf["customer_id"].to_numpy()
        self._plant_customer_stories()
        city_cat = np.array([[json.loads(j)[c] for c in CATEGORIES] for j in self.cities["category_mult_json"]])
        self.static_rate = (ca["base_rate"][:, None] / 365.0 / CONV0[None, :]) * ca["aff"] * city_cat[ca["city_i"]] * self.st_local[ca["store_idx"]]
        self.B = np.zeros((K, K))
        for (a, b), v in COMPLEMENT.items():
            self.B[CAT_INDEX[a], CAT_INDEX[b]] = v
        cyc = np.array([dict(TV=72, PHN=30, LAP=48, TAB=40, AC=96, REF=110, WM=96, KIT=60, AUD=30, WEA=30, GAM=48, ACC=18)[c] for c in CATEGORIES]) * 30.44
        self.cycle = cyc
        self.h_ps = np.clip(ca["price_sens"] / 0.4, 0.25, 2.5)
        self.attach_city = np.exp(rng.normal(0, 0.12, (len(CITY_CODES), 8)))
        self.attach_city[CITY_INDEX["HYD"], 2] = stories.HYD_BAG_ATTACH_MULT  # S10 bag attach
        self.camps = build_campaign_plan(rng)
        guest_share = float(self.cal.get("guest_order_share", 0.0776))
        self.guest_ratio = guest_share / (1 - guest_share)

    def _build_ranging(self):
        rng = self.rng
        fmt = self.stores["format"].to_numpy()
        std_p = dict(ACC=.95, PHN=.75, AUD=.8, WEA=.75, TV=.6, LAP=.6, TAB=.6, KIT=.55, AC=.55, REF=.5, WM=.5, GAM=.5)
        exp_p = dict(ACC=.85, PHN=.6, AUD=.6, WEA=.55, TAB=.3, LAP=.25, TV=.12, KIT=.2, GAM=.2, AC=0, REF=0, WM=0)
        tier = self.products["tier"].to_numpy()
        R = np.zeros((self.S, self.P), bool)
        for s in range(self.S):
            for p in range(self.P):
                c = CATEGORIES[self.s_cat[p]]
                if fmt[s] == "Flagship":
                    R[s, p] = True
                else:
                    base = (std_p if fmt[s] == "Standard" else exp_p)[c] * 0.72
                    base *= 0.7 if tier[p] == "premium" else 1.0
                    R[s, p] = rng.random() < base
        forced = {stories.S1_SKUS[0]: ["HYD", "PUN-01", "PUN-02", "MUM-03", "MUM-01", "MUM-02"],
                  stories.S1_SKUS[1]: ["HYD", "PUN-01", "PUN-02", "MUM-03", "MUM-01"],
                  "TV-AUR-50U5": ["HYD", "PUN-01", "PUN-02", "MUM-03", "DEL", "BLR"],
                  stories.S2_SKU: ["DEL-01", "DEL-02", "DEL-03"], "LAP-KAI-14A26": ["DEL-01", "DEL-02", "DEL-03"],
                  "ACC-PRE-BAG15": ["ALL"], "ACC-PRE-MSE01": ["ALL"]}
        for sku, where in forced.items():
            p = self.sku_pos[sku]
            for s, sid in enumerate(self.store_ids):
                if any(w == "ALL" or sid.startswith(w) for w in where):
                    R[s, p] = True
        for s, sid in enumerate(self.store_ids):
            if sid in ("CHE-01", "CHE-02"):
                R[s, self.cat_skus[CAT_INDEX["AC"]]] = True
        self.ranged = R

    def _plant_customer_stories(self):
        ca = self.ca
        # S4: elite loyalists are heavy, loyal phone upgraders
        el = ca["elite"]
        ca["base_rate"][el] *= 1.6
        k = CAT_INDEX["PHN"]
        ca["aff"][el, k] += 0.18
        ca["aff"][el] /= ca["aff"][el].sum(1, keepdims=True)
        self.cust_truth.loc[el, "base_purchase_rate"] = ca["base_rate"][el]
        for j, c in enumerate(CATEGORIES):
            self.cust_truth[f"affinity_{c}"] = ca["aff"][:, j]

    # =================================================================== dynamic state
    def _init_state(self):
        rng, N = self.rng, self.N
        ca = self.ca
        self.present = ca["joined_day"] <= 0
        self.active = rng.random(N) < 0.75
        own = rng.random((N, K)) < np.clip(0.25 + 3 * ca["aff"], 0, 0.95)
        self.age = np.where(own, rng.uniform(0, 1.3, (N, K)) * self.cycle[None, :], np.nan)
        self.lastbuy = np.full((N, K), -1e6)
        self.ongoing = np.zeros((N, K), np.int16)
        self.ongoing_vis = np.zeros((N, K), np.int16)
        self.last_browse = np.full((N, K), -10 ** 6)
        self.n_orders = np.zeros(N, int)
        self.promo_orders = np.zeros(N, int)
        self.spend = np.zeros(N)
        self.last_order = np.full(N, -10 ** 6)
        self.cat_buy_last = np.full((N, K), -10 ** 6)
        self.order_days: list[list[int]] = [[] for _ in range(N)]
        self.exp_days: list[list[int]] = [[] for _ in range(N)]
        self.offers: list[list[int]] = [[] for _ in range(N)]
        self.supp_until = np.full(N, -1)
        self.supp_cats = np.zeros((N, K), bool)
        self.supp_p = np.zeros(N)
        self.churn_mult = np.ones(N)
        self.churn_mult_until = np.full(N, -1)
        self.boost_wm_until = np.full(N, -1)
        self.consent = ca["consent"].copy()
        self.wa = ca["wa"].copy()
        self.email = ca["email"].copy()
        self.unsub_day = np.full(N, -1)
        # journeys (preallocated)
        cap = 1_600_000
        self.J = dict(cust=np.zeros(cap, np.int32), cat=np.zeros(cap, np.int8), sub=np.zeros(cap, np.int16),
                      start=np.zeros(cap, np.int32), end=np.zeros(cap, np.int32), vis=np.zeros(cap, bool),
                      kind=np.zeros(cap, np.int8), camp=np.full(cap, -1, np.int16), outcome=np.zeros(cap, np.int8),
                      restrict=np.full(cap, -1, np.int16))
        self.nJ = 0
        self.end_bucket: dict[int, list[np.ndarray]] = {}
        # outputs
        self.orders: list[tuple] = []
        self.lines: list[tuple] = []
        self.returns: list[tuple] = []
        self.reviews: list[tuple] = []
        self.lost: list[tuple] = []
        self.life_events: list[tuple] = []
        self.exposures: list[dict] = []
        self.kappa: dict = {}
        self.restock_due: dict[int, list[tuple]] = {}
        self.install_booked = np.zeros((self.S, self.DX), np.int32)
        self.demo_booked = np.zeros((self.S, self.DX), np.int32)
        self.sfs_load = np.zeros((self.S, self.DX), np.int32)
        self.install_requests = np.zeros((self.S, self.DX), np.int32)
        self.city_lambda = np.zeros((self.D, len(CITY_CODES), K), np.float32)
        self.oid = 0
        self.inv = Inventory(rng, self.S, self.P, self.ranged, self.sku_arr, self.st_region, [], self.store_ids,
                             self.sku_ids[: self.P], self.dates, self.h0)
        self._init_inventory()

    def _init_inventory(self):
        ca = self.ca
        cat_rate = np.zeros((self.S, K))
        np.add.at(cat_rate, ca["store_idx"], self.static_rate * CONV0[None, :] * 0.55)
        cat_rate *= 1 + self.guest_ratio
        self.guest_base = cat_rate * self.guest_ratio / (1 + self.guest_ratio) / 0.55 * 0.6
        inv = self.inv
        for s in range(self.S):
            for k in range(K):
                idx = self.cat_skus[k]
                live = idx[(self.s_launch[idx] <= 0) & (self.s_eol[idx] > 0) & self.ranged[s, idx]]
                if len(live) == 0:
                    continue
                w = np.exp(self.s_pop[live])
                share = w / w.sum()
                d0 = cat_rate[s, k] * share
                inv.ewma[s, live] = d0
                for p, dd in zip(live, d0):
                    qty = int(round(dd * self.rng.uniform(20, 40))) + (1 if self.sku_arr["is_big"][p] else 2)
                    remaining = qty
                    while remaining > 0:  # spread initial receipts over the previous 45 days
                        q = min(remaining, max(1, qty // 3))
                        inv.add_stock(s, p, q, -int(self.rng.integers(0, 45)))
                        remaining -= q

    # =================================================================== helpers
    def _rep(self, idx=None):
        age = self.age if idx is None else self.age[idx]
        floor = REP_FLOOR[None, :]
        x = (age - self.cycle[None, :]) / (0.2 * self.cycle[None, :])
        r = floor + (1.45 - floor) / (1 + np.exp(-np.nan_to_num(x, nan=0.0)))
        r = np.where(np.isnan(age), 0.85, r)
        el = self.ca["elite"] if idx is None else self.ca["elite"][idx]
        r[:, CAT_INDEX["PHN"]] = np.where(el, np.maximum(r[:, CAT_INDEX["PHN"]], 1.0), r[:, CAT_INDEX["PHN"]])
        return r

    def _rates(self, d, idx=None):
        """Journey-start hazard per customer x category (no ongoing mask)."""
        ca = self.ca
        sl = slice(None) if idx is None else idx
        t = min(d + 6, self.DX - 1)
        ci = ca["city_i"][sl]
        season = self.season[t][ci]
        festm = np.maximum(0.2, 1 + ca["fest_aff"][sl][:, None] * self.fest[t][ci])
        delta = d - self.lastbuy[sl]
        E = np.where((delta >= 1) & (delta <= 45), np.exp(-delta / 15.0), 0.0)
        comp = 1 + E @ self.B
        lam = self.static_rate[sl] * season * festm * self._rep(idx) * comp
        lam *= self.story_cc[ci]
        if self.launch_flag[d]:
            lam[:, CAT_INDEX["PHN"]] *= np.where(ca["elite"][sl], 2.2, 1.0)
        wm = self.boost_wm_until[sl] >= d
        if wm.any():
            lam[:, CAT_INDEX["WM"]] *= np.where(wm, 9.0, 1.0)
        lam *= np.where(self.active[sl], 1.0, 0.06)[:, None]
        return lam

    def _F(self, d, city, k, h):
        return (1 - self.md[d, city, k]) ** (-EPS[k] * h)

    # =================================================================== main loop
    def run(self):
        self._init_state()
        self.story_cc = np.ones((len(CITY_CODES), K))
        self.camp_by_day: dict[int, list[int]] = {}
        for m, c in enumerate(self.camps):
            c["start_day"], c["end_day"] = self.di(c["start"]), self.di(c["end"])
            self.camp_by_day.setdefault(c["start_day"], []).append(m)
        self.launch_by_day: dict[int, list[int]] = {}
        for p in range(self.P):
            if 0 < self.s_launch[p] < self.D:
                self.launch_by_day.setdefault(int(self.s_launch[p]), []).append(p)
        self._story_setup()
        for d in range(self.D):
            if d % 60 == 0:
                self.log(f"  day {d:4d} {self.dates[d]}  orders={len(self.orders):,} journeys={self.nJ:,} exposures={len(self.exposures):,}")
            self._day(d)
        self.log(f"  done: orders={len(self.orders):,} lines={len(self.lines):,} journeys={self.nJ:,} exposures={len(self.exposures):,}")

    def _day(self, d):
        rng, inv = self.rng, self.inv
        record = d >= self.h0
        inv.receive_due(d)
        for (s, p, q) in self.restock_due.pop(d, []):
            inv.add_stock(s, p, q, d)
            inv.receipts_today[s, p] += q
        for p in self.launch_by_day.get(d, []):
            self._launch_fill(d, p)
        self._story_hooks(d)
        newly = np.nonzero(self.ca["joined_day"] == d)[0] if d > 0 else np.array([], int)
        self.present[newly] = True
        self.active[newly] = True
        if record:
            for m in self.camp_by_day.get(d, []):
                self._run_campaign(d, m)
        # ---------------- journeys start
        lam = self._rates(d)
        if record:
            ci = self.ca["city_i"]
            for k in range(K):
                self.city_lambda[d, :, k] = np.bincount(ci, weights=lam[:, k] * self.present, minlength=len(CITY_CODES))
        lam = lam * (self.ongoing == 0) * self.present[:, None]
        starts = rng.random((self.N, K)) < lam
        ii, cc = np.nonzero(starts)
        self._new_journeys(d, ii, cc, kind=0)
        if len(newly):
            k = np.array([rng.choice(K, p=a) for a in self.ca["aff"][newly]])
            self._new_journeys(d, newly, k, kind=2)
        vis = self.ongoing_vis > 0
        self.last_browse[vis] = d
        # ---------------- purchases
        self._purchases(d, record)
        self._guests(d, record)
        # ---------------- lifecycle
        act = self.active & self.present
        cm = np.where(self.churn_mult_until >= d, self.churn_mult, 1.0)
        churn = act & (rng.random(self.N) < self.ca["churn"] / 30.0 * cm)
        react = self.present & ~self.active & (rng.random(self.N) < 0.0025)
        self.active[churn] = False
        self.active[react] = True
        if record:
            for i in np.nonzero(churn)[0]:
                self.life_events.append((int(i), d, "churned", "hazard"))
            for i in np.nonzero(react)[0]:
                self.life_events.append((int(i), d, "reactivated", "spontaneous"))
        self.age += 1
        # ---------------- inventory
        active_mask = self.ranged & ((self.s_launch[None, : self.P] <= d) & ((self.s_eol[None, : self.P] > d) | (inv.on_hand > 0)))
        wk_end = self.dates[d].weekday() == 6 or d == self.D - 1
        wk_label = self.dates[d] - timedelta(days=self.dates[d].weekday())
        inv.end_of_day(d, active_mask, record, wk_end, wk_label)
        stores = np.array([s for s in range(self.S) if (s % 7) == self.dates[d].weekday()], int)
        if len(stores):
            sellable = (self.s_launch[: self.P] <= d + 7) & (self.s_eol[: self.P] > d + 14)
            inv.review(d, stores, sellable, self._plan_uplift(d))

    def _plan_uplift(self, d):
        a, b = min(d + 10, self.DX - 1), min(d + 28, self.DX - 1)
        fut = (self.season[a:b] * (1 + 0.75 * self.fest[a:b])).mean(0)
        past = (self.season[max(d - 21, 0):d + 1] * (1 + np.maximum(self.fest[max(d - 21, 0):d + 1], -0.5))).mean(0)
        ratio = np.clip(fut / np.maximum(past, 0.05), 0.3, 3.0)  # city x cat
        return ratio[self.st_city][:, self.s_cat[: self.P]]

    def _launch_fill(self, d, p):
        inv = self.inv
        k = self.s_cat[p]
        for s in range(self.S):
            if not self.ranged[s, p]:
                continue
            idx = self.cat_skus[k]
            live = (self.ranged[s, idx]) & (self.s_launch[idx] <= d) & (self.s_eol[idx] > d)
            cat_e = inv.ewma[s, idx].sum()
            share = 1.5 / max(1, live.sum())
            inv.ewma[s, p] = cat_e * share
            qty = max(1 if self.sku_arr["is_big"][p] else 2, int(math.ceil(cat_e * share * 21)))
            inv.create_po(s, p, qty, d - 3, po_type="launch_fill", eta_override=d)
            inv.receive_due(d)

    # =================================================================== journeys
    def _new_journeys(self, d, ii, cc, kind, camp=-1, restrict=-1, end=None, sub=None):
        n = len(ii)
        if n == 0:
            return np.array([], int)
        rng, ca = self.rng, self.ca
        if sub is None:
            sub = np.zeros(n, np.int16)
            t = min(d + 6, self.DX - 1)
            for k in np.unique(cc):
                m = cc == k
                subs, pos = self.cat_subs[k]
                live_n = np.array([((self.s_sub[self.cat_skus[k]] == s) & (self.s_launch[self.cat_skus[k]] <= d) &
                                    (self.s_eol[self.cat_skus[k]] > d)).sum() for s in subs], float) + 0.3
                ci = ca["city_i"][ii[m]]
                shift = 0.12 * np.clip(self.fest[t][ci, k], 0, 1)
                tp = ca["tier_pref"][ii[m]] + shift
                w = live_n[None, :] * np.exp(-2.5 * np.abs(tp[:, None] - pos[None, :]))
                if k == CAT_INDEX["TV"] and d >= self.di(stories.S1_START):
                    s55 = self.sub_names.index("TV_55")
                    col = np.nonzero(subs == s55)[0]
                    boost = np.isin(ci, [CITY_INDEX[c] for c in stories.S1_CITIES])
                    w[boost[:, None] & (np.arange(len(subs))[None, :] == col[0])] *= 2.2
                w /= w.sum(1, keepdims=True)
                u = rng.random(m.sum())
                sub[m] = subs[(w.cumsum(1) < u[:, None]).sum(1).clip(0, len(subs) - 1)]
        if end is None:
            big = np.isin(cc, [CAT_INDEX[c] for c in ("TV", "AC", "REF", "WM", "LAP", "PHN", "TAB", "GAM")])
            mid = np.isin(cc, [CAT_INDEX[c] for c in ("AUD", "WEA", "KIT")])
            L = np.where(big, np.clip(3 + rng.negative_binomial(2, 0.3, n), 3, 21),
                         np.where(mid, np.clip(2 + rng.negative_binomial(2, 0.45, n), 2, 14), np.clip(1 + rng.poisson(1.5, n), 1, 7)))
            if kind == 2:
                L = rng.integers(0, 4, n)
            end = d + L
        vis = rng.random(n) < 0.2 + 0.75 * ca["online"][ii]
        a, b = self.nJ, self.nJ + n
        if b > len(self.J["cust"]):
            for key in self.J:
                self.J[key] = np.concatenate([self.J[key], np.full_like(self.J[key], self.J[key][0] * 0 + (-1 if key in ("camp", "restrict") else 0))])
        J = self.J
        J["cust"][a:b], J["cat"][a:b], J["sub"][a:b] = ii, cc, sub
        J["start"][a:b], J["end"][a:b], J["vis"][a:b], J["kind"][a:b] = d, end, vis, kind
        J["camp"][a:b], J["restrict"][a:b] = camp, restrict
        self.nJ = b
        np.add.at(self.ongoing, (ii, cc), 1)
        np.add.at(self.ongoing_vis, (ii[vis], cc[vis]), 1)
        ids = np.arange(a, b)
        for e in np.unique(end):
            self.end_bucket.setdefault(int(e), []).append(ids[end == e])
        return ids

    # =================================================================== purchases
    def _purchases(self, d, record):
        rng, ca, J = self.rng, self.ca, self.J
        bucket = self.end_bucket.pop(d, [])
        if not bucket:
            return
        ids = np.sort(np.concatenate(bucket))
        ii, cc = J["cust"][ids], J["cat"][ids].astype(int)
        np.add.at(self.ongoing, (ii, cc), -1)
        v = J["vis"][ids]
        np.add.at(self.ongoing_vis, (ii[v], cc[v]), -1)
        kind = J["kind"][ids]
        ci = ca["city_i"][ii]
        F = (1 - self.md[d, ci, cc]) ** (-EPS[cc] * self.h_ps[ii])
        dowm = ca["online"][ii] * self.dow_online[d] + (1 - ca["online"][ii]) * self.dow_store[d]
        p = CONV0[cc] * F * self.payday[d] * dowm
        sup = (self.supp_until[ii] >= d) & self.supp_cats[ii, cc]
        p = np.where(sup, p * (1 - self.supp_p[ii]), p)
        conv = (rng.random(len(ids)) < p) | (kind != 0)
        J["outcome"][ids[~conv]] = 2
        J["outcome"][ids[sup & ~conv & (kind == 0)]] = 4
        buy = ids[conv]
        if len(buy) == 0:
            return
        custs = J["cust"][buy]
        order = np.argsort(custs, kind="stable")
        buy, custs = buy[order], custs[order]
        cuts = np.nonzero(np.diff(custs))[0] + 1
        for grp in np.split(buy, cuts):
            self._customer_order(d, int(J["cust"][grp[0]]), grp, record)

    def _offer_vector(self, d, i, idx):
        """Best targeted offer applicable to each candidate SKU for customer i (depth, campaign)."""
        depth = np.zeros(len(idx))
        camp = np.full(len(idx), -1)
        keep = []
        for m in self.offers[i]:
            c = self.camps[m]
            if c["end_day"] < d:
                continue
            keep.append(m)
            if c["cities"] != "ALL" and CITY_CODES[self.ca["city_i"][i]] not in c["cities"]:
                continue
            inscope = c["scope_mask"][idx]
            dp = c["eff_depth"]
            better = inscope & (dp >= depth)
            depth[better] = dp
            camp[better] = m
        self.offers[i] = keep
        return depth, camp

    def _choose(self, d, i, k, jsub, store, online, restrict=-1):
        """Nested-logit SKU choice. Returns (sku, fulfil_store, price info) or None."""
        rng, ca, inv = self.rng, self.ca, self.inv
        idx = self.cat_skus[k]
        city = ca["city_i"][i] if i >= 0 else self.st_city[store]
        launched = self.s_launch[idx] <= d
        alive = self.s_eol[idx] > d
        if online:
            fl = self.fulfil[store] if len(self.fulfil[store]) else np.array([store])
            stock_any = inv.on_hand[np.ix_(fl, idx)].max(0) > 0
            cand = launched & (alive | stock_any) & self.ranged[fl][:, idx].any(0)
        else:
            stock_any = inv.on_hand[store, idx] > 0
            cand = launched & (alive | stock_any) & self.ranged[store, idx]
        if restrict >= 0:
            cand &= self.camps[restrict]["scope_mask"][idx]
        if not cand.any():
            return None
        lp = self.list_price[d, idx]
        base_disc = 1 - (1 - self.md[d, city, k]) * (1 - self.deal[d, idx]) * (1 - self.clear[d, idx])
        if i >= 0:
            tdep, tcamp = self._offer_vector(d, i, idx)
            tp, alpha, bu = ca["tier_pref"][i], 0.8 + 2.2 * ca["price_sens"][i], ca["brand_util"][i, self.s_brand[idx]]
        else:
            tdep, tcamp = np.zeros(len(idx)), np.full(len(idx), -1)
            tp, alpha, bu = rng.uniform(0.2, 0.8), 1.7, 0.0
        fest_up = 0.4 * max(0.0, min(1.0, self.fest[d, city, k]))
        Vb = (self.s_pop[idx] - 2.6 * np.abs(tp - self.s_tierpos[idx]) + 1.0 * (self.s_sub[idx] == jsub) + bu
              + 0.4 * self.s_quality[idx] + 0.3 * ((d - self.s_launch[idx]) < 120) - 0.3 * (~alive) + fest_up * self.s_tierpos[idx])

        def probs(disc_extra, bonus):
            price = lp * (1 - base_disc) * (1 - disc_extra)
            V = Vb - alpha * np.log(price / self.cat_pref[k]) + bonus
            V = np.where(cand, V, -np.inf)
            g = self.s_grp[idx]
            x = np.where(cand, np.exp((V - V[cand].max()) / NEST_LAMBDA), 0.0)
            ug, inv_g = np.unique(g, return_inverse=True)
            sums = np.bincount(inv_g, weights=x, minlength=len(ug))
            iv = np.where(sums > 0, NEST_LAMBDA * np.log(np.maximum(sums, 1e-300)), -np.inf)
            pg = np.exp(iv - iv[sums > 0].max())
            pg = np.where(sums > 0, pg, 0)
            pg /= pg.sum()
            return pg[inv_g] * x / np.maximum(sums[inv_g], 1e-300)

        eff_t = np.where(tcamp >= 0, tdep, 0.0)
        bonus = np.where(tcamp >= 0, 0.35, 0.0)
        P1 = probs(eff_t, bonus)
        # counterfactual bookkeeping for cannibalisation truth (SKU-specific price actions only)
        sku_specific = (eff_t > 0) | (self.deal[d, idx] > 0) | (self.clear[d, idx] > 0)
        if record_kappa := (sku_specific.any() and (~sku_specific & cand).any()):
            price0 = lp * (1 - self.md[d, city, k])
            V0 = Vb - alpha * np.log(price0 / self.cat_pref[k])
            base_disc_save = base_disc
            P0 = self._probs_plain(V0, cand, idx)
        j = int(rng.choice(len(idx), p=P1 / P1.sum()))
        if record_kappa and self.dates[d] >= HISTORY_START:
            g = self.s_grp[idx]
            for gg in np.unique(g[sku_specific]):
                prom = sku_specific & (g == gg)
                dprom = float((P1[prom] - P0[prom]).sum())
                same = (g == gg) & ~prom
                drop_same = float((P0[same] - P1[same]).sum())
                drop_other = float((P0[g != gg] - P1[g != gg]).sum())
                key = (self.grp_names[gg], "targeted" if (eff_t[prom] > 0).any() else "open_deal")
                acc = self.kappa.setdefault(key, [0.0, 0.0, 0.0, 0.0])
                if restrict >= 0:
                    acc[3] += float(P1[prom].sum())
                else:
                    acc[0] += dprom
                    acc[1] += drop_same
                    acc[2] += drop_other
        return idx[j], tdep[j] if tcamp[j] >= 0 else 0.0, int(tcamp[j])

    def _probs_plain(self, V, cand, idx):
        V = np.where(cand, V, -np.inf)
        g = self.s_grp[idx]
        x = np.where(cand, np.exp((V - V[cand].max()) / NEST_LAMBDA), 0.0)
        ug, inv_g = np.unique(g, return_inverse=True)
        sums = np.bincount(inv_g, weights=x, minlength=len(ug))
        iv = np.where(sums > 0, NEST_LAMBDA * np.log(np.maximum(sums, 1e-300)), -np.inf)
        pg = np.where(sums > 0, np.exp(iv - iv[sums > 0].max()), 0)
        pg /= pg.sum()
        return pg[inv_g] * x / np.maximum(sums[inv_g], 1e-300)

    def _pick_store(self, i):
        ca = self.ca
        if self.rng.random() < 0.8:
            return int(ca["store_idx"][i])
        cs = self.city_stores[ca["city_i"][i]]
        w = self.st_attr[cs]
        return int(cs[self.rng.choice(len(cs), p=w / w.sum())])

    def _customer_order(self, d, i, jids, record):
        rng, ca, J, inv = self.rng, self.ca, self.J, self.inv
        k0 = int(J["cat"][jids[0]])
        online = rng.random() < np.clip(ca["online"][i] * CAT_ONLINE[k0], 0.02, 0.95)
        store = self._pick_store(i) if not online else int(ca["store_idx"][i])
        groups: dict[tuple, list] = {}
        for j in jids:
            k, jsub, restrict = int(J["cat"][j]), int(J["sub"][j]), int(J["restrict"][j])
            res = self._choose(d, i, k, jsub, store, online, restrict)
            if res is None:
                J["outcome"][j] = 3
                if record:
                    self.lost.append((d, i, store, -1, k, "no_candidate"))
                continue
            p, tdep, tcamp = res
            fs, ch = self._fulfil(d, p, store, online)
            if fs is None:  # out of stock -> substitute / online / lost
                u = rng.random()
                if u < 0.55:
                    alt = self._substitute(p, store, online, d)
                    if alt is not None:
                        p, fs, ch = alt, (store if not online else self._fulfil(d, alt, store, True)[0]), ("store" if not online else "web")
                        tdep, tcamp = self._target_for(d, i, p)
                if fs is None and not online and 0.55 <= u < 0.75:
                    fs, ch = self._fulfil(d, p, store, True)
                if fs is None:
                    J["outcome"][j] = 3
                    inv.lost_today[store, p] += 1
                    if record:
                        self.lost.append((d, i, store, p, k, "stock_out"))
                    continue
            J["outcome"][j] = 1
            if ch == "web" and ca["app"][i] and rng.random() < 0.65:
                ch = "app"
            groups.setdefault((fs, ch), []).append((p, tdep, tcamp, j))
        for (fs, ch), items in groups.items():
            self._make_order(d, i, fs, ch, items, record)

    def _target_for(self, d, i, p):
        dep, cam = self._offer_vector(d, i, np.array([p]))
        return (float(dep[0]), int(cam[0])) if cam[0] >= 0 else (0.0, -1)

    def _fulfil(self, d, p, store, online):
        inv = self.inv
        if not online:
            return (store, "store") if inv.on_hand[store, p] > 0 else (None, None)
        for fs in self.fulfil[store] if len(self.fulfil[store]) else [store]:
            if inv.on_hand[fs, p] > 0:
                return int(fs), "web"
        return None, None

    def _substitute(self, p, store, online, d):
        inv = self.inv
        stores = self.fulfil[store] if online and len(self.fulfil[store]) else np.array([store])
        for level in (self.s_grp, self.s_sub):
            cands = np.nonzero((level[: self.P] == level[p]) & (np.arange(self.P) != p) & (self.s_launch[: self.P] <= d))[0]
            ok = cands[(inv.on_hand[np.ix_(stores, cands)].max(0) > 0)] if len(cands) else cands
            if len(ok):
                return int(ok[np.argmax(self.s_pop[ok])])
        return None

    # ------------------------------------------------------------------- order construction
    def _price_line(self, d, p, city, tdep, tcamp, extra_disc=0.0):
        lp = self.list_price[d, p]
        k = self.s_cat[p]
        md = self.md[d, city, k] if k >= 0 else 0.0
        comps = {"markdown": md, "deal": self.deal[d, p], "clearance": self.clear[d, p], "campaign": tdep, "bundle": extra_disc}
        tot = 1 - np.prod([1 - v for v in comps.values()])
        if k >= 0:
            tot = min(tot, 1 - 0.82 * (1 - self.s_margin[p]))
        src = max(comps, key=comps.get) if tot > 0.001 else "none"
        return lp, max(tot, 0.0), src

    def _make_order(self, d, i, fs, ch, items, record):
        rng, ca, inv = self.rng, self.ca, self.inv
        city = ca["city_i"][i] if i >= 0 else self.st_city[fs]
        cancelled = rng.random() < float(self.cal.get("canceled_share", 0.0063))
        lines = []
        order_camp = -1
        for (p, tdep, tcamp, j) in items:
            c = self.camps[tcamp] if tcamp >= 0 else None
            depth = tdep if c is not None and c["offer_type"] in ("pct_off", "bundle_pct", "flat_off") else 0.0
            promo_val = 0.0
            if c is not None and c["offer_type"] == "bank_cashback":
                promo_val = c["discount_pct"] * self.list_price[d, p]
            if c is not None and c["offer_type"] == "loyalty_points":
                promo_val = 0.5 * c["discount_pct"] * self.list_price[d, p]
            if c is not None:
                order_camp = tcamp
            lines.append([p, 1 if self.s_cat[p] != CAT_INDEX["ACC"] else int(rng.choice([1, 1, 1, 1, 2, 2, 3][:7])), depth, tcamp, promo_val, None])
            lines += self._attach(d, i, p, fs, city, c, tcamp)
        if not lines:
            return
        # stock movements (services have none)
        final = []
        for ln in lines:
            p, q = ln[0], ln[1]
            if p < self.P:
                if cancelled:
                    if inv.on_hand[fs, p] <= 0:
                        continue
                else:
                    q = inv.sell(fs, p, q)
                    if q == 0:
                        continue
                    ln[1] = q
            final.append(ln)
        if not final:
            return
        self.oid += 1
        oid = self.oid
        if not record:
            self._update_trackers(d, i, final, 0.0, record, None)
            return
        order_id = f"ORD-{oid:08d}"
        gross = disc_tot = promo_tot = net = 0.0
        out_lines = []
        has_install = has_demo = False
        max_price = 0.0
        for ln_no, (p, q, depth, tcamp, promo_val, bundle_id) in enumerate(final, 1):
            lp, tot, src = self._price_line(d, p, city, depth, tcamp)
            if p >= self.P and tcamp >= 0 and bundle_id == "FREE":
                tot, src = 1.0, "campaign"
            unit = round(lp * (1 - tot), 2)
            cost = round(lp * (1 - self.s_margin[p]), 2)
            camp_id = self.camps[tcamp]["campaign_id"] if tcamp >= 0 else None
            gross += lp * q
            disc_tot += (lp - unit) * q
            promo_tot += promo_val * q
            net += unit * q
            max_price = max(max_price, lp)
            sid = self.sku_ids[p]
            has_install |= sid in ("SRV-INS-TV", "SRV-INS-AC", "SRV-INS-WM")
            has_demo |= sid == "SRV-DEM-REF"
            out_lines.append((order_id, ln_no, sid, q, float(self.s_mrp[p]), round(lp, 2), unit, round(tot, 4), cost,
                              round(unit * q, 2), src, camp_id, bundle_id if bundle_id != "FREE" else None, round(promo_val * q, 2)))
        # fulfilment / delivery
        home = int(ca["store_idx"][i]) if i >= 0 else fs
        delivery_days = 0
        promised = 0
        dispatch_delay = 0
        big = any(self.sku_arr["is_big"][ln[0]] for ln in final if ln[0] < self.P)
        if ch in ("web", "app"):
            k = 0
            while self.sfs_load[fs, d + k] >= self.st_sfs_cap[fs] and k < 4:
                k += 1
            dispatch_delay = k
            self.sfs_load[fs, d + k] += 1
            cls = 0 if self.st_city[fs] == self.ca["city_i"][i] else (1 if self.st_region[fs] == self.st_region[home] else 2)
            base = [2.0, 3.5, 6.8][cls]
            promised = int(base + 1)
            delivery_days = int(max(1, round(dispatch_delay + base * rng.lognormal(0, 0.28))))
        elif big:
            promised = 2
            delivery_days = int(max(1, round(1 + rng.lognormal(0, 0.45))))
        late = delivery_days > promised if promised else False
        install_delay = None
        if has_install and not cancelled:
            install_delay = self._book(self.install_booked, self.st_install, fs, d + max(delivery_days, 1))
        if has_demo and not cancelled:
            self._book(self.demo_booked, self.st_demo, fs, d + max(delivery_days, 1))
        # payment type (Olist instalment share by price quartile, scaled for Indian no-cost EMI)
        inst = self.cal.get("installment_share_by_price_quartile", {"q1": .31, "q2": .45, "q3": .59, "q4": .71})
        q = "q1" if net < 5000 else "q2" if net < 20000 else "q3" if net < 50000 else "q4"
        u = rng.random()
        emi = inst[q] * 0.55
        if u < emi:
            pay = "emi"
        else:
            v = rng.random()
            pay = ("upi" if v < 0.5 else "card" if v < 0.8 else "bnpl" if v < 0.86 else "gift_card" if v < 0.88 else
                   ("cash" if ch == "store" else "upi"))
        hour = self._hour(ch)
        status = "cancelled" if cancelled else "completed"
        self.orders.append((order_id, d, hour, self.cust_ids[i] if i >= 0 else None, i < 0, self.store_ids[fs],
                            self.store_ids[home] if i >= 0 else self.store_ids[fs], ch, self.camps[order_camp]["campaign_id"] if order_camp >= 0 else None,
                            len(out_lines), round(gross, 2), round(disc_tot, 2), round(promo_tot, 2), round(net, 2), pay, status,
                            promised, delivery_days if (ch != "store" or big) else 0, bool(late), install_delay))
        if cancelled:
            return
        self.lines.extend(out_lines)
        self._update_trackers(d, i, final, net, record, disc_tot / max(gross, 1))
        # returns & reviews
        rs = float(self.cal.get("return_rate_scale", 0.915))
        for (order_id_, ln_no, sid, qq, mrp, lp, unit, tot, cost, lt, src, camp_id, bid, pv) in out_lines:
            p = self.sku_pos[sid]
            if p >= self.P:
                continue
            pr = RETURN_BASE[CATEGORIES[self.s_cat[p]]] * rs * (1 + 1.5 * late) * math.exp(-0.6 * self.s_quality[p])
            if rng.random() < pr:
                rday = d + delivery_days + int(rng.integers(1, 15))
                reason = ("late_delivery" if late and rng.random() < 0.5 else
                          rng.choice(["defective", "not_as_expected", "changed_mind", "damaged_in_transit"], p=[0.35, 0.3, 0.25, 0.1]))
                restock = reason in ("not_as_expected", "changed_mind") and rng.random() < 0.6
                if restock:
                    self.restock_due.setdefault(rday, []).append((fs, p, 1))
                self.returns.append((order_id_, ln_no, sid, rday, str(reason), 1, round(unit, 2), bool(restock), self.store_ids[fs]))
        if i >= 0:
            pr_rev = 0.10 + 0.08 * late + 0.05 * (install_delay is not None and install_delay > 2)
            if rng.random() < pr_rev:
                anchor = max((ln for ln in out_lines), key=lambda x: x[5])
                p = self.sku_pos[anchor[2]]
                lateness = delivery_days - promised if late else 0
                band = self.cal.get("review_score_by_late_band", {})
                base = 4.29 if lateness <= 0 else band.get("1-3", 3.29) if lateness <= 3 else band.get("4-7", 2.1) if lateness <= 7 else band.get("8-14", 1.68)
                score = base + 0.8 * self.s_quality[p] - (0.5 if (install_delay or 0) > 2 else 0) + rng.normal(0, 1.0)
                score = int(np.clip(round(score), 1, 5))
                self.reviews.append((order_id, self.cust_ids[i], anchor[2], d + max(delivery_days, 0) + int(rng.integers(2, 21)),
                                     score, delivery_days, bool(late), install_delay))

    def _book(self, booked, slots, s, day):
        for k in range(0, 21):
            if booked[s, day + k] < slots[s]:
                booked[s, day + k] += 1
                self.install_requests[s, day] += 1 if booked is self.install_booked else 0
                return k
        booked[s, day + 21] += 1
        return 21

    def _hour(self, ch):
        if ch == "store":
            prof = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .3, .8, 1.1, 1.2, 1.1, 1.0, 1.0, 1.2, 1.5, 1.6, 1.4, .9, .2, 0])
        else:
            prof = np.array(self.cal.get("online_hour_profile", [1] * 24), float)
        prof = prof / prof.sum()
        return int(self.rng.choice(24, p=prof))

    def _attach(self, d, i, p, fs, city, camp, tcamp):
        """Services and accessories added to the same order (PLAN §6.4e)."""
        rng, inv = self.rng, self.inv
        cat = CATEGORIES[self.s_cat[p]] if self.s_cat[p] >= 0 else "SRV"
        ac = self.attach_city[city]
        out = []
        lp = self.list_price[d, p]
        bundle = camp["bundle_skus"] if camp is not None else []
        free = camp["free_service_sku"] if camp is not None else None
        bid = camp["campaign_id"] + "-B" if bundle else None

        def svc(sid, prob, free_kind=None):
            fr = free is not None and free_kind is not None and free in (free_kind, sid)
            if sid in bundle:
                prob = min(0.95, prob * 2.2 + 0.3)
            if fr:
                prob = min(0.95, prob * 1.3 + 0.25)
            if rng.random() < prob:
                q = self.sku_pos[sid]
                out.append([q, 1, camp["eff_depth"] if (sid in bundle and camp) else 0.0, tcamp if (fr or sid in bundle) else -1, 0.0,
                            "FREE" if fr else (bid if sid in bundle else None)])

        def acc(sub, prob, prefer=None):
            if prefer and prefer in bundle:
                prob = min(0.9, prob * 2.2 + 0.3)
            if rng.random() >= prob:
                return
            cands = [self.sku_pos[prefer]] if prefer and inv.on_hand[fs, self.sku_pos[prefer]] > 0 and rng.random() < 0.6 else []
            if not cands:
                sidx = self.sub_names.index(sub)
                c2 = np.nonzero((self.s_sub[: self.P] == sidx) & (inv.on_hand[fs] > 0) & (self.s_launch[: self.P] <= d))[0]
                if len(c2) == 0:
                    return
                cands = [int(c2[np.argmax(self.s_pop[c2] + rng.gumbel(0, 1, len(c2)))])]
            q = cands[0]
            inb = self.sku_ids[q] in bundle
            out.append([q, 1, camp["eff_depth"] if (inb and camp) else 0.0, tcamp if inb else -1, 0.0, bid if inb else None])

        pp_sid = "SRV-PP-2Y-XL" if lp >= 100000 else ("SRV-PP-1Y-L" if lp >= 30000 else "SRV-PP-1Y-S")
        if rng.random() < 0.35 and pp_sid != "SRV-PP-2Y-XL":
            pp_sid = pp_sid.replace("1Y", "2Y")
        if cat == "TV":
            svc("SRV-INS-TV", 0.70 * ac[0], "INSTALL")
            svc("SRV-WMT-TV", 0.22 * ac[0])
            acc("ACC_MNT", 0.20 * ac[3], "ACC-PRE-WMT55")
            acc("AUD_SB", 0.05 * ac[4], "AUD-AUR-SB5")
            svc(pp_sid, 0.18 * ac[1], "PROTECTPLUS")
        elif cat == "AC":
            svc("SRV-INS-AC", 0.92, "INSTALL")
            svc(pp_sid, 0.15 * ac[1], "PROTECTPLUS")
        elif cat == "WM":
            svc("SRV-INS-WM", 0.75 * ac[0], "INSTALL")
            svc(pp_sid, 0.15 * ac[1], "PROTECTPLUS")
        elif cat == "REF":
            svc("SRV-DEM-REF", 0.55 * ac[0], "INSTALL")
            svc(pp_sid, 0.15 * ac[1], "PROTECTPLUS")
        elif cat == "LAP":
            acc("ACC_BAG", 0.22 * ac[2], "ACC-PRE-BAG15")
            acc("ACC_MSE", 0.15 * ac[5], "ACC-PRE-MSE01")
            svc(pp_sid, 0.12 * ac[1], "PROTECTPLUS")
            svc("SRV-SET-LAP", 0.10)
        elif cat == "PHN":
            acc("ACC_CASE", 0.25 * ac[6])
            acc("ACC_CHG", 0.12 * ac[6])
            acc("AUD_EARBUDS", 0.05 * ac[7])
            svc("SRV-SET-PHN", 0.05)
            svc(pp_sid, 0.10 * ac[1], "PROTECTPLUS")
        elif cat == "TAB":
            acc("ACC_CASE", 0.25 * ac[6])
            svc(pp_sid, 0.10 * ac[1], "PROTECTPLUS")
        elif cat == "GAM" and self.sub_names[self.s_sub[p]] == "GAM_CON":
            acc("GAM_CTRL", 0.30)
        elif cat == "ACC" and bundle:
            for b in bundle:
                if self.sku_ids[p] != b and rng.random() < 0.45:
                    q = self.sku_pos[b]
                    if inv.on_hand[fs, q] > 0:
                        out.append([q, 1, camp["eff_depth"], tcamp, 0.0, bid])
        if rng.random() < 0.04:  # impulse add-on
            acc(["ACC_CBL", "ACC_CHG", "AUD_EARBUDS", "ACC_CASE"][int(rng.integers(0, 4))], 1.0)
        return out

    def _update_trackers(self, d, i, final, net, record, disc_share):
        if i < 0:
            return
        cats = {int(self.s_cat[ln[0]]) for ln in final if ln[0] < self.P}
        for k in cats:
            self.age[i, k] = 0.0
            self.lastbuy[i, k] = d
            self.cat_buy_last[i, k] = d
        if not self.active[i]:
            self.active[i] = True
            if record:
                self.life_events.append((i, d, "reactivated", "purchase"))
        self.n_orders[i] += 1
        self.last_order[i] = d
        self.spend[i] += net
        if disc_share is not None and disc_share >= 0.05:
            self.promo_orders[i] += 1
        if record:
            self.order_days[i].append(d)

    # =================================================================== guests
    def _guests(self, d, record):
        rng = self.rng
        cityk = self.st_city
        mult = self.season[d][cityk] * np.maximum(0.2, 1 + self.fest[d][cityk]) * (1 - self.md[d][cityk]) ** (-EPS[None, :]) * self.dow_store[d]
        lam = self.guest_base * mult
        n = rng.poisson(lam)
        for s, k in zip(*np.nonzero(n)):
            for _ in range(n[s, k]):
                idx = self.cat_skus[k]
                subs, _pos = self.cat_subs[k]
                jsub = int(rng.choice(subs))
                res = self._choose(d, -1, int(k), jsub, int(s), False)
                if res is None:
                    continue
                p = res[0]
                if self.inv.on_hand[s, p] <= 0:
                    self.inv.lost_today[s, p] += 1
                    if record:
                        self.lost.append((d, -1, int(s), int(p), int(k), "stock_out_guest"))
                    continue
                self._make_order(d, -1, int(s), "store", [(p, 0.0, -1, -1)], record)

    # =================================================================== campaigns
    def _resolve_scope(self, c, d):
        sc = c["sku_scope"]
        mask = np.zeros(self.PT, bool)
        if sc["type"] == "category":
            for v in sc["values"]:
                mask[self.cat_skus[CAT_INDEX[v]]] = True
        elif sc["type"] == "subcategory":
            for v in sc["values"]:
                mask[self.s_sub == self.sub_names.index(v)] = True
            mask[self.P:] = False
        elif sc["type"] == "skus":
            for v in sc["values"]:
                mask[self.sku_pos[v]] = True
        elif sc["type"] == "eol_in_category":
            for v in sc["values"]:
                idx = self.cat_skus[CAT_INDEX[v]]
                idx = idx[(self.s_eol[idx] <= d + 30) & (self.inv.on_hand[:, idx].sum(0) > 0)]
                mask[idx] = True
        c["scope_mask"] = mask
        c["scope_cats"] = sorted({int(self.s_cat[p]) for p in np.nonzero(mask)[0] if self.s_cat[p] >= 0})
        ot = c["offer_type"]
        if ot in ("pct_off", "bundle_pct", "bank_cashback", "loyalty_points"):
            c["eff_depth"] = c["discount_pct"]
        elif ot == "flat_off":
            ref = np.median(self.list_price[d, np.nonzero(mask[: self.P])[0]]) if mask[: self.P].any() else 20000
            c["eff_depth"] = round(min(0.3, c["flat_inr"] / ref), 4)
        else:
            c["eff_depth"] = 0.0

    def _audience(self, d, rule, cities):
        ca, N = self.ca, self.N
        base = self.present.copy()
        cty = rule.get("cities", cities) if isinstance(rule.get("cities", cities), list) else cities
        if isinstance(cty, list):
            base &= np.isin(ca["city_i"], [CITY_INDEX[c] for c in cty])
        t = rule["type"]
        if t == "broad":
            m = base & (self.n_orders >= rule.get("min_orders", 0))
        elif t == "deal_hunters":
            m = base & (self.n_orders >= rule["min_orders"]) & (self.promo_orders >= rule["min_promo_share"] * np.maximum(self.n_orders, 1))
        elif t == "promo_sensitive":
            m = base & (self.n_orders >= rule["min_orders"]) & (self.promo_orders >= rule["min_promo_share"] * np.maximum(self.n_orders, 1))
        elif t == "category_browsers":
            m = base & (self.last_browse[:, CAT_INDEX[rule["category"]]] >= d - rule["days"])
        elif t == "category_buyers":
            m = base & (self.cat_buy_last[:, CAT_INDEX[rule["category"]]] >= d - rule["days"]) & np.isin(ca["tier"], rule["tiers"])
        elif t == "recent_buyers":
            m = base & (self.cat_buy_last[:, CAT_INDEX[rule["category"]]] >= d - rule["days"])
        elif t == "loyalty":
            m = base & np.isin(ca["tier"], rule["tiers"])
        elif t == "lapsed":
            since = d - self.last_order
            m = base & (since >= rule["min_days"]) & (since <= rule["max_days"])
            if rule.get("categories"):
                ks = [CAT_INDEX[c] for c in rule["categories"]]
                bought = (self.cat_buy_last[:, ks] > -10 ** 5).any(1)
                browsed = (self.last_browse[:, ks] >= d - rule["browse_days"]).any(1)
                m &= bought | browsed
        elif t == "age":
            m = base & np.isin(np.array(AGE_BANDS)[ca["age"]], rule["bands"])
            if rule.get("browse_category"):
                m &= (self.last_browse[:, CAT_INDEX[rule["browse_category"]]] >= d - rule["browse_days"]) | (ca["age"] == 0)
        elif t == "high_value":
            m = base & (self.spend >= rule["min_spend"])
        else:
            raise ValueError(t)
        return np.nonzero(m)[0]

    def _run_campaign(self, d, m):
        rng, ca = self.rng, self.ca
        c = self.camps[m]
        self._resolve_scope(c, d)
        aud = self._audience(d, c["target_rule"], c["cities"])
        reach = {"whatsapp": self.wa & self.consent, "sms": self.consent, "email": self.email & self.consent,
                 "app_push": ca["app"] & self.consent, "in_store": np.ones(self.N, bool)}
        ok = np.zeros(self.N, bool)
        for ch in c["channels"]:
            ok |= reach[ch]
        aud = aud[ok[aud] & ~ca["dnd"][aud]]
        eligible = len(aud)
        if len(aud) > c["cap"]:
            aud = np.sort(rng.choice(aud, c["cap"], replace=False))
        n = len(aud)
        c["eligible"], c["audience_size"] = eligible, n
        if n == 0:
            return
        ctrl = rng.random(n) < 0.10
        chan = np.empty(n, dtype=object)
        for j in range(n):
            for ch in c["channels"]:
                if reach[ch][aud[j]]:
                    chan[j] = ch
                    break
        ks = c["scope_cats"] or [0]
        lam = self._rates(d, aud)
        # fraction of the category's demand that falls inside a narrower SKU scope
        frac = []
        for k in ks:
            idx = self.cat_skus[k]
            live = idx[(self.s_launch[idx] <= d) & (self.s_eol[idx] > d - 60)]
            w = np.exp(self.s_pop[live])
            frac.append(float(w[c["scope_mask"][live]].sum() / max(w.sum(), 1e-9)) if len(live) else 0.0)
        frac = np.array(frac)
        lam_s = (lam[:, ks] * CONV0[ks] * frac[None, :]).sum(1)
        p_ong = 1 - np.prod(1 - np.where(self.ongoing[aud][:, ks] > 0, CONV0[ks] * frac, 0.0), axis=1)
        p_base = 1 - np.exp(-30 * lam_s) * (1 - p_ong)
        exp60 = np.array([sum(1 for x in self.exp_days[i] if x >= d - 60) for i in aud])
        affmax = ca["aff"][aud][:, ks].max(1)
        rel = np.clip((affmax * 12) ** 0.6, 0.1, 2.0) * np.where((self.ongoing[aud][:, ks] > 0).any(1), 1.5, 1.0)
        ot = c["offer_type"]
        dd = c["eff_depth"]
        if ot in ("pct_off", "flat_off"):
            g = 1 - math.exp(-dd / 0.12)
        elif ot == "bundle_pct":
            g = 0.6 * (1 - math.exp(-(dd + 0.08) / 0.12))
        elif ot == "bank_cashback":
            g = 0.85 * (1 - math.exp(-dd / 0.12))
        elif ot == "loyalty_points":
            g = 0.5 * (1 - math.exp(-dd / 0.12))
        elif ot == "free_service":
            g = 0.45
        else:
            g = 0.35
        if ot == "flat_off" and c["free_service_sku"]:
            g = min(1.0, g + 0.25)
        np_off = ot in NONPRICE
        ps, pr, fk = ca["price_sens"][aud], ca["promo_resp"][aud], ca["fatigue_k"][aud]
        loyal = np.isin(ca["tier"][aud], ["gold", "elite"])
        if np_off:
            base = U0 * ca["nonprice"][aud] * g * (1.3 - ps) * np.where(loyal, 1.5, 1.0)
        else:
            base = U0 * pr * g * (1 + ps)
        base = base * rel * np.exp(-fk * exp60)
        ut = ca["utype"][aud]
        tm = np.select([ut == 0, ut == 1, ut == 2, ut == 3], [1.0, 0.6 if np_off else 0.08, 0.1, -0.5])
        eff = base * tm
        opened = ~ctrl & (rng.random(n) < np.array([OPEN_RATE[x] for x in chan]) * np.exp(-0.07 * exp60))
        q = np.clip(eff * (1 - p_base), 0, 0.6)
        induced = opened & (eff > 0) & (rng.random(n) < q)
        s_sd = np.where(ut == 3, np.minimum(0.9, 0.5 * base / np.maximum(p_base, 0.005)), 0.0)
        p_treat = np.where(ut == 3, p_base * (1 - s_sd), p_base + q)
        clicked = opened & (rng.random(n) < np.clip(0.12 + 3 * np.maximum(eff, 0), 0, 0.8))
        p_unsub = 0.0015 + 0.004 * np.maximum(0, exp60 - 3) * (fk / 0.165) + np.where(ut == 3, 0.01, 0.0)
        unsub = ~ctrl & (rng.random(n) < p_unsub)
        # apply effects
        dur = c["end_day"] - d + 1
        ind_ids = aud[induced]
        if len(ind_ids):
            kk = []
            subs = []
            for i in ind_ids:
                w = ca["aff"][i, ks] * np.maximum(frac, 1e-6)
                k = ks[int(rng.choice(len(ks), p=w / w.sum()))]
                kk.append(k)
                scope_idx = self.cat_skus[k][c["scope_mask"][self.cat_skus[k]]]
                subs.append(int(self.s_sub[scope_idx[int(rng.integers(0, len(scope_idx)))]]) if len(scope_idx) else 0)
            L = np.minimum(rng.integers(1, 11, len(ind_ids)), max(dur - 1, 0))
            self._new_journeys(d, ind_ids, np.array(kk), kind=1, camp=m, restrict=m, end=d + L, sub=np.array(subs, np.int16))
        for j, i in enumerate(aud):
            if ctrl[j]:
                continue
            self.exp_days[i].append(d)
            if opened[j]:
                self.offers[i].append(m)
                if ut[j] == 3:
                    self.supp_until[i] = d + 30
                    self.supp_cats[i] = False
                    self.supp_cats[i, ks] = True
                    self.supp_p[i] = s_sd[j]
                    self.churn_mult[i], self.churn_mult_until[i] = 1.3, d + 60
                elif c["objective"] in ("reactivation", "loyalty"):
                    tf = {0: 1.0, 1: 1.0, 2: 0.5}[int(ut[j])]
                    self.churn_mult[i] = 1 - 0.7 * ca["ret_sens"][i] * tf
                    self.churn_mult_until[i] = d + 180
                    if not self.active[i] and rng.random() < 0.6 * ca["ret_sens"][i] * tf:
                        self.active[i] = True
                        self.life_events.append((int(i), d, "reactivated", "campaign"))
            if unsub[j]:
                self.consent[i] = self.wa[i] = self.email[i] = False
                self.unsub_day[i] = d
        cid = c["campaign_id"]
        for j, i in enumerate(aud):
            self.exposures.append(dict(campaign_id=cid, m=m, cust=int(i), group="C" if ctrl[j] else "T", channel=chan[j], sent_day=d,
                                       opened=bool(opened[j]), clicked=bool(clicked[j]), unsubscribed=bool(unsub[j]),
                                       exposures_60d=int(exp60[j]), p_ctrl=float(p_base[j]), p_treat=float(p_treat[j]),
                                       reach_prob=float(OPEN_RATE[chan[j]] * math.exp(-0.07 * exp60[j])), induced=bool(induced[j]),
                                       uplift_type=UPLIFT_TYPES[int(ut[j])], fatigue_mult=float(math.exp(-fk[j] * exp60[j]))))

    # =================================================================== stories
    def _story_setup(self):
        inv = self.inv
        pb = self.di(stories.PUNE_BLOCK_FROM)
        eta = self.di(stories.PUNE_ETA)
        for sid in ("PUN-01", "PUN-02"):
            s = self.store_ids.index(sid)
            for sku in stories.S1_SKUS:
                inv.blocked_until[(s, self.sku_pos[sku])] = (pb, eta)

    def _story_hooks(self, d):
        dt = self.dates[d]
        inv = self.inv
        if dt == stories.S1_START:
            for c in stories.S1_CITIES:
                self.story_cc[CITY_INDEX[c], CAT_INDEX["TV"]] = 1.45
        if dt == stories.S2_BULK_DAY:
            p = self.sku_pos[stories.S2_SKU]
            for sid, q in stories.S2_STORES.items():
                s = self.store_ids.index(sid)
                inv.create_po(s, p, q, d - 30, po_type="bulk_buy", eta_override=d)
                inv.no_reorder.add((s, p))
            inv.receive_due(d)
        if dt == stories.S2_TRIM_DAY:
            p = self.sku_pos[stories.S2_SKU]
            stores = [self.store_ids.index(s) for s in stories.S2_STORES]
            total = int(inv.on_hand[stores, p].sum())
            r = float(np.mean(inv.daily_sales[-28:], axis=0)[stores, p].sum()) if inv.daily_sales else 0.0
            excess = total - int(round(212 + r * 18))
            for s in stores:
                if excess <= 0:
                    break
                take = min(excess, int(inv.on_hand[s, p]) - 40)
                if take > 0:
                    excess -= inv.transfer_out(s, p, take, d, kind="return_to_dc")
        if dt == stories.S6_DAY:
            for sid in ("CHE-01", "CHE-02"):
                s = self.store_ids.index(sid)
                for p in self.cat_skus[CAT_INDEX["AC"]]:
                    if self.s_launch[p] <= d < self.s_eol[p]:
                        self._adjust_cover(d, s, p, 70, horizon=25, allow_down=False, kind="allocation")
        if dt == stories.MUM03_DAY:
            s = self.store_ids.index("MUM-03")
            for sku, extra in (("TV-AUR-55U7", 75), ("TV-AUR-55Q8", 25)):
                p = self.sku_pos[sku]
                inv.create_po(s, p, extra, d - 12, po_type="allocation", eta_override=d)
                inv.receive_due(d)
        if dt == stories.S7_DAY:
            for s in self.city_stores[CITY_INDEX["KOL"]]:
                for k in ("TV", "REF"):
                    for p in self.cat_skus[CAT_INDEX[k]]:
                        if self.ranged[s, p] and self.s_launch[p] <= d < self.s_eol[p]:
                            self._adjust_cover(d, s, p, 38, horizon=10, allow_down=False, kind="allocation")
        if dt == stories.S8_DAY:
            self._plant_s8(d)
        if dt == stories.FINAL_ALLOC_DAY:
            for sid in ("HYD-01", "HYD-02", "HYD-03"):
                for sku in stories.S1_SKUS:
                    self._adjust_cover(d, self.store_ids.index(sid), self.sku_pos[sku], 53, horizon=1, allow_down=True, kind="allocation")
            for sid in ("PUN-01", "PUN-02"):
                for sku in stories.S1_SKUS:
                    self._adjust_cover(d, self.store_ids.index(sid), self.sku_pos[sku], 8, horizon=1, allow_down=True, kind="transfer_out",
                                       to_store="PUN-03")
            s = self.store_ids.index("MUM-03")
            p = self.sku_pos["TV-AUR-55U7"]
            r = self._r28(s, p)
            need = int(math.ceil(30 * r + 70 - inv.on_hand[s, p]))
            if need > 0:
                inv.create_po(s, p, need, d - 12, po_type="allocation", eta_override=d)
                inv.receive_due(d)

    def _r28(self, s, p):
        ds = self.inv.daily_sales[-28:]
        return float(sum(x[s, p] for x in ds)) / 28.0 if ds else float(self.inv.ewma[s, p])

    def _adjust_cover(self, d, s, p, target_days, horizon, allow_down, kind, to_store=None):
        inv = self.inv
        r = max(self._r28(s, p), 0.04)
        target = int(round(r * (target_days + horizon)))
        cur = int(inv.on_hand[s, p])
        if target > cur:
            inv.create_po(s, p, target - cur, d - 10, po_type="allocation", eta_override=d)
            inv.receive_due(d)
        elif allow_down and cur > target:
            inv.transfer_out(s, p, cur - target, d, kind="inter_store_transfer" if to_store else "return_to_dc", to_store=to_store)

    def _plant_s8(self, d):
        """At-risk (observable rule) customers with washing-machine affinity get a WM intent spike."""
        ca = self.ca
        gaps_all = []
        for od in self.order_days:
            if len(od) >= 2:
                gaps_all.extend(np.diff(od).tolist())
        pop_gap = float(np.median(gaps_all)) if gaps_all else 120.0
        cand = []
        for i in range(self.N):
            od = self.order_days[i]
            if not od:
                continue
            exp_gap = float(np.median(np.diff(od))) if len(od) >= 2 else pop_gap
            exp_gap = max(exp_gap, 30.0)
            since = d - od[-1]
            if 1.5 * exp_gap <= since + 14 < 3 * exp_gap and since + 14 <= 365:
                cand.append(i)
        cand = np.array(cand, int)
        score = ca["aff"][cand, CAT_INDEX["WM"]] + 0.02 * self.rng.random(len(cand))
        pick = cand[np.argsort(-score, kind="stable")[:1900]]
        self.boost_wm_until[pick] = d + 14
        self.age[pick, CAT_INDEX["WM"]] = 1.2 * self.cycle[CAT_INDEX["WM"]]
        self.active[pick] = True
        self.s8_selected = pick
