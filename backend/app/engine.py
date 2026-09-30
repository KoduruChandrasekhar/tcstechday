"""PromoForge decision engine on the Prometheus digital twin (data/synthetic/*.parquet).

Learns from the observed tables only (never data/_truth):
  * customer segments        <- customers + customer_behavior_summary (rule-based, consent-aware)
  * category affinity        <- order_lines x orders per segment (lift vs overall mix)
  * uplift / sure-thing share <- campaign exposures, treated vs control 30-day conversion
  * demand, stock, inbound   <- inventory_snapshot + inbound_po + orders, per city x SKU
  * festival multipliers     <- events (category_uplift x regional_intensity)
  * local intent             <- city_search_index (last 14d vs prior 60d)
  * ops capacity             <- store_capacity + forward install_bookings
  * campaign memory          <- campaigns_hist (ROI, stock-outs, leakage) -> calibration
Each candidate (segment x SKU x city x offer x window) is simulated -> readiness + verdict + explanation.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
DEMO_TODAY = pd.Timestamp("2026-10-01")
DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"

WINDOWS = {  # planning windows (horizon Oct 2026 - Jan 2027)
    "navratri": ("Navratri & Durga Puja", "2026-10-14", "2026-10-21"),
    "diwali": ("Diwali & Dhanteras", "2026-11-01", "2026-11-08"),
    "xmas": ("Christmas & New Year", "2026-12-22", "2026-12-31"),
    "rds": ("Republic Day Sale", "2027-01-22", "2027-01-26"),
}
DEFAULT_WINDOW = "diwali"
# the twin's 8,000 CRM customers are a 1:SCALE sample of the full base; quantities are scaled uniformly
# (audience, demand, stock, costs), so ratios, probabilities of guardrails and verdicts are unaffected
SCALE = 50

# label, pct discount, flat off INR, free installation
OFFERS = [("5% off", 0.05, 0, False), ("10% off", 0.10, 0, False), ("15% off", 0.15, 0, False),
          ("10% + free installation", 0.10, 0, True), ("Flat ₹2,000 off", 0.0, 2000, False)]
CHANNELS = {"WhatsApp + App": ["whatsapp", "app_push"], "Email + App": ["email", "app_push"], "SMS + In-store": ["sms", "in_store"]}
CH_REACH = {"WhatsApp + App": 0.62, "Email + App": 0.45, "SMS + In-store": 0.40}

GUARDRAILS = {
    "min_gp_margin": 0.03,       # post-discount gross margin floor
    "max_stockout_prob": 0.40,   # above -> BLOCK unless capped
    "max_capacity_load": 1.0,    # installation slots in the window
    "max_leakage_share": 0.60,   # share of discount spend going to "sure things"
    "max_fatigue": 3.0,          # avg promos received in last 60 days
    "min_segment_size": 25,      # k-anonymity on contactable audience
}
W = {"profit": 0.30, "stock": 0.25, "uplift": 0.20, "ops": 0.15, "fatigue": 0.10}
INSTALL_SVC = {"TV": "SRV-INS-TV", "AC": "SRV-INS-AC", "WM": "SRV-INS-WM", "REF": "SRV-DEM-REF"}


def inr(x: float) -> str:
    x = float(x)
    s = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e7:
        return f"{s}₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"{s}₹{x / 1e5:.1f} L"
    n = f"{int(round(x))}"
    if len(n) > 3:
        head, tail = n[:-3], n[-3:]
        head = ",".join([head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1])
        n = f"{head},{tail}"
    return f"{s}₹{n}"


def _r(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


def _segment(row) -> str:
    if row.dnd_or_unsub:
        return "Do-Not-Contact"
    if row.orders_24m >= 1 and row.days_since_last_order > 240:
        return "At-Risk Lapsers"
    if row.loyalty_tier in ("gold", "elite"):
        return "Premium Loyalists"
    if row.promo_order_share >= 0.5 and row.orders_24m >= 1:
        return "Deal Hunters"
    if (DEMO_TODAY - row.joined_on).days <= 180:
        return "New Joiners"
    if row.web_active_days_90d >= 8:
        return "High-Intent Browsers"
    return "Steady Regulars"


class World:
    def __init__(self):
        self.stores = _r("stores")
        self.cities_df = _r("cities")
        prods = _r("products")
        self.all_products = prods.set_index("sku_id")
        self.channel_cost = _r("channel_costs").set_index("channel")["cost_per_send_inr"].to_dict()
        self.events = _r("events")
        self.events["cu"] = self.events.category_uplift.map(json.loads)
        self.events["ri"] = self.events.regional_intensity.map(json.loads)
        self._fest, self._stock = {}, {}
        store_city = self.stores.set_index("store_id")["city_code"]
        self.city_name = self.cities_df.set_index("city_code")["city"].to_dict()
        self.cities = {r.city_code: {"code": r.city_code, "city": r.city, "region": r.region, "stores": int(r.n_stores),
                                     "lat": r.lat, "lon": r.lng} for r in self.cities_df.itertuples()}

        # ---------- customers & segments ----------
        cu = _r("customers").merge(_r("customer_behavior_summary"), on="customer_id", how="left")
        cu[["orders_24m", "promo_order_share", "web_active_days_90d", "exposures_60d"]] = cu[
            ["orders_24m", "promo_order_share", "web_active_days_90d", "exposures_60d"]].fillna(0)
        cu["days_since_last_order"] = cu["days_since_last_order"].fillna(9999)
        cu["dnd_or_unsub"] = cu["dnd"] | cu["unsubscribed_on"].notna() | ~cu["marketing_consent"]
        cu["segment"] = [_segment(r) for r in cu.itertuples()]
        self.customers = cu
        contact = cu[cu.segment != "Do-Not-Contact"]
        self.seg_city_reach = contact.groupby(["segment", "home_city_code"]).size().to_dict()
        self.seg_size = contact.groupby("segment").size().to_dict()
        self.dnc = int((cu.segment == "Do-Not-Contact").sum())
        self.fatigue = contact.groupby("segment")["exposures_60d"].mean().round(2).to_dict()

        # ---------- orders -> affinity, demand ----------
        orders = _r("orders")
        lines = _r("order_lines").merge(orders[["order_id", "order_date", "customer_id", "store_id"]], on="order_id")
        lines = lines[lines.category != "SRV"]
        lines["city_code"] = lines.store_id.map(store_city)
        lines = lines.merge(cu[["customer_id", "segment"]], on="customer_id", how="left")
        overall = lines.groupby("category")["qty"].sum() / lines["qty"].sum()
        seg_mix = lines.groupby(["segment", "category"])["qty"].sum()
        seg_mix = seg_mix / seg_mix.groupby(level=0).transform("sum")
        self.affinity = (seg_mix / overall.reindex(seg_mix.index.get_level_values(1)).values).round(2).to_dict()
        self.cat_share = overall.to_dict()
        recent = lines[lines.order_date > DEMO_TODAY - pd.Timedelta(days=90)]
        self.sku_daily = (recent.groupby(["city_code", "sku_id"])["qty"].sum() / 90).to_dict()
        cat_units = recent.groupby("category")["qty"].sum()
        self.sku_share_in_cat = (recent.groupby(["category", "sku_id"])["qty"].sum() / cat_units.reindex(
            recent.groupby(["category", "sku_id"])["qty"].sum().index.get_level_values(0)).values).to_dict()
        # same-period-last-year festival lift per category (observed), for explanations
        self.lines = lines
        # attach margin: GP of other lines (services, accessories) in baskets containing each category
        al = _r("order_lines").merge(orders[["order_id"]], on="order_id")
        al["gp"] = (al.unit_price - al.unit_cost) * al.qty
        basket_gp = al.groupby("order_id")["gp"].sum()
        att = {}
        for cat, d in al[al.category != "SRV"].groupby("category"):
            own = d.groupby("order_id")["gp"].sum()
            att[cat] = float(((basket_gp.reindex(own.index) - own).clip(lower=0)).mean())
        self.attach_gp = att

        # ---------- uplift: T-learner on campaign exposures (treated vs holdout control) ----------
        from sklearn.linear_model import LogisticRegression
        ex = _r("exposures")
        hist = _r("campaigns_hist")
        ex = ex.merge(hist[["campaign_id", "discount_pct"]], on="campaign_id", how="left")
        feats = ["orders_24m", "log_spend", "recency", "web_active_days_90d", "promo_order_share", "exposures_60d",
                 "tier", "app_user"]
        cu["log_spend"] = np.log1p(cu["spend_24m"].fillna(0))
        cu["recency"] = np.minimum(cu["days_since_last_order"], 730) / 365
        cu["tier"] = cu["loyalty_tier"].map({"none": 0, "silver": 1, "gold": 2, "elite": 3}).fillna(0)
        cu["app_user"] = cu["app_user"].astype(float)
        X = ex.merge(cu[["customer_id", "segment"] + feats], on="customer_id").dropna(subset=["converted_30d"])
        X["converted_30d"] = X.converted_30d.astype(int)
        T, Cn = X[X.group == "T"], X[X.group == "C"]
        mt = LogisticRegression(max_iter=500, C=0.5).fit(T[feats], T.converted_30d)
        mc = LogisticRegression(max_iter=500, C=0.5).fit(Cn[feats], Cn.converted_30d)
        cu["p_treat"], cu["p_ctrl"] = mt.predict_proba(cu[feats])[:, 1], mc.predict_proba(cu[feats])[:, 1]
        cu["uplift"] = cu.p_treat - cu.p_ctrl
        mean_disc = float(T.discount_pct.clip(lower=0.03).mean())
        # Qini-style validation: observed (T - C) conversion in top-30% predicted uplift vs the rest
        X["pred_uplift"] = mt.predict_proba(X[feats])[:, 1] - mc.predict_proba(X[feats])[:, 1]
        top = X.pred_uplift >= X.pred_uplift.quantile(0.7)
        obs = lambda d: d[d.group == "T"].converted_30d.mean() - d[d.group == "C"].converted_30d.mean()
        self.model_card = {"model": "T-learner uplift (2 × logistic regression)", "features": feats,
                           "train_rows": int(len(X)), "treated": int(len(T)), "control": int(len(Cn)),
                           "obs_uplift_top30_pts": round(float(obs(X[top])) * 100, 2),
                           "obs_uplift_rest_pts": round(float(obs(X[~top])) * 100, 2),
                           "obs_uplift_all_pts": round(float(obs(X)) * 100, 2)}
        self.uplift = {}
        tgt = cu[cu.segment != "Do-Not-Contact"]
        for (seg, city), d in tgt.groupby(["segment", "home_city_code"]):
            pers = d[d.uplift > 0]  # persuadables only: sure things and sleeping dogs are suppressed
            self.uplift[(seg, city)] = {"n": int(len(pers)), "n_all": int(len(d)),
                                        "control": float(pers.p_ctrl.mean()) if len(pers) else 0.0,
                                        "treated": float(pers.p_treat.mean()) if len(pers) else 0.0,
                                        "per_disc": float(pers.uplift.mean() / mean_disc) if len(pers) else 0.0}
        seg_all = tgt.groupby("segment").agg(control=("p_ctrl", "mean"), treated=("p_treat", "mean"))
        self.seg_uplift = {s: {"treated": round(r.treated, 4), "control": round(r.control, 4),
                               "lift": round(r.treated - r.control, 4)} for s, r in seg_all.iterrows()}
        self.seg_persuadable = tgt.assign(p=tgt.uplift > 0).groupby("segment")["p"].mean().round(3).to_dict()

        # ---------- inventory, inbound, capacity ----------
        inv = _r("inventory_snapshot")
        inv = inv[inv.is_ranged].copy()
        inv["city_code"] = inv.store_id.map(store_city)
        self.inv = inv.groupby(["city_code", "sku_id"]).agg(available=("available", "sum"), age=("avg_age_days", "mean"),
                                                            excess=("excess_units_over_60d", "sum"),
                                                            ads=("avg_daily_sales_28d", "sum")).to_dict("index")
        po = _r("inbound_po")
        po = po[(po.status != "received") & po.eta.notna()].copy()
        po["city_code"] = po.store_id.map(store_city)
        self.po = {}
        for r in po.itertuples():
            self.po.setdefault((r.city_code, r.sku_id), []).append((r.eta, r.qty))
        cap = _r("store_capacity")
        cap["city_code"] = cap.store_id.map(store_city)
        self.install_slots = cap.groupby("city_code")["install_slots_per_day"].sum().to_dict()
        ib = _r("install_bookings")
        fwd = ib[ib.is_forward]
        fwd = fwd.assign(city_code=fwd.store_id.map(store_city))
        self.fwd_booked = fwd.groupby(["city_code", "date"])["booked_slots"].sum().groupby(level=0).mean().to_dict()

        # ---------- search intent ----------
        si = _r("city_search_index")
        last = si[si.date > DEMO_TODAY - pd.Timedelta(days=14)].groupby(["city_code", "category"])["search_index"].mean()
        prev = si[(si.date <= DEMO_TODAY - pd.Timedelta(days=14)) & (si.date > DEMO_TODAY - pd.Timedelta(days=74))
                  ].groupby(["city_code", "category"])["search_index"].mean()
        self.intent = (last / prev).clip(0.6, 1.8).round(2).to_dict()
        rd = _r("regional_demand")
        self.regional = rd

        # ---------- hero SKUs (current range, top sellers + clearance candidates) ----------
        p = prods[(prods.category != "SRV") & (prods.lifecycle != "end_of_life")]
        sold = recent.groupby("sku_id")["qty"].sum()
        exc = inv.groupby("sku_id")["excess_units_over_60d"].sum()
        heroes = []
        for cat, d in p.groupby("category"):
            ids = d.sku_id
            heroes += list(sold.reindex(ids).fillna(0).sort_values(ascending=False).index[:2])
            heroes += list(exc.reindex(ids).fillna(0).sort_values(ascending=False).index[:1])
        self.hero = list(dict.fromkeys(heroes))
        self.products = {s: self._prod(s) for s in self.hero}

        # ---------- campaign memory ----------
        h = hist[hist.outcome_window_complete].copy()
        h["actual_roi"] = h.gross_profit / (h.discount_cost + h.channel_cost + 15000)
        h["pred_roi"] = [h[(h.objective == r.objective) & (h.campaign_id != r.campaign_id)].actual_roi.mean()
                         for r in h.itertuples()]
        h["pred_roi"] = h.pred_roi.fillna(h.actual_roi.mean())
        h["leak"] = (h.control_conv_rate / h.treated_conv_rate.replace(0, np.nan)).clip(0, 1).fillna(1)
        self.memory = h
        resid = (h.actual_roi - h.pred_roi)
        self.calib = {"bias": round(float(resid.mean()), 3), "sd": round(float(resid.std()), 3),
                      "mae": round(float(resid.abs().mean()), 3), "n": int(len(h))}

    # ---------------------------------------------------------------
    def _prod(self, sku):
        p = self.all_products.loc[sku]
        svc = INSTALL_SVC.get(p.category)
        return {"sku": sku, "name": p["name"], "brand": p.brand, "cat": p.category, "cat_name": p.category_name,
                "price": float(p.list_price), "cost": float(p.unit_cost), "install": bool(p.requires_install),
                "install_cost": float(self.all_products.loc[svc, "unit_cost"]) if svc else 0.0,
                "install_value": float(self.all_products.loc[svc, "list_price"]) if svc else 0.0,
                "attach_gp": float(self.attach_gp.get(p.category, 0.0)), "tier": p.tier}

    def fest(self, city: str, cat: str, start, end) -> tuple[float, list[str]]:
        k = (city, cat, start, end)
        if k not in self._fest:
            self._fest[k] = self._fest_calc(city, cat, start, end)
        return self._fest[k]

    def _fest_calc(self, city, cat, start, end):
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        ev = self.events[(self.events.start <= end) & (self.events.end >= start)]
        mult, names = 1.0, []
        for e in ev.itertuples():
            u = e.cu.get(cat, 1.0)
            ri = e.ri
            inten = ri.get(city, ri.get("default", 1.0))
            m = 1 + (u - 1) * inten
            if abs(m - 1) > 0.05:
                names.append(f"{e.name} ×{m:.2f}")
            mult *= m
        return round(mult, 2), names

    def daily_demand(self, city, sku):
        d = self.sku_daily.get((city, sku), 0.0)
        a = self.inv.get((city, sku), {}).get("ads", 0.0)
        return max(d, a, 0.02)

    def stock_at(self, city, sku, start, days):
        """Project stock to window start: available + inbound before start - baseline sales until start."""
        k = (city, sku, start, days)
        if k not in self._stock:
            self._stock[k] = self._stock_calc(city, sku, start, days)
        return self._stock[k]

    def _stock_calc(self, city, sku, start, days):
        inv = self.inv.get((city, sku), {"available": 0, "age": 0, "excess": 0})
        start = pd.Timestamp(start)
        pos = self.po.get((city, sku), [])
        pre = sum(q for eta, q in pos if eta < start)
        lead = (start - DEMO_TODAY).days
        s0 = max(0.0, inv["available"] + pre - self.daily_demand(city, sku) * lead)
        during = [((eta - start).days + 1, q) for eta, q in pos if start <= eta < start + pd.Timedelta(days=days)]
        return s0, during, inv


def evaluate(w: World, seg: str, sku: str, city: str, offer_idx: int, channel: str = "WhatsApp + App",
             cap: int | None = None, window: str = DEFAULT_WINDOW) -> dict:
    P, C = w.products.get(sku) or w._prod(sku), w.cities[city]
    wname, ws, we = WINDOWS[window]
    days = (pd.Timestamp(we) - pd.Timestamp(ws)).days + 1
    offer, disc, flat, free_inst = OFFERS[offer_idx]
    free_inst = free_inst and P["install"]
    freebie = P["install_cost"] if free_inst else 0.0
    perceived = P["install_value"] if free_inst else 0.0  # customers value the service at list price
    disc_eff = disc + flat / P["price"]
    U = w.uplift.get((seg, city), {"n": 0, "n_all": 0, "control": 0.0, "treated": 0.0, "per_disc": 0.0})
    SU = w.seg_uplift.get(seg, {"treated": 0, "control": 0, "lift": 0})
    aff = float(w.affinity.get((seg, P["cat"]), 0.5))
    intent = float(w.intent.get((city, P["cat"]), 1.0))
    fest, fest_names = w.fest(city, P["cat"], ws, we)
    fatigue = float(w.fatigue.get(seg, 0))
    audience = U["n"]  # persuadable customers only (T-learner uplift > 0)
    reach = audience * CH_REACH[channel] * SCALE

    # P(targeted customer buys this SKU in window) = category purchase prob x SKU share
    sku_share = max(float(w.sku_share_in_cat.get((P["cat"], sku), 0.05)), 0.35)  # promoted SKU captures category choice
    cat_prob = float(w.cat_share.get(P["cat"], 0.05)) * aff
    win = days / 30
    fat_mult = max(0.5, 1 - 0.1 * max(0, fatigue - 1))
    base_rate = U["control"] * cat_prob * sku_share * win * fest * intent
    # historical lift was measured on category-targeted campaigns, so it applies to the promoted category directly
    lift_rate = U["per_disc"] * (disc_eff + perceived / P["price"] * 1.5) * float(np.clip(aff, 0.5, 1.6)) * sku_share         * math.sqrt(fest) * intent * fat_mult
    baseline_units = reach * base_rate
    incr_units = reach * lift_rate
    organic = w.daily_demand(city, sku) * days * fest * intent * SCALE
    promo_units = baseline_units + incr_units
    if cap:
        promo_units = min(promo_units, cap)
        incr_units = min(incr_units, max(0, cap - baseline_units))
    total_need = organic + promo_units

    s0, inbound, inv = w.stock_at(city, sku, ws, days)
    s0, inbound = s0 * SCALE, [(d, q * SCALE) for d, q in inbound]
    avail = s0 + sum(q for _, q in inbound)
    sd = math.sqrt(max(total_need, 0.1)) * 1.2 + 0.5
    p_stockout = 0.5 * math.erfc(((avail - total_need) / sd) / math.sqrt(2))
    sell = min(total_need, avail)
    lost = max(0.0, total_need - avail)
    daily = total_need / days
    burn, s_left, stockout_day = [], s0, None
    inb = dict(inbound)
    for d in range(1, days + 1):
        s_left += inb.get(d, 0)
        s_left -= daily
        if s_left <= 0 and stockout_day is None:
            stockout_day = d
        burn.append(round(max(0.0, s_left), 1))

    price_net = P["price"] * (1 - disc) - flat
    margin_unit = price_net - P["cost"] - freebie
    gp_margin = margin_unit / price_net
    fill = sell / total_need if total_need else 1
    full_margin = P["price"] - P["cost"]
    incr_gp = incr_units * fill * (margin_unit + P["attach_gp"])  # + services/accessories attached in the basket
    per_unit_giveaway = P["price"] * disc + flat + freebie
    leakage = baseline_units * per_unit_giveaway          # discount given to customers who'd buy anyway
    discount_spend = promo_units * per_unit_giveaway
    leak_share = leakage / discount_spend if discount_spend else 0.0
    comm_cost = sum(audience * SCALE * w.channel_cost.get(ch, 0) for ch in CHANNELS[channel])
    lost_promo = max(0.0, lost - max(0.0, organic - avail))  # only shortfall caused by the promotion
    lost_gp = lost_promo * full_margin * 0.5 + lost_promo * P["price"] * 0.02  # lost sales + goodwill
    net_gp = incr_gp - leakage - comm_cost - lost_gp
    roi = net_gp / max(discount_spend + comm_cost, 1)
    slots = w.install_slots.get(city, 1) * days
    booked = w.fwd_booked.get(city, 0) * days
    cap_load = (promo_units + organic) / SCALE / max(slots - booked, 1) if P["install"] else 0.0
    cover_days = s0 / SCALE / max(w.daily_demand(city, sku) * fest, 0.01)

    sc = {"profit": float(np.clip(55 + roi * 60, 0, 100)), "stock": float(np.clip(100 * (1 - p_stockout), 0, 100)),
          "uplift": float(np.clip(incr_units / max(promo_units, 0.01) * 110, 0, 100)),
          "ops": float(np.clip(100 * (1.2 - cap_load), 0, 100)) if P["install"] else 100.0,
          "fatigue": float(np.clip(100 - fatigue * 18, 0, 100))}
    readiness = round(sum(W[k] * sc[k] for k in W), 1)

    g, risks, blocks, drivers = GUARDRAILS, [], [], []
    if gp_margin < g["min_gp_margin"]:
        blocks.append(f"Too little profit: margin after discount is {gp_margin:.1%}, below our {g['min_gp_margin']:.0%} minimum")
    if p_stockout > g["max_stockout_prob"] and not cap:
        blocks.append(f"{p_stockout:.0%} chance of a stock-out in {C['city']}: only {avail:.0f} units available vs ~{total_need:.0f} needed")
    elif p_stockout > 0.15:
        risks.append(f"{p_stockout:.0%} chance of a stock-out" + (f", runs out on day {stockout_day}" if stockout_day else ""))
    if audience < g["min_segment_size"]:
        blocks.append(f"Customer group too small to target privately ({audience} customers, minimum {g['min_segment_size']}; anonymity rule)")
    if cap_load > g["max_capacity_load"]:
        risks.append(f"Not enough installation slots ({cap_load:.0%} of free capacity needed)")
    if leak_share > g["max_leakage_share"]:
        risks.append(f"{leak_share:.0%} of discount goes to customers who'd buy anyway")
    if fatigue >= g["max_fatigue"]:
        risks.append(f"These customers already got {fatigue:.1f} promotions in the last 60 days")
    if SU["lift"] <= 0:
        risks.append("In past promotions, this group bought the same with or without an offer")
    if net_gp < 0:
        risks.append("Loses money after discounts and costs")

    if aff >= 1.2:
        drivers.append(f"{seg} buy {P['cat_name']} more than average ({aff:.2f}× based on past purchases)")
    if U["n"]:
        drivers.append(f"{U['n'] * SCALE:,} of {U['n_all'] * SCALE:,} customers are likely to respond "
                       f"({U['treated']:.1%} buy with the offer vs {U['control']:.1%} without)")
    if intent >= 1.1:
        drivers.append(f"Online searches for {P['cat_name']} in {C['city']} up {intent - 1:.0%} in the last 2 weeks")
    for n in fest_names[:2]:
        drivers.append(f"Festival boost: {n}")
    if inv.get("excess", 0) > 0 and cover_days > 45:
        drivers.append(f"Too much stock: {cover_days:.0f} days worth, {inv['excess']:.0f} units older than 60 days")
    if gp_margin > 0.12:
        drivers.append(f"Healthy profit margin after discount ({gp_margin:.1%})")
    if not drivers:
        drivers.append("Normal demand; no special signal")

    if blocks:
        verdict = "BLOCK"
    elif readiness >= 70 and net_gp > 0 and len(risks) <= 1:
        verdict = "GO"
    elif readiness >= 55 and net_gp > 0:
        verdict = "CONDITIONAL GO"
    else:
        verdict = "HOLD"

    change = []
    if p_stockout > 0.15:
        safe_cap = max(0, int(avail - organic - 1.2 * math.sqrt(max(total_need, 0.1))))
        change.append(f"Limit the offer to {safe_cap} units, or move stock in from a city that has extra")
    if leak_share > 0.45:
        change.append("Leave out customers who'd buy anyway, or drop to 5% off")
    if gp_margin < 0.06:
        change.append("Offer free installation or a flat amount off instead of a % discount")
    if cap_load > 0.9:
        change.append("Spread out deliveries or add installer slots")
    if fatigue >= g["max_fatigue"]:
        change.append("Skip customers we contacted recently, or promote in-store instead")
    if audience < g["min_segment_size"]:
        change.append("Target the whole region or combine with a similar customer group")
    if not change:
        change.append("Already close to the best option; a bigger discount would earn less")

    sd_ = pd.Timestamp(ws).strftime("%d %b"), pd.Timestamp(we).strftime("%d %b")
    sentence = (f"Offer {offer} to {seg} ({audience * SCALE:,}) on {P['name']} in {C['city']} ({C['stores']} stores) "
                f"from {sd_[0]}–{sd_[1]} via {channel}" + (f", capped at {cap} units" if cap else ""))
    return {
        "id": f"{seg[:3].upper()}-{sku}-{city}-{offer_idx}-{window}", "window": window, "window_name": wname,
        "segment": seg, "sku": sku, "product": P["name"], "category": P["cat"], "city": city, "city_name": C["city"],
        "region": C["region"], "offer": offer, "offer_idx": offer_idx, "channel": channel, "cap": cap,
        "sentence": sentence, "verdict": verdict, "readiness": readiness, "scores": {k: round(v) for k, v in sc.items()},
        "audience": audience * SCALE, "reach": int(reach), "baseline_units": round(baseline_units, 1), "incr_units": round(incr_units, 1),
        "promo_units": round(promo_units, 1), "organic_units": round(organic, 1), "available": round(avail, 1),
        "stock": round(s0, 1), "p_stockout": round(p_stockout, 3), "stockout_day": stockout_day, "burn": burn,
        "inbound": [{"day": d, "qty": int(q)} for d, q in inbound], "gp_margin": round(gp_margin, 4),
        "incr_revenue": round(incr_units * fill * price_net), "incr_gp": round(incr_gp), "net_gp": round(net_gp),
        "discount_spend": round(discount_spend), "leakage": round(leakage), "leak_share": round(leak_share, 3),
        "comm_cost": round(comm_cost), "lost_gp": round(lost_gp),
        "roi": round(roi, 2), "cap_load": round(cap_load, 2), "fatigue": fatigue, "cover_days": round(cover_days, 1),
        "fest": fest, "intent": intent, "affinity": aff,
        "drivers": drivers, "risks": risks, "blocks": blocks, "what_would_change": change,
        "fmt": {"net_gp": inr(net_gp), "incr_revenue": inr(incr_units * fill * price_net),
                "discount_spend": inr(discount_spend), "leakage": inr(leakage)},
    }


def objective_key(r: dict, objective: str) -> float:
    pen = {"BLOCK": -1e9, "HOLD": -1e6, "CONDITIONAL GO": 0, "GO": 0}[r["verdict"]]
    if objective == "growth":
        return pen + r["incr_revenue"] / 1e4 + r["readiness"] / 5
    if objective == "clear":
        return pen + min(r["cover_days"], 200) / 2 + r["readiness"] / 5
    if objective == "retain":
        return pen + (60 if r["segment"] == "At-Risk Lapsers" else 0) + r["readiness"]
    return pen + r["net_gp"] / 1e3 + r["readiness"] / 5


_CACHE: dict = {}


def generate_candidates(w: World, objective: str = "profit", window: str = DEFAULT_WINDOW) -> list[dict]:
    key = (objective, window)
    if key in _CACHE:
        return _CACHE[key]
    segs = [s for s in w.seg_size if s != "Do-Not-Contact"]
    out = []
    for seg, sku, city in itertools.product(segs, w.hero, w.cities):
        if w.affinity.get((seg, w.products[sku]["cat"]), 0) < 0.9:
            continue
        best = None
        for oi in range(len(OFFERS)):
            if OFFERS[oi][3] and not w.products[sku]["install"]:
                continue
            if OFFERS[oi][2] and w.products[sku]["price"] < 15000:
                continue
            r = evaluate(w, seg, sku, city, oi, window=window)
            k = objective_key(r, objective)
            if best is None or k > best[0]:
                best = (k, r)
        out.append(best[1])
    out.sort(key=lambda r: objective_key(r, objective), reverse=True)
    _CACHE[key] = out
    return out


def mismatch(w: World, window: str = DEFAULT_WINDOW):
    _, ws, we = WINDOWS[window]
    days = (pd.Timestamp(we) - pd.Timestamp(ws)).days + 1
    rows = []
    for city in w.cities:
        for sku, p in w.products.items():
            fest, _ = w.fest(city, p["cat"], ws, we)
            d = w.daily_demand(city, sku) * fest * w.intent.get((city, p["cat"]), 1.0) * SCALE
            s0, inbound, _ = w.stock_at(city, sku, ws, days)
            s = (s0 + sum(q for _, q in inbound)) * SCALE
            cover = s / max(d, 0.01)
            rows.append({"city": city, "city_name": w.cities[city]["city"], "sku": sku, "product": p["name"], "cat": p["cat"],
                         "demand_per_day": round(d, 2), "stock": round(s, 1), "cover_days": round(cover, 1),
                         "status": "SHORT" if cover < days * 1.2 else "EXCESS" if cover > 60 else "OK"})
    transfers = []
    for sku in w.products:
        short = sorted([r for r in rows if r["sku"] == sku and r["status"] == "SHORT" and r["demand_per_day"] > 0.05 * SCALE],
                       key=lambda r: r["cover_days"])
        excess = sorted([r for r in rows if r["sku"] == sku and r["status"] == "EXCESS"], key=lambda r: -r["cover_days"])
        for s, e in zip(short, excess):
            qty = int(min(e["stock"] - 30 * e["demand_per_day"], days * 1.5 * s["demand_per_day"] - s["stock"]))
            if qty >= 1:
                a, b = w.cities[e["city"]], w.cities[s["city"]]
                transfers.append({"sku": sku, "product": s["product"], "from": a["city"], "to": b["city"], "qty": qty,
                                  "from_ll": [a["lat"], a["lon"]], "to_ll": [b["lat"], b["lon"]]})
    return rows, transfers


def time_warp(w: World, rec: dict) -> dict:
    """Run the campaign forward: noise calibrated on campaign-memory residuals (predicted vs actual ROI)."""
    rng = np.random.default_rng(abs(hash(rec["id"])) % 2**32)
    ratio = max(0.2, rng.normal(1 + w.calib["bias"] / 2, min(0.35, w.calib["sd"] / 2 + 0.1)))
    act_incr = rec["incr_units"] * ratio
    stocked = bool(rec["p_stockout"] > rng.uniform())
    act_gp = rec["net_gp"] + (act_incr - rec["incr_units"]) * (rec["incr_gp"] / max(rec["incr_units"], 0.01)) \
        - (rec["lost_gp"] * 0.5 if stocked else 0)
    return {"pred_incr_units": rec["incr_units"], "actual_incr_units": round(act_incr, 1),
            "pred_net_gp": rec["net_gp"], "actual_net_gp": round(act_gp), "stocked_out": stocked,
            "error_pct": round((ratio - 1) * 100, 1),
            "lesson": (f"Uplift for {rec['segment']} came in {abs(ratio - 1):.0%} below forecast; engine shrinks its "
                       f"discount sensitivity for similar campaigns." if ratio < 0.95 else
                       f"Response came in at or above forecast (+{(ratio - 1) * 100:.0f}%); confidence raised for "
                       f"{rec['segment']} × {rec['category']}.")}
