"""Turn the simulated world into observed tables (data/synthetic) and hidden truth (data/_truth)."""
from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from . import stories
from .catalog import SERVICES
from .config import CATEGORIES, CAT_INDEX, HISTORY_END, HISTORY_START, DEMO_TODAY, FORWARD_DAYS
from .geography import CITY_CODES
from .pricing import markdown_calendar_frame
from .world import ELASTICITY, CHANNEL_COST, NEST_LAMBDA, U0, RATE_THETA, CONV0


def _dates(w, idx):
    return pd.to_datetime(pd.Series(np.asarray(idx)).map(lambda k: w.dates[int(k)]))


def build_all(w):
    rng = np.random.default_rng(w.seed + 1)
    h0 = w.h0
    out, truth = {}, {}
    day = lambda k: w.dates[int(k)]
    tsd = pd.Timestamp

    # ------------------------------------------------------------ reference / master data
    out["regions"] = w.regions
    out["cities"] = w.cities
    st = w.stores.drop(columns=["attractiveness"]).copy()
    out["stores"] = st
    out["warehouses"] = w.warehouses
    out["store_capacity"] = st[["store_id", "format", "install_slots_per_day", "demo_zone", "demo_slots_per_day",
                                "ship_from_store", "sfs_orders_per_day", "staff_count"]].assign(
        delivery_vans=np.where(st["format"].eq("Flagship"), 6, np.where(st["format"].eq("Standard"), 3, 1)))
    prod = w.products.copy()
    out["product_relationships"] = w.relationships
    out["events"] = w.events.assign(start=pd.to_datetime(w.events["start"]), end=pd.to_datetime(w.events["end"]),
                                    peak=pd.to_datetime(w.events["peak"]))
    out["channel_costs"] = pd.DataFrame([dict(channel=k, cost_per_send_inr=v) for k, v in CHANNEL_COST.items()] +
                                        [dict(channel="creative_fixed_per_campaign", cost_per_send_inr=15000.0)])

    # ------------------------------------------------------------ orders & lines
    oc = ["order_id", "day", "hour", "customer_id", "is_guest", "store_id", "home_store_id", "channel", "campaign_id", "items",
          "gross_amount", "discount_total", "promo_value_total", "total", "payment_type", "status", "delivery_promised_days",
          "delivery_days", "is_late", "install_wait_days"]
    orders = pd.DataFrame(w.orders, columns=oc)
    orders["order_date"] = _dates(w, orders["day"]).values
    orders["order_ts"] = orders["order_date"] + pd.to_timedelta(orders["hour"], unit="h") + pd.to_timedelta(rng.integers(0, 3600, len(orders)), unit="s")
    orders.loc[orders["channel"].eq("store") & (orders["delivery_promised_days"] == 0), "delivery_promised_days"] = 0
    orders["delivered_on"] = orders["order_date"] + pd.to_timedelta(orders["delivery_days"], unit="D")
    orders.loc[orders["status"].eq("cancelled"), ["delivered_on"]] = pd.NaT
    orders["install_wait_days"] = orders["install_wait_days"].astype("Int64")
    orders = orders.drop(columns=["day", "hour"])
    lc = ["order_id", "line_no", "sku_id", "qty", "mrp", "list_price", "unit_price", "discount_pct", "unit_cost", "line_total",
          "promo_source", "campaign_id", "bundle_id", "promo_value_inr"]
    lines = pd.DataFrame(w.lines, columns=lc)
    lines = lines.merge(prod[["sku_id", "category"]], on="sku_id", how="left")
    out["orders"] = orders[["order_id", "order_date", "order_ts", "customer_id", "is_guest", "store_id", "home_store_id", "channel",
                            "campaign_id", "items", "gross_amount", "discount_total", "promo_value_total", "total", "payment_type",
                            "status", "delivery_promised_days", "delivery_days", "delivered_on", "is_late", "install_wait_days"]]
    out["order_lines"] = lines
    ol = lines.merge(orders[["order_id", "order_date", "customer_id", "store_id", "status"]], on="order_id")
    ol = ol[ol["status"] == "completed"]

    # ------------------------------------------------------------ returns / reviews
    ret = pd.DataFrame(w.returns, columns=["order_id", "line_no", "sku_id", "rday", "reason", "qty", "refund_amount", "restocked", "store_id"])
    ret = ret[ret["rday"] < w.D].copy()
    ret["return_date"] = _dates(w, ret["rday"]).values
    ret.insert(0, "return_id", [f"RET-{k:07d}" for k in range(1, len(ret) + 1)])
    out["returns"] = ret.drop(columns=["rday"])
    rv = pd.DataFrame(w.reviews, columns=["order_id", "customer_id", "sku_id", "rday", "rating", "delivery_days", "was_late", "install_wait_days"])
    rv = rv[rv["rday"] < w.D].copy()
    rv["review_date"] = _dates(w, rv["rday"]).values
    rv.insert(0, "review_id", [f"REV-{k:07d}" for k in range(1, len(rv) + 1)])
    rv["install_wait_days"] = rv["install_wait_days"].astype("Int64")
    rv["verified_purchase"] = True
    out["reviews"] = rv.drop(columns=["rday"])
    # product rating = Bayesian mean of observed reviews
    agg = rv.groupby("sku_id")["rating"].agg(["sum", "count"])
    prior_m, prior_n = 4.1, 8
    prod["n_reviews"] = prod["sku_id"].map(agg["count"]).fillna(0).astype(int)
    prod["rating"] = ((prod["sku_id"].map(agg["sum"]).fillna(0) + prior_m * prior_n) / (prod["n_reviews"] + prior_n)).round(2)
    prod.loc[prod["is_service"], "rating"] = np.nan
    out["products"] = prod.drop(columns=["margin_pct", "erosion_per_month"])

    # ------------------------------------------------------------ customers (observed)
    cust = w.cust_df.copy()
    cust["marketing_consent"] = w.consent
    cust["whatsapp_opt_in"] = w.wa
    cust["email_opt_in"] = w.email
    cust["unsubscribed_on"] = pd.to_datetime([day(k) if k >= 0 else None for k in w.unsub_day])
    cust["joined_on"] = pd.to_datetime(cust["joined_on"])
    # income_band_proxy derived from observed basket tier
    tier_num = prod.set_index("sku_id")["tier"].map({"entry": 0, "mid": 1, "premium": 2})
    ph = ol[~ol["sku_id"].str.startswith("SRV")].assign(t=lambda x: x["sku_id"].map(tier_num))
    mt = ph.groupby("customer_id")["t"].mean()
    band = np.where(cust["customer_id"].map(mt).isna(), None,
                    np.where(cust["customer_id"].map(mt) >= 1.35, "high", np.where(cust["customer_id"].map(mt) >= 0.7, "mid", "low")))
    cust["income_band_proxy"] = band
    cust["preferred_channel"] = np.where(w.ca["online"] > 0.6, "online", np.where(w.ca["online"] > 0.3, "omni", "store"))
    out["customers"] = cust[["customer_id", "home_city", "home_city_code", "home_store_id", "preferred_channel", "loyalty_tier",
                             "joined_on", "marketing_consent", "whatsapp_opt_in", "email_opt_in", "app_user", "dnd",
                             "unsubscribed_on", "age_band", "income_band_proxy"]]

    # ------------------------------------------------------------ web / intent
    web = build_web_daily(w, rng)
    onl = ol[ol["customer_id"].notna() & ~ol["category"].eq("SRV")].merge(orders[["order_id", "channel"]], on="order_id")
    onl = onl[onl["channel"].isin(["web", "app"])].groupby(["customer_id", "order_date", "category"]).size().rename("n").reset_index()
    onl = onl.rename(columns={"order_date": "date"})
    onl["date"] = pd.to_datetime(onl["date"])
    web["date"] = pd.to_datetime(web["date"])
    web = web.merge(onl, on=["customer_id", "date", "category"], how="left")
    web["purchases"] = web["n"].fillna(0).astype(int)
    web = web.drop(columns=["n"])
    out["web_daily"] = web
    out["city_search_index"] = build_search_index(w, web, rng)

    # ------------------------------------------------------------ campaigns & exposures
    camp, expo, cout, uplift_t, design = build_campaign_tables(w, ol)
    out["campaigns_hist"], out["exposures"], out["campaign_outcomes"] = camp, expo, cout
    truth["uplift_truth"], truth["campaign_design_truth"] = uplift_t, design

    # ------------------------------------------------------------ inventory
    inv_w, snap, po, transfers = build_inventory_tables(w)
    out["inventory_weekly"], out["inventory_snapshot"], out["inbound_po"], out["stock_transfers"] = inv_w, snap, po, transfers
    out["install_bookings"] = build_install_bookings(w, rng)
    out["markdown_calendar"] = markdown_calendar_frame(w.md, w.deal[:, : w.P], w.clear[:, : w.P], w.dates[: w.D], w.sku_ids[: w.P], h0)
    out["regional_demand"] = build_regional_demand(w, ol, web, inv_w)
    out["customer_behavior_summary"] = build_behavior_summary(w, ol, orders, web, expo)

    # ------------------------------------------------------------ truth
    ct = w.cust_truth.copy()
    ct["loyalty_tier"] = w.ca["tier"]
    ct["s8_wm_intent_spike"] = np.isin(np.arange(w.N), getattr(w, "s8_selected", np.array([], int)))
    truth["customers_truth"] = ct
    pt = prod[["sku_id", "category", "subcategory", "substitute_group"]].copy()
    pt["true_quality"] = w.s_quality
    pt["true_popularity_utility"] = w.s_pop
    pt["true_margin_pct"] = w.s_margin
    pt["category_elasticity"] = pt["category"].map(ELASTICITY)
    pt["nest_lambda"] = NEST_LAMBDA
    truth["product_truth"] = pt
    truth["elasticity_truth"] = pd.DataFrame([dict(category=c, true_elasticity=e, definition="units ∝ (1 - open markdown)^(-e) at mean price sensitivity")
                                              for c, e in ELASTICITY.items()])
    truth["festival_truth"] = w.fest_truth
    truth["demand_truth"] = build_demand_truth(w)
    kap = []
    for (g, src), (dprom, same, other, induced) in w.kappa.items():
        tot = dprom + induced
        kap.append(dict(substitute_group=g, promo_source=src, promoted_share_gain_organic=round(dprom, 3), shifted_from_same_group=round(same, 3),
                        shifted_from_other_groups=round(other, 3), induced_promoted_units=round(induced, 3),
                        kappa_same_group=round(same / tot, 4) if tot > 0 else None,
                        kappa_total_shift=round((same + other) / tot, 4) if tot > 0 else None))
    truth["cannibalisation_truth"] = pd.DataFrame(kap).sort_values(["substitute_group", "promo_source"])
    lost = pd.DataFrame(w.lost, columns=["day", "cust", "store", "sku", "cat", "reason"])
    lost["date"] = _dates(w, lost["day"]).values
    lost["customer_id"] = [w.cust_ids[i] if i >= 0 else None for i in lost["cust"]]
    lost["store_id"] = [w.store_ids[s] for s in lost["store"]]
    lost["sku_id"] = [w.sku_ids[p] if p >= 0 else None for p in lost["sku"]]
    lost["category"] = [CATEGORIES[k] for k in lost["cat"]]
    truth["lost_demand_events"] = lost[["date", "customer_id", "store_id", "sku_id", "category", "reason"]]
    le = pd.DataFrame(w.life_events, columns=["cust", "day", "event", "cause"])
    le["date"] = _dates(w, le["day"]).values
    le["customer_id"] = w.cust_ids[le["cust"].to_numpy()]
    truth["lifecycle_events"] = le[["customer_id", "date", "event", "cause"]]
    attach = [dict(anchor=a, item=b, base_prob=p) for a, b, p in [
        ("TV", "installation", 0.70), ("TV", "wall_mount_service", 0.22), ("TV", "wall_mount", 0.20), ("TV", "soundbar", 0.05),
        ("TV", "protectplus", 0.18), ("AC", "installation", 0.92), ("WM", "installation", 0.75), ("REF", "delivery_demo", 0.55),
        ("LAP", "bag", 0.22), ("LAP", "mouse", 0.15), ("LAP", "protectplus", 0.12), ("PHN", "case", 0.25), ("PHN", "charger", 0.12)]]
    at = pd.DataFrame(attach)
    city_mult = pd.DataFrame(w.attach_city, columns=["install", "protectplus", "bag", "mount", "soundbar", "mouse", "case", "earbuds"])
    city_mult.insert(0, "city_code", CITY_CODES)
    truth["attach_truth"] = at
    truth["attach_city_multipliers"] = city_mult
    truth["story_truth"] = pd.DataFrame([dict(s, params=json.dumps(s["params"])) for s in stories.STORIES])
    truth["simulation_params"] = pd.DataFrame([dict(param=k, value=json.dumps(v)) for k, v in dict(
        seed=w.seed, rate_theta=RATE_THETA, u0=U0, nest_lambda=NEST_LAMBDA, conv0=CONV0.tolist(), elasticity=ELASTICITY,
        uplift_type_multipliers={"persuadable": 1.0, "sure_thing": "0.08 price / 0.6 non-price", "lost_cause": 0.1, "sleeping_dog": -0.5},
        g_pct="1-exp(-d/0.12)", holdout=0.10, guest_ratio=w.guest_ratio).items()])
    return out, truth


# ============================================================================ web
def build_web_daily(w, rng):
    J = w.J
    n = w.nJ
    vis = J["vis"][:n] & (J["end"][:n] >= w.h0)
    ids = np.nonzero(vis)[0]
    cust, cat, sub = J["cust"][ids], J["cat"][ids], J["sub"][ids]
    s, e, out, kind = J["start"][ids], J["end"][ids], J["outcome"][ids], J["kind"][ids]
    L = np.maximum(e - s, 0) + 1
    rep = np.repeat(np.arange(len(ids)), L)
    offs = np.arange(len(rep)) - np.repeat(np.cumsum(L) - L, L)
    dayk = s[rep] + offs
    browse = w.ca["browse"][cust[rep]]
    first, last = offs == 0, offs == (L[rep] - 1)
    keep = first | last | (rng.random(len(rep)) < np.clip(0.6 * np.sqrt(browse), 0.15, 0.95))
    keep &= (dayk >= w.h0) & (dayk < w.D)
    rep, dayk, offs = rep[keep], dayk[keep], offs[keep]
    first, last = first[keep], last[keep]
    m = len(rep)
    phase = offs / np.maximum(L[rep] - 1, 1)
    conv = out[rep] == 1
    b = w.ca["browse"][cust[rep]]
    durable = np.isin(cat[rep], [CAT_INDEX[c] for c in ("TV", "AC", "REF", "WM", "LAP", "PHN", "TAB", "GAM")])
    views = 1 + rng.poisson(1.2 * b + 0.8 * phase)
    searches = rng.poisson(np.where(first, 1.4, 0.3) * (1.2 - 0.6 * phase))
    cat_views = rng.poisson(0.6 + 0.5 * (1 - phase))
    compares = rng.poisson(np.where(durable, 0.9, 0.2) * 4 * phase * (1 - phase))
    wish = (rng.random(m) < 0.06 + 0.12 * phase).astype(int)
    atc = (rng.random(m) < np.where(last & conv, 0.75, 0.04 + 0.18 * phase)).astype(int)
    rem = (atc & (rng.random(m) < np.where(conv, 0.05, 0.35))).astype(int)
    promo = (kind[rep] == 1).astype(int) * rng.poisson(1.0, m)
    online_buy = np.zeros(m, int)
    ck = (last & (atc == 1)).astype(int)
    df = pd.DataFrame(dict(cust=cust[rep], day=dayk, category=cat[rep], sub=sub[rep], views=views, searches=searches,
                           category_views=cat_views, compares=compares, wishlist=wish, atc=atc, remove_from_cart=rem,
                           promo_views=promo, checkout_starts=ck, purchases=online_buy))
    # clicked campaign messages -> promotion landing views
    ex = pd.DataFrame(w.exposures)
    if len(ex):
        cl = ex[ex["clicked"]]
        cats = {c["campaign_id"]: (c["scope_cats"][0] if c.get("scope_cats") else 0) for c in w.camps if "scope_cats" in c}
        subs = {}
        for c in w.camps:
            if "scope_mask" in c:
                idx = np.nonzero(c["scope_mask"][: w.P])[0]
                subs[c["campaign_id"]] = int(w.s_sub[idx[0]]) if len(idx) else 0
        cdf = pd.DataFrame(dict(cust=cl["cust"].values, day=cl["sent_day"].values, category=cl["campaign_id"].map(cats).values,
                                sub=cl["campaign_id"].map(subs).values, views=1 + rng.poisson(1.0, len(cl)), searches=0, category_views=1,
                                compares=0, wishlist=0, atc=0, remove_from_cart=0, promo_views=1, checkout_starts=0, purchases=0))
        df = pd.concat([df, cdf], ignore_index=True)
    # casual browsing without a purchase journey
    days = np.arange(w.h0, w.D)
    n_idle = int(0.012 * w.N * len(days))
    ci = rng.integers(0, w.N, n_idle)
    wt = w.ca["browse"][ci] * w.ca["online"][ci] * np.clip(w.ca["joined_day"][ci] <= w.D, 0, 1)
    ci = ci[rng.random(n_idle) < wt / wt.max()]
    dd = rng.integers(w.h0, w.D, len(ci))
    ok = w.ca["joined_day"][ci] <= dd
    ci, dd = ci[ok], dd[ok]
    kc = (w.ca["aff"][ci].cumsum(1) < rng.random(len(ci))[:, None]).sum(1).clip(0, 11)
    sb = np.array([w.cat_subs[k][0][int(rng.integers(0, len(w.cat_subs[k][0])))] for k in kc])
    idf = pd.DataFrame(dict(cust=ci, day=dd, category=kc, sub=sb, views=1 + rng.poisson(0.6, len(ci)), searches=rng.poisson(0.3, len(ci)),
                            category_views=1, compares=0, wishlist=0, atc=0, remove_from_cart=0, promo_views=0, checkout_starts=0, purchases=0))
    df = pd.concat([df, idf], ignore_index=True)
    agg = df.groupby(["cust", "day", "category", "sub"], sort=True).sum().reset_index()
    # online purchases from observed orders
    agg["customer_id"] = w.cust_ids[agg["cust"].to_numpy()]
    agg["date"] = pd.to_datetime(pd.Series(agg["day"]).map(lambda k: w.dates[int(k)])).values
    agg["category"] = np.array(CATEGORIES)[agg["category"].to_numpy()]
    agg["subcategory"] = np.array(w.sub_names)[agg["sub"].to_numpy()]
    app = w.ca["app"][agg["cust"].to_numpy()]
    agg["device"] = np.where(app & (rng.random(len(agg)) < 0.65), "app", "web")
    agg["sessions"] = 1 + (agg["views"] > 4).astype(int)
    return agg[["customer_id", "date", "category", "subcategory", "device", "sessions", "views", "searches", "category_views", "compares",
                "wishlist", "atc", "remove_from_cart", "promo_views", "checkout_starts", "purchases"]]


def build_search_index(w, web, rng):
    """Market-level search interest: registered-customer searches + anonymous market searches driven by the same intent."""
    D0, D1 = w.h0, w.D
    lam = w.city_lambda[D0:D1].astype(float)  # day x city x cat expected journey starts (registered)
    wc = web.merge(pd.DataFrame(dict(customer_id=w.cust_ids, city=w.ca["city_i"])), on="customer_id")
    wc["k"] = wc["category"].map(CAT_INDEX)
    wc["d"] = (pd.to_datetime(wc["date"]) - pd.Timestamp(HISTORY_START)).dt.days
    reg = np.zeros_like(lam)
    np.add.at(reg, (wc["d"].to_numpy(), wc["city"].to_numpy(), wc["k"].to_numpy()), wc["searches"].to_numpy())
    market = lam * 40.0 * np.exp(rng.normal(0, 0.08, lam.shape))
    raw = market + reg
    idx = raw / raw.mean(0, keepdims=True) * 100
    allc = raw.sum(2)
    idx_all = allc / allc.mean(0, keepdims=True) * 100
    dates = pd.to_datetime([w.dates[k] for k in range(D0, D1)])
    rows = []
    for ci, c in enumerate(CITY_CODES):
        for k, cat in enumerate(CATEGORIES + ["ALL"]):
            v = idx[:, ci, k] if cat != "ALL" else idx_all[:, ci]
            rows.append(pd.DataFrame(dict(city_code=c, category=cat, date=dates, search_index=np.round(v, 2))))
    return pd.concat(rows, ignore_index=True)


# ============================================================================ campaigns
def build_campaign_tables(w, ol):
    ex = pd.DataFrame(w.exposures)
    ex["customer_id"] = w.cust_ids[ex["cust"].to_numpy()]
    ex["sent_at"] = pd.to_datetime(ex["sent_day"].map(lambda k: w.dates[int(k)])) + pd.to_timedelta(10, unit="h")
    end_day = w.D - 1
    # conversions: any completed order line in the campaign's scope categories
    scope = {c["campaign_id"]: [CATEGORIES[k] for k in c.get("scope_cats", [])] for c in w.camps}
    olc = ol[ol["customer_id"].notna()][["customer_id", "order_date", "category", "line_total", "unit_cost", "qty", "campaign_id"]].copy()
    olc["d"] = (pd.to_datetime(olc["order_date"]) - pd.Timestamp(w.dates[0])).dt.days
    sc = pd.DataFrame([(cid, c) for cid, cs in scope.items() for c in cs], columns=["campaign_id", "category"])
    exk = ex[["campaign_id", "customer_id", "sent_day"]].reset_index()
    j = exk.merge(sc, on="campaign_id").merge(olc.drop(columns=["campaign_id"]), on=["customer_id", "category"])
    j = j[(j["d"] >= j["sent_day"]) & (j["d"] < j["sent_day"] + 30)]
    j["lag"] = j["d"] - j["sent_day"]
    c7 = j[j["lag"] < 7].groupby("index").size()
    c30 = j.groupby("index").size()
    rev30 = j.groupby("index")["line_total"].sum()
    gp30 = (j["line_total"] - j["unit_cost"] * j["qty"]).groupby(j["index"]).sum()
    anyo = olc[["customer_id", "d"]].drop_duplicates()
    jr = exk.merge(anyo, on="customer_id")
    jr = jr[(jr["d"] >= jr["sent_day"] + 30) & (jr["d"] < jr["sent_day"] + 180)]
    rep = jr.groupby("index").size()
    ex["converted_7d"] = pd.Series(ex.index.map(c7), index=ex.index).fillna(0).gt(0).astype("boolean")
    ex["converted_30d"] = pd.Series(ex.index.map(c30), index=ex.index).fillna(0).gt(0).astype("boolean")
    ex["conv_revenue"] = pd.Series(ex.index.map(rev30), index=ex.index).fillna(0.0).round(2)
    ex["conv_gp"] = pd.Series(ex.index.map(gp30), index=ex.index).fillna(0.0)
    ex["repeat_180d"] = pd.Series(ex.index.map(rep), index=ex.index).fillna(0).gt(0).astype("boolean")
    ex.loc[ex["sent_day"] + 6 > end_day, "converted_7d"] = pd.NA
    ex.loc[ex["sent_day"] + 29 > end_day, ["converted_30d"]] = pd.NA
    ex.loc[ex["sent_day"] + 179 > end_day, "repeat_180d"] = pd.NA
    expo = ex[["campaign_id", "customer_id", "group", "channel", "sent_at", "opened", "clicked", "unsubscribed", "converted_7d",
               "converted_30d", "conv_revenue", "repeat_180d"]].copy()
    expo.loc[expo["group"] == "C", ["opened", "clicked", "unsubscribed"]] = False
    uplift_t = ex[["campaign_id", "customer_id", "group", "uplift_type", "p_ctrl", "p_treat", "reach_prob", "exposures_60d",
                   "fatigue_mult", "induced"]].copy()
    uplift_t["true_tau"] = uplift_t["p_treat"] - uplift_t["p_ctrl"]

    # campaign-level observed outcomes
    ln = ol[ol["campaign_id"].notna()].copy()
    ln["disc_amt"] = (ln["list_price"] - ln["unit_price"]) * ln["qty"]
    share = np.where(ln["promo_source"].eq("campaign") | ln["bundle_id"].notna() | ln["campaign_id"].notna(), 1.0, 0.0)
    bank = ln["campaign_id"].map({c["campaign_id"]: c["offer_type"] for c in w.camps}).eq("bank_cashback")
    ln["camp_cost"] = ln["disc_amt"] * share + ln["promo_value_inr"] * np.where(bank, 0.5, 1.0)
    disc = ln.groupby("campaign_id")["camp_cost"].sum()
    oh = np.stack(w.inv.daily_on_hand)  # history days x S x P
    rows, outc = [], []
    for c in w.camps:
        cid = c["campaign_id"]
        e = ex[ex["campaign_id"] == cid]
        T, C = e[e["group"] == "T"], e[e["group"] == "C"]
        chcost = float(T["channel"].map(CHANNEL_COST).sum())
        # stock-outs of the campaign's best-selling scope SKUs in scope stores during the window
        a, b = c["start_day"] - w.h0, min(c["end_day"], w.D - 1) - w.h0
        top = ln[ln["campaign_id"] == cid]["sku_id"].value_counts().head(3).index.tolist()
        oos = 0
        if top:
            ps = [w.sku_pos[s] for s in top if w.sku_pos[s] < w.P]
            sts = [s for s in range(w.S) if c["cities"] == "ALL" or CITY_CODES[w.st_city[s]] in c["cities"]]
            if ps and sts:
                sub = oh[a:b + 1][:, sts][:, :, ps]
                rg = w.ranged[np.ix_(sts, ps)][None]
                oos = int((((sub == 0) & rg).any(2)).sum())
        tconv = T["converted_30d"].astype("float").mean() if len(T) else np.nan
        cconv = C["converted_30d"].astype("float").mean() if len(C) else np.nan
        rows.append(dict(
            campaign_id=cid, name=c["name"], objective=c["objective"], offer_type=c["offer_type"], discount_pct=c["discount_pct"],
            flat_off_inr=c["flat_inr"], free_service=c["free_service_sku"], bundle_skus=json.dumps(c["bundle_skus"]),
            target_rule=json.dumps(c["target_rule"]), sku_scope=json.dumps(c["sku_scope"]),
            store_scope=json.dumps({"cities": c["cities"]}), channels=json.dumps(c["channels"]),
            start=pd.Timestamp(c["start"]), end=pd.Timestamp(c["end"]),
            budget_inr=round(c.get("audience_size", 0) * 25 + 15000 + c.get("audience_size", 0) * 0.02 * 2000 * c["discount_pct"] * 10, -2),
            audience_size=int(c.get("audience_size", 0)), eligible_audience=int(c.get("eligible", 0)), holdout_pct=0.10,
            approved_by_role=c["approved_by_role"], exposed=int(T["opened"].sum()), treated=len(T), control=len(C),
            treated_conv_rate=round(tconv, 4) if tconv == tconv else None, control_conv_rate=round(cconv, 4) if cconv == cconv else None,
            revenue=round(float(T["conv_revenue"].sum()), 2), gross_profit=round(float(T["conv_gp"].sum()), 2),
            discount_cost=round(float(disc.get(cid, 0.0)), 2), channel_cost=round(chcost, 2),
            oos_store_days_during=oos, unsub_rate=round(float(T["unsubscribed"].mean()), 4) if len(T) else None,
            treated_repeat_180d=round(float(T["repeat_180d"].astype("float").mean()), 4) if T["repeat_180d"].notna().any() else None,
            control_repeat_180d=round(float(C["repeat_180d"].astype("float").mean()), 4) if C["repeat_180d"].notna().any() else None,
            outcome_window_complete=bool(c["end_day"] + 30 <= w.D - 1),
        ))
    camp = pd.DataFrame(rows)
    # daily treated vs control outcome series per campaign
    jj = j.merge(ex[["group"]], left_on="index", right_index=True)
    jj["gp"] = jj["line_total"] - jj["unit_cost"] * jj["qty"]
    daily = jj.groupby(["campaign_id", "group", "d"]).agg(buyers=("customer_id", "nunique"), units=("qty", "sum"),
                                                          revenue=("line_total", "sum"), gross_profit=("gp", "sum")).reset_index()
    daily["date"] = pd.to_datetime(daily["d"].map(lambda k: w.dates[int(k)]))
    daily["days_since_send"] = daily["d"] - daily["campaign_id"].map({c["campaign_id"]: c["start_day"] for c in w.camps})
    gsize = ex.groupby(["campaign_id", "group"]).size().rename("group_size").reset_index()
    daily = daily.merge(gsize, on=["campaign_id", "group"])
    cout = daily[["campaign_id", "group", "date", "days_since_send", "group_size", "buyers", "units", "revenue", "gross_profit"]].round(2)
    design = pd.DataFrame([dict(campaign_id=c["campaign_id"], template=c["template"]) for c in w.camps])
    return camp, expo, cout, uplift_t, design


# ============================================================================ inventory
def build_inventory_tables(w):
    inv = w.inv
    parts = []
    for (wk, ss, pp, oh, sales, rec, oos, oo, lost) in inv.weekly_rows:
        parts.append(pd.DataFrame(dict(week_start=pd.Timestamp(wk), s=ss, p=pp, on_hand_end=oh, sales=sales, receipts=rec,
                                       oos_days=oos, on_order_end=oo, _lost=lost)))
    iw = pd.concat(parts, ignore_index=True)
    iw["store_id"] = np.array(w.store_ids)[iw["s"]]
    iw["sku_id"] = np.array(w.sku_ids)[iw["p"]]
    iw["is_partial_week"] = iw["week_start"].isin([iw["week_start"].min(), iw["week_start"].max()])
    inv_weekly = iw[["store_id", "sku_id", "week_start", "on_hand_end", "sales", "receipts", "oos_days", "on_order_end", "is_partial_week"]]

    last = w.D - 1
    ds = np.stack(inv.daily_sales[-28:]).astype(float).sum(0) / 28.0
    online_last = np.zeros((w.S, w.P))
    lines_last = [l for l in w.lines[-3000:]]
    rows = []
    po_open = {}
    for po in inv.pos:
        if po["received"] is None and po["eta"] > last:
            key = (po["s"], po["p"])
            po_open.setdefault(key, []).append(po)
    for s in range(w.S):
        for p in range(w.P):
            oh = int(inv.on_hand[s, p])
            age, aged90 = inv.avg_age(s, p, last)
            lr = inv.last_receipt(s, p)
            r = ds[s, p]
            ss_ = int(round(1.3 * np.sqrt(max(inv.ewma[s, p], 0) * 17) + 2 * inv.ewma[s, p]))
            rop = int(round(inv.ewma[s, p] * 17 + ss_))
            opens = po_open.get((s, p), [])
            inc = sum(x["qty"] for x in opens)
            nxt = min((x["eta"] for x in opens), default=None)
            reserved = int(min(oh, np.random.default_rng(s * 1000 + p).poisson(0.3 * r))) if oh > 0 else 0
            rows.append(dict(store_id=w.store_ids[s], sku_id=w.sku_ids[p], is_ranged=bool(w.ranged[s, p]), on_hand=oh, reserved=reserved,
                             available=oh - reserved, safety_stock=ss_, reorder_point=rop, incoming_qty=int(inc),
                             next_inbound_eta=pd.Timestamp(w.dates[nxt]) if nxt is not None and nxt < len(w.dates) else pd.NaT,
                             avg_daily_sales_28d=round(r, 4), days_of_cover=round(oh / r, 1) if r > 0 else None,
                             avg_age_days=round(age, 1) if age is not None else None, units_aged_90d=int(aged90),
                             last_receipt=pd.Timestamp(w.dates[lr]) if lr is not None and lr >= 0 else pd.NaT,
                             stock_value_at_cost=round(oh * w.list_price[last, p] * (1 - w.s_margin[p]), 2),
                             excess_units_over_60d=int(max(0, oh - 60 * r)) if r > 0 else oh,
                             snapshot_date=pd.Timestamp(HISTORY_END)))
    snap = pd.DataFrame(rows)
    pr = []
    for k, po in enumerate(inv.pos):
        if po["created"] < w.h0 - 30 and (po["received"] is not None and po["received"] < w.h0):
            continue
        status = "received" if po["received"] is not None and po["received"] <= last else ("delayed" if po["delay"] > 0 else "open")
        pr.append(dict(po_id=f"PO-{k + 1:07d}", store_id=w.store_ids[po["s"]], sku_id=w.sku_ids[po["p"]],
                       warehouse_id=w.stores.loc[po["s"], "warehouse_id"], qty=po["qty"], po_type=po["type"],
                       created_on=pd.Timestamp(w.dates[max(po["created"], 0)]), planned_eta=pd.Timestamp(w.dates[po["planned"]]),
                       eta=pd.Timestamp(w.dates[po["eta"]]), received_on=pd.Timestamp(w.dates[po["received"]]) if po["received"] is not None else pd.NaT,
                       delay_days=po["delay"], status=status))
    po = pd.DataFrame(pr)
    tr = pd.DataFrame(inv.transfers)
    if len(tr):
        tr = tr[tr["day"] >= w.h0]
        tr = pd.DataFrame(dict(transfer_date=pd.to_datetime(tr["day"].map(lambda k: w.dates[int(k)])),
                               from_store_id=np.array(w.store_ids)[tr["s"]], to_store_id=tr["to_store"],
                               sku_id=np.array(w.sku_ids)[tr["p"]], qty=tr["qty"], kind=tr["kind"]))
    return inv_weekly, snap, po, tr


def build_install_bookings(w, rng):
    rows = []
    last = w.D - 1
    hist = range(w.h0, w.D)
    fwd = range(w.D, w.D + FORWARD_DAYS)
    # forward baseline: recent utilisation x planned festive load x booking curve (+ bookings already made by orders)
    recent = w.install_booked[:, last - 27:last + 1].mean(1) / w.st_install
    blr2 = w.store_ids.index(stories.STORIES[8]["params"]["store"])
    s9a, s9b = w.di(pd.Timestamp("2026-11-02").date()), w.di(pd.Timestamp("2026-11-08").date())
    for s in range(w.S):
        for d in list(hist) + list(fwd):
            slots = int(w.st_install[s])
            booked = int(w.install_booked[s, d])
            demo = int(w.demo_booked[s, d])
            if d >= w.D:
                lead = d - last
                fest = float(np.clip(1 + w.fest[d, w.st_city[s], [0, 4, 6]].mean(), 0.5, 2.5))
                base = recent[s] * fest * np.exp(-lead / 14.0) * slots
                booked += int(rng.poisson(max(base, 0)))
                demo += int(rng.poisson(max(0.3 * w.demo_booked[s, last - 27:last + 1].mean() * np.exp(-lead / 10), 0)))
                if s == blr2 and s9a <= d <= s9b:
                    booked = int(round(slots * 0.92)) - (1 if rng.random() < 0.3 else 0)
                booked = min(booked, int(slots * 1.1))
            rows.append((w.store_ids[s], pd.Timestamp(w.dates[d]), slots, booked, int(w.st_demo[s]), demo,
                         int(w.st_sfs_cap[s]) if w.st_sfs[s] else 0, int(w.sfs_load[s, d]) if d < w.D else 0, d >= w.D))
    return pd.DataFrame(rows, columns=["store_id", "date", "install_slots", "booked_slots", "demo_slots", "demo_booked",
                                       "sfs_capacity", "sfs_orders", "is_forward"])


def build_regional_demand(w, ol, web, inv_w):
    x = ol.merge(w.stores[["store_id", "city_code"]], on="store_id")
    x = x[~x["category"].eq("SRV")]
    x["week_start"] = pd.to_datetime(x["order_date"]) - pd.to_timedelta(pd.to_datetime(x["order_date"]).dt.weekday, unit="D")
    x["gp"] = x["line_total"] - x["unit_cost"] * x["qty"]
    x["list_rev"] = x["list_price"] * x["qty"]
    g = x.groupby(["city_code", "category", "week_start"]).agg(orders=("order_id", "nunique"), units=("qty", "sum"), revenue=("line_total", "sum"),
                                                               gross_profit=("gp", "sum"), list_revenue=("list_rev", "sum")).reset_index()
    g["avg_discount_pct"] = (1 - g["revenue"] / g["list_revenue"]).round(4)
    wc = web.merge(pd.DataFrame(dict(customer_id=w.cust_ids, city_code=np.array(CITY_CODES)[w.ca["city_i"]])), on="customer_id")
    wc["week_start"] = pd.to_datetime(wc["date"]) - pd.to_timedelta(pd.to_datetime(wc["date"]).dt.weekday, unit="D")
    wg = wc.groupby(["city_code", "category", "week_start"]).agg(web_views=("views", "sum"), web_searches=("searches", "sum")).reset_index()
    iv = inv_w.merge(w.stores[["store_id", "city_code"]], on="store_id").merge(w.products[["sku_id", "category"]], on="sku_id")
    ig = iv.groupby(["city_code", "category", "week_start"]).agg(oos_store_sku_days=("oos_days", "sum"), on_hand_end=("on_hand_end", "sum")).reset_index()
    out = g.merge(wg, on=["city_code", "category", "week_start"], how="outer").merge(ig, on=["city_code", "category", "week_start"], how="left")
    out = out[out["week_start"] >= pd.Timestamp(HISTORY_START) - pd.Timedelta(days=7)]
    out["region"] = out["city_code"].map(w.cities.set_index("city_code")["region"])
    for c in ("orders", "units", "revenue", "gross_profit", "web_views", "web_searches"):
        out[c] = out[c].fillna(0)
    return out.drop(columns=["list_revenue"]).round(2).sort_values(["city_code", "category", "week_start"]).reset_index(drop=True)


def build_behavior_summary(w, ol, orders, web, expo):
    oc = orders[orders["status"].eq("completed") & orders["customer_id"].notna()]
    g = oc.groupby("customer_id").agg(orders_24m=("order_id", "size"), spend_24m=("total", "sum"),
                                      first_order=("order_date", "min"), last_order=("order_date", "max"),
                                      promo_orders=("discount_total", lambda s: int((s > 0).sum())))
    cats = ol[ol["customer_id"].notna() & ~ol["category"].eq("SRV")].groupby("customer_id")["category"].nunique().rename("categories_bought")
    today = pd.Timestamp(DEMO_TODAY)
    w90 = web[pd.to_datetime(web["date"]) >= today - pd.Timedelta(days=90)].groupby("customer_id")["date"].nunique().rename("web_active_days_90d")
    e = expo[expo["group"] == "T"]
    e60 = e[e["sent_at"] >= today - pd.Timedelta(days=60)].groupby("customer_id").size().rename("exposures_60d")
    lastx = e.groupby("customer_id")["sent_at"].max().rename("last_exposure")
    df = pd.DataFrame(dict(customer_id=w.cust_ids)).set_index("customer_id")
    df = df.join(g).join(cats).join(w90).join(e60).join(lastx)
    for c in ("orders_24m", "promo_orders", "categories_bought", "web_active_days_90d", "exposures_60d"):
        df[c] = df[c].fillna(0).astype(int)
    df["spend_24m"] = df["spend_24m"].fillna(0).round(2)
    df["promo_order_share"] = (df["promo_orders"] / df["orders_24m"].replace(0, np.nan)).round(3)
    df["days_since_last_order"] = (today - pd.to_datetime(df["last_order"])).dt.days
    df["as_of"] = today
    return df.reset_index()


def build_demand_truth(w):
    D0, D1 = w.h0, w.D
    lam = w.city_lambda[D0:D1]
    dates = pd.to_datetime([w.dates[k] for k in range(D0, D1)])
    rows = []
    for ci, c in enumerate(CITY_CODES):
        for k, cat in enumerate(CATEGORIES):
            rows.append(pd.DataFrame(dict(city_code=c, category=cat, date=dates,
                                          season_mult=np.round(w.season[D0:D1, ci, k], 4), festival_excess=np.round(w.fest[D0:D1, ci, k], 4),
                                          open_markdown=np.round(w.md[D0:D1, ci, k], 4),
                                          expected_journey_starts=np.round(lam[:, ci, k], 4),
                                          expected_purchases_at_list=np.round(lam[:, ci, k] * CONV0[k], 4))))
    return pd.concat(rows, ignore_index=True)
