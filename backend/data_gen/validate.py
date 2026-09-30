"""Validate the generated digital twin: integrity, realism, causal links and the ten planted stories.

    python -m data_gen.validate            -> docs/DATA_VALIDATION_REPORT.md + data/_report.html
Exit code 1 if any hard check fails.

Story checks read *observed* tables only (what the engine will see); _truth is used only
where a story's claim is about hidden truth (e.g. true cannibalisation kappa).
"""
from __future__ import annotations

import base64
import io
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

from .config import SYNTH_DIR, TRUTH_DIR, TARGETS, TOLERANCE, HISTORY_START, HISTORY_END, DEMO_TODAY, REPO_DIR, DATA_DIR

RESULTS: list[dict] = []
CHARTS: list[tuple[str, str]] = []


def check(section, name, ok, detail, hard=True):
    RESULTS.append(dict(section=section, check=name, status="PASS" if ok else ("FAIL" if hard else "WARN"), detail=detail))
    return ok


def load():
    t = {p.stem: pd.read_parquet(p) for p in sorted(SYNTH_DIR.glob("*.parquet"))}
    tr = {p.stem: pd.read_parquet(p) for p in sorted(TRUTH_DIR.glob("*.parquet"))}
    return t, tr


def _chart(title, fn):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7.5, 3.2))
        fn(ax)
        ax.set_title(title, fontsize=10)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=90)
        plt.close(fig)
        CHARTS.append((title, base64.b64encode(buf.getvalue()).decode()))
    except Exception as e:  # charts are optional
        CHARTS.append((title + f" (chart failed: {e})", ""))


# ============================================================================ checks
def row_counts(t):
    m = {"customers": "customers", "stores": "stores", "products": "products", "orders": "orders", "order_lines": "order_lines",
         "web_daily": "web_daily", "campaigns_hist": "campaigns_hist", "exposures": "exposures",
         "inventory_weekly": "inventory_weekly", "inventory_snapshot": "inventory_snapshot"}
    for k, tab in m.items():
        n, tgt = len(t[tab]), TARGETS[k]
        check("row counts", f"{tab} within ±20% of {tgt:,}", abs(n - tgt) <= TOLERANCE * tgt, f"{n:,} rows ({(n / tgt - 1) * 100:+.1f}%)")
    check("row counts", "12 cities / 4 regions / 36 stores", len(t["cities"]) == 12 and len(t["regions"]) == 4 and len(t["stores"]) == 36,
          f"{len(t['cities'])} cities, {len(t['regions'])} regions, {len(t['stores'])} stores")


def integrity(t):
    pk = {"customers": ["customer_id"], "products": ["sku_id"], "stores": ["store_id"], "orders": ["order_id"],
          "order_lines": ["order_id", "line_no"], "campaigns_hist": ["campaign_id"], "exposures": ["campaign_id", "customer_id"],
          "inventory_snapshot": ["store_id", "sku_id"], "inventory_weekly": ["store_id", "sku_id", "week_start"],
          "inbound_po": ["po_id"], "returns": ["return_id"], "reviews": ["review_id"], "web_daily": ["customer_id", "date", "category", "subcategory"],
          "install_bookings": ["store_id", "date"], "city_search_index": ["city_code", "category", "date"]}
    for tab, cols in pk.items():
        d = t[tab].duplicated(cols).sum()
        check("integrity", f"unique key {tab}({', '.join(cols)})", d == 0, f"{d} duplicates")
    cust, prod, st = set(t["customers"].customer_id), set(t["products"].sku_id), set(t["stores"].store_id)
    fk = [("orders.customer_id", t["orders"].customer_id.dropna(), cust), ("orders.store_id", t["orders"].store_id, st),
          ("order_lines.order_id", t["order_lines"].order_id, set(t["orders"].order_id)), ("order_lines.sku_id", t["order_lines"].sku_id, prod),
          ("exposures.campaign_id", t["exposures"].campaign_id, set(t["campaigns_hist"].campaign_id)),
          ("exposures.customer_id", t["exposures"].customer_id, cust), ("returns.order_id", t["returns"].order_id, set(t["orders"].order_id)),
          ("reviews.order_id", t["reviews"].order_id, set(t["orders"].order_id)), ("web_daily.customer_id", t["web_daily"].customer_id, cust),
          ("inventory_weekly.sku_id", t["inventory_weekly"].sku_id, prod), ("inventory_weekly.store_id", t["inventory_weekly"].store_id, st),
          ("inbound_po.sku_id", t["inbound_po"].sku_id, prod), ("inbound_po.store_id", t["inbound_po"].store_id, st),
          ("install_bookings.store_id", t["install_bookings"].store_id, st), ("customers.home_store_id", t["customers"].home_store_id, st),
          ("product_relationships.related_sku_id", t["product_relationships"].related_sku_id, prod),
          ("orders.campaign_id", t["orders"].campaign_id.dropna(), set(t["campaigns_hist"].campaign_id)),
          ("stores.warehouse_id", t["stores"].warehouse_id, set(t["warehouses"].warehouse_id))]
    for name, s, ref in fk:
        bad = (~s.isin(ref)).sum()
        check("integrity", f"FK {name}", bad == 0, f"{bad} orphans / {len(s):,}")
    o = t["orders"]
    lo, hi = pd.Timestamp(HISTORY_START), pd.Timestamp(HISTORY_END)
    check("integrity", "order dates inside history", o.order_date.between(lo, hi).all(), f"{o.order_date.min().date()} .. {o.order_date.max().date()}")
    check("integrity", "web dates inside history", t["web_daily"].date.between(lo, hi).all(), "")
    l = t["order_lines"]
    phys = ~l.sku_id.str.startswith("SRV")
    check("integrity", "no negative / zero quantities", (l.qty > 0).all(), f"min qty {l.qty.min()}")
    check("integrity", "unit_price >= 0.8 x unit_cost (physical goods)", (l.unit_price[phys] >= 0.8 * l.unit_cost[phys] - 0.01).all(),
          f"min ratio {(l.unit_price[phys] / l.unit_cost[phys]).min():.3f}")
    check("integrity", "prices positive, discount in [0,1]", (l.list_price > 0).all() and l.discount_pct.between(0, 1).all(), "")
    p = t["products"]
    check("integrity", "product cost < list price; mrp >= list", ((p.unit_cost < p.list_price) & (p.mrp >= p.list_price)).all(), "")
    sn = t["inventory_snapshot"]
    check("integrity", "no negative stock", (sn.on_hand >= 0).all() and (t["inventory_weekly"].on_hand_end >= 0).all() and (sn.available >= 0).all(), "")
    ev = t["events"]
    check("integrity", "event start <= end", (ev.start <= ev.end).all(), f"{len(ev)} events")
    key_cols = {"orders": ["order_id", "order_date", "store_id", "channel", "total"], "order_lines": ["sku_id", "qty", "unit_price"],
                "customers": ["customer_id", "home_city", "loyalty_tier"], "exposures": ["group", "channel", "sent_at"]}
    for tab, cols in key_cols.items():
        n = int(t[tab][cols].isna().sum().sum())
        check("integrity", f"no missing key fields in {tab}", n == 0, f"{n} nulls")
    rel = t["product_relationships"].merge(p[["sku_id", "category"]], on="sku_id").merge(
        p[["sku_id", "category"]].rename(columns={"sku_id": "related_sku_id", "category": "rc"}), on="related_sku_id")
    sub = rel[rel.relation == "substitute"]
    check("integrity", "substitutes share a category", (sub.category == sub.rc).all(), f"{len(sub)} substitute edges")
    # no hidden labels leak into observed tables
    leak_cols = {"uplift_type", "price_sensitivity", "promo_responsiveness", "churn_hazard", "true_tau", "p_ctrl", "fatigue_k", "true_quality"}
    leaks = [f"{k}.{c}" for k, df in t.items() for c in df.columns if c in leak_cols]
    check("integrity", "hidden truth not exposed in observed tables", not leaks, ", ".join(leaks) or "none")


def realism(t, tr):
    o, l = t["orders"], t["order_lines"]
    oc = o[o.status == "completed"]
    reg = oc[oc.customer_id.notna()]
    n_per = reg.groupby("customer_id").size()
    check("behaviour", "repeat purchasers exist (>=2 orders share of buyers 35-85%)", 0.35 <= (n_per >= 2).mean() <= 0.85, f"{(n_per >= 2).mean():.1%} of buyers; median {n_per.median():.0f} orders")
    check("behaviour", "heterogeneous frequency (top 10% buyers >= 25% of orders)", n_per.sort_values(ascending=False).head(len(n_per) // 10).sum() / n_per.sum() >= 0.25,
          f"top-decile share {n_per.sort_values(ascending=False).head(len(n_per) // 10).sum() / n_per.sum():.1%}")
    lo = l.merge(o[["order_id", "order_date", "store_id", "status"]], on="order_id")
    lo = lo[lo.status == "completed"].merge(t["stores"][["store_id", "city_code"]], on="store_id")
    # regional variation in per-customer category demand
    cust_city = t["customers"].groupby("home_city_code").size()
    pc = lo[lo.category != "SRV"].groupby(["city_code", "category"]).qty.sum().unstack().div(cust_city, axis=0)
    cv = (pc.std() / pc.mean())
    check("regional", "category demand per customer varies across cities (median CV >= 0.12)", cv.median() >= 0.12, f"median CV {cv.median():.2f}; AC CV {cv.get('AC', np.nan):.2f}")
    # festival effect: Diwali 2025 TV units vs 6-week baseline, by city
    lo["d"] = pd.to_datetime(lo.order_date)
    tv = lo[lo.category == "TV"]
    win = tv[tv.d.between("2025-10-06", "2025-10-23")].groupby("city_code").qty.sum() / 18
    base = tv[tv.d.between("2025-08-18", "2025-09-15")].groupby("city_code").qty.sum() / 29
    ratio = (win / base).dropna()
    check("festival", "Diwali-2025 TV lift > 1.3x nationally", win.sum() / base.sum() > 1.3, f"{win.sum() / base.sum():.2f}x")
    check("festival", "festival lift differs by city (max/min >= 1.3)", ratio.max() / ratio.min() >= 1.3, " ".join(f"{k}:{v:.2f}" for k, v in ratio.sort_values().items()))
    _chart("Daily TV units (national) - festivals visible", lambda ax: tv.groupby("d").qty.sum().rolling(7).mean().plot(ax=ax, color="#E8551C"))
    # web intent -> purchase
    w = t["web_daily"]
    w14 = w[(w.date >= "2026-06-01") & (w.date < "2026-06-15")].groupby(["customer_id", "category"]).views.sum().reset_index()
    buy = lo[(lo.d >= "2026-06-15") & (lo.d < "2026-07-15") & lo.customer_id.notna()] if "customer_id" in lo else None
    lo2 = l.merge(o[["order_id", "order_date", "customer_id", "status"]], on="order_id")
    lo2 = lo2[(lo2.status == "completed") & lo2.customer_id.notna()]
    lo2["d"] = pd.to_datetime(lo2.order_date)
    b = lo2[(lo2.d >= "2026-06-15") & (lo2.d < "2026-07-15")][["customer_id", "category"]].drop_duplicates().assign(bought=1)
    grid = pd.MultiIndex.from_product([t["customers"].customer_id, [c for c in pc.columns]], names=["customer_id", "category"]).to_frame(index=False)
    g = grid.merge(w14, how="left").merge(b, how="left").fillna(0)
    p_view, p_no = g[g.views > 0].bought.mean(), g[g.views == 0].bought.mean()
    check("intent", "recent category views raise next-30-day purchase odds (lift >= 3x)", p_view / p_no >= 3, f"{p_view:.2%} vs {p_no:.2%} (lift {p_view / p_no:.1f}x)")
    # inventory depletion / replenishment / stock-outs
    iw = t["inventory_weekly"].sort_values(["store_id", "sku_id", "week_start"])
    iw["prev"] = iw.groupby(["store_id", "sku_id"]).on_hand_end.shift()
    x = iw.dropna(subset=["prev"])
    resid = x.on_hand_end - (x.prev + x.receipts - x.sales)
    check("inventory", "stock ledger balances (on_hand = prev + receipts - sales, adj. transfers/returns)", (resid.abs() <= 3).mean() >= 0.98,
          f"{(resid == 0).mean():.1%} exact, {(resid.abs() <= 3).mean():.1%} within 3 units")
    check("inventory", "sales deplete stock and receipts replenish it", x.sales.sum() > 0 and x.receipts.sum() > 0, f"{int(x.sales.sum()):,} units sold, {int(x.receipts.sum()):,} received")
    oos = (iw.oos_days > 0).mean()
    check("inventory", "stock-outs occur but are not the norm (2-35% of store-SKU-weeks)", 0.02 <= oos <= 0.35, f"{oos:.1%} of store-SKU-weeks had >=1 OOS day")
    ld = tr["lost_demand_events"]
    check("inventory", "stock-outs cause lost demand (truth only)", len(ld) > 0, f"{len(ld):,} lost purchase attempts in _truth")
    sn = t["inventory_snapshot"]
    cov = sn[sn.is_ranged & sn.days_of_cover.notna()].days_of_cover
    check("inventory", "stock cover heterogeneous across stores/SKUs", cov.quantile(0.9) / max(cov.quantile(0.1), 0.1) > 4, f"P10 {cov.quantile(.1):.0f} d, median {cov.median():.0f} d, P90 {cov.quantile(.9):.0f} d")
    aged = (sn.units_aged_90d.sum() / max(sn.on_hand.sum(), 1))
    check("inventory", "aging stock exists (>90d units 3-40%)", 0.03 <= aged <= 0.4, f"{aged:.1%} of units older than 90 days")
    # campaigns
    c = t["campaigns_hist"]
    e = t["exposures"]
    hold = e.groupby("campaign_id").group.apply(lambda s: (s == "C").mean())
    check("campaigns", "every campaign has a ~10% random holdout", hold.between(0.05, 0.16).all(), f"holdout share {hold.min():.1%}..{hold.max():.1%}")
    check("campaigns", "control rows were never messaged (opened=False)", not e[e.group == "C"].opened.any(), "")
    cc = c.dropna(subset=["treated_conv_rate", "control_conv_rate"])
    lift = cc.treated_conv_rate - cc.control_conv_rate
    check("campaigns", "campaign outcomes are mixed (some clear winners, some ~0 or negative)", (lift > 0.02).sum() >= 10 and (lift <= 0.005).sum() >= 10,
          f"{(lift > 0.02).sum()} with lift > 2pp, {(lift <= 0.005).sum()} with lift <= 0.5pp")
    gp_net = c.gross_profit - c.discount_cost - c.channel_cost
    check("campaigns", "some campaigns lose money after discount & channel cost", (gp_net < 0).sum() >= 5, f"{(gp_net < 0).sum()} campaigns with GP - discount - channel < 0")
    check("campaigns", "some campaigns coincide with stock-outs", (c.oos_store_days_during > 0).sum() >= 5, f"{(c.oos_store_days_during > 0).sum()} campaigns with OOS store-days")
    # retention
    r = c[c.objective.eq("reactivation") & c.treated_repeat_180d.notna()]
    check("retention", "reactivation campaigns lift 180-day repeat (T > C on average)", (r.treated_repeat_180d - r.control_repeat_180d).mean() > 0,
          f"mean T-C repeat_180d {(r.treated_repeat_180d - r.control_repeat_180d).mean() * 100:+.1f} pp over {len(r)} campaigns")
    le = tr["lifecycle_events"]
    check("retention", "customers churn and reactivate", (le.event == "churned").sum() > 1000 and (le.event == "reactivated").sum() > 1000,
          f"{(le.event == 'churned').sum():,} churn / {(le.event == 'reactivated').sum():,} reactivation events (truth)")
    # fatigue
    et = e[(e.group == "T") & e.converted_7d.notna()].merge(c[["campaign_id", "objective"]], on="campaign_id")
    et = et.sort_values("sent_at")
    et["n_prev"] = et.groupby("customer_id").cumcount()
    fr = et.groupby(et.n_prev.clip(upper=8)).converted_7d.mean()
    check("fatigue", "response falls with prior exposures", fr.iloc[-1] < fr.iloc[0] * 0.8, " ".join(f"{int(k)}:{v:.3f}" for k, v in fr.items()))
    un = e[e.group == "T"].merge(t["customers"][["customer_id"]], on="customer_id")
    check("fatigue", "unsubscribes happen and are recorded", t["customers"].unsubscribed_on.notna().sum() > 50, f"{t['customers'].unsubscribed_on.notna().sum():,} customers unsubscribed")
    # capacity
    ib = t["install_bookings"]
    h = ib[~ib.is_forward]
    util = (h.booked_slots / h.install_slots)
    check("capacity", "installation bookings respect capacity (<=100% on >=97% of store-days)", (util <= 1.0).mean() >= 0.97, f"{(util > 1).mean():.2%} store-days over; P95 util {util.quantile(.95):.0%}")
    # elasticity signal (informational)
    rd = t["regional_demand"].dropna(subset=["avg_discount_pct"])
    rd = rd[(rd.units > 0) & (rd.avg_discount_pct < 0.5)]
    et_ = tr["elasticity_truth"].set_index("category").true_elasticity
    rec = {}
    for cat_, g in rd.groupby("category"):
        g = g.copy()
        g["y"] = np.log(g.units)
        g["x"] = np.log(1 - g.avg_discount_pct.clip(0, 0.45))
        for fe in ("city_code", "week_start"):
            g["y"] -= g.groupby(fe).y.transform("mean")
            g["x"] -= g.groupby(fe).x.transform("mean")
        rec[cat_] = -(g.x * g.y).sum() / max((g.x ** 2).sum(), 1e-9)
    within = sum(abs(rec[k] - et_[k]) / et_[k] <= 0.5 for k in rec)
    check("price", "naive 2-way FE regression finds negative price response in >= 9/12 categories", sum(v > 0 for v in rec.values()) >= 9,
          " ".join(f"{k}:{v:.2f}/{et_[k]}" for k, v in rec.items()), hard=False)


# ============================================================================ stories
def cover(sn, store, sku):
    r = sn[(sn.store_id == store) & (sn.sku_id == sku)].iloc[0]
    return r.days_of_cover, r.on_hand, r.avg_daily_sales_28d


def stories(t, tr):
    sn, w, c, e = t["inventory_snapshot"], t["web_daily"], t["campaigns_hist"], t["exposures"]
    cust = t["customers"]
    today = pd.Timestamp(DEMO_TODAY)
    # S1
    w55 = w[w.subcategory == "TV_55"].merge(cust[["customer_id", "home_city_code"]], on="customer_id")
    msg = []
    ok = True
    for city in ("HYD", "PUN"):
        x = w55[w55.home_city_code == city]
        last = x[x.date >= today - pd.Timedelta(days=21)].views.sum() / 21
        prev = x[(x.date < today - pd.Timedelta(days=21)) & (x.date >= today - pd.Timedelta(days=49))].views.sum() / 28
        ok &= last / prev - 1 >= 0.25
        msg.append(f"{city} TV_55 views/day {prev:.1f}->{last:.1f} ({last / prev - 1:+.0%})")
    nat = w55[~w55.home_city_code.isin(["HYD", "PUN"])]
    nl = nat[nat.date >= today - pd.Timedelta(days=21)].views.sum() / 21
    npv = nat[(nat.date < today - pd.Timedelta(days=21)) & (nat.date >= today - pd.Timedelta(days=49))].views.sum() / 28
    msg.append(f"rest of India {nl / npv - 1:+.0%}")
    check("S1", "55in TV intent rising in HYD & PUN (>= +25%)", ok, "; ".join(msg))
    hyd = [cover(sn, s, k) for s in ("HYD-01", "HYD-02", "HYD-03") for k in ("TV-AUR-55U7", "TV-AUR-55Q8")]
    hc = [h[0] for h in hyd]
    check("S1", "HYD 55U7/55Q8 cover 40-65 days", all(h is not None and 40 <= h <= 65 for h in hc), ", ".join(f"{h:.0f}" if h else "n/a" for h in hc))
    pun = [cover(sn, s, k) for s in ("PUN-01", "PUN-02") for k in ("TV-AUR-55U7", "TV-AUR-55Q8")]
    pc = [p[0] for p in pun]
    check("S1", "PUN-01/02 55U7/55Q8 cover 5-11 days", all(p is not None and 5 <= p <= 11 for p in pc), ", ".join(f"{p:.1f}d ({int(q)} units)" if p else "n/a" for p, q, _ in pun))
    po = t["inbound_po"]
    pp = po[po.store_id.isin(["PUN-01", "PUN-02"]) & po.sku_id.isin(["TV-AUR-55U7", "TV-AUR-55Q8"]) & (po.status != "received")]
    check("S1", "next Pune PO arrives after Diwali (2026-11-12)", len(pp) > 0 and (pp.eta.min() >= pd.Timestamp("2026-11-10")),
          f"{len(pp)} open POs, earliest ETA {pp.eta.min().date() if len(pp) else None}")
    m3 = sn[(sn.store_id == "MUM-03") & (sn.sku_id == "TV-AUR-55U7")].iloc[0]
    excess = m3.on_hand - 30 * m3.avg_daily_sales_28d
    check("S1", "MUM-03 holds >= 40 units above 30-day cover on 55U7", excess >= 40, f"on_hand {m3.on_hand}, cover {m3.days_of_cover} d, excess {excess:.0f}")
    # S2
    k = sn[(sn.sku_id == "LAP-KAI-14A25") & sn.store_id.str.startswith("DEL")]
    units = k.on_hand.sum()
    age = (k.avg_age_days * k.on_hand).sum() / max(units, 1)
    check("S2", "DEL holds 180-240 aged units of Kairo Air 14 (2025), avg age >= 120 d", 180 <= units <= 240 and age >= 120, f"{units} units, avg age {age:.0f} d")
    lc = t["products"].set_index("sku_id").loc[["LAP-KAI-14A25", "LAP-KAI-14A26"], "lifecycle"].tolist()
    check("S2", "2025 model end_of_life, 2026 successor is new", lc == ["end_of_life", "new"], str(lc))
    # S3
    fd = c[c.name.str.startswith("Flash Deals")].sort_values("start")
    ex = e[e.campaign_id.isin(fd.campaign_id) & (e.group == "T") & e.converted_7d.notna()]
    resp = ex.groupby("campaign_id").converted_7d.mean().reindex(fd.campaign_id).dropna()
    early, late = resp.iloc[:5].mean(), resp.iloc[-4:].mean()
    check("S3", "deal-blast response of the latest blasts <= 45% of early blasts", late <= 0.45 * early, f"early {early:.1%} -> latest {late:.1%}")
    rec = fd[fd.start >= today - pd.Timedelta(days=60)]
    ex60 = e[e.campaign_id.isin(rec.campaign_id) & (e.group == "T")].groupby("customer_id").size()
    check("S3", "deal-hunter segment received ~9 promos in the last 60 days", len(rec) == 9 and ex60.median() >= 6,
          f"{len(rec)} blasts; median {ex60.median():.0f} sends per recipient ({len(ex60):,} customers)")
    un_early = fd.unsub_rate.iloc[:5].mean()
    un_late = fd.unsub_rate.iloc[-5:].mean()
    check("S3", "unsubscribe rate rises with pressure", un_late > un_early, f"{un_early:.2%} -> {un_late:.2%}")
    _chart("S3 - flash-deal 7-day response by blast", lambda ax: resp.reset_index(drop=True).plot(ax=ax, marker="o", color="#E8551C"))
    # S4
    el = c[c.name.str.startswith("Nimbus Launch Privilege") & c.treated_conv_rate.notna()]
    check("S4", "elite phone campaigns: control conversion >= 20%", el.control_conv_rate.mean() >= 0.20, f"control {el.control_conv_rate.mean():.1%}")
    check("S4", "elite phone discounts show ~0 uplift (T-C <= 4pp)", (el.treated_conv_rate - el.control_conv_rate).mean() <= 0.04,
          f"treated {el.treated_conv_rate.mean():.1%} vs control {el.control_conv_rate.mean():.1%}; discount spent Rs {el.discount_cost.sum() / 1e5:.1f} L")
    # S5
    iw = t["inventory_weekly"]
    mk = t["markdown_calendar"]
    dw = set(mk[(mk.sku_id == "TV-AUR-50U5") & (mk.action == "deal_of_week")].week_start)
    cw = c[c.sku_scope.str.contains("TV-AUR-50U5")]
    for r in cw.itertuples():
        for wk in pd.date_range(r.start - pd.Timedelta(days=r.start.weekday()), r.end, freq="7D"):
            dw.add(wk)
    s = iw[iw.sku_id.isin(["TV-AUR-55U7", "TV-AUR-50U5"]) & ~iw.is_partial_week].groupby(["week_start", "sku_id"]).sales.sum().unstack().fillna(0)
    s = s[s.index >= pd.Timestamp("2025-06-01")]
    s["promo"] = s.index.isin(dw)
    a = s.groupby("promo").mean()
    check("S5", "55U7 sells less in weeks when 50U5 is discounted", a.loc[True, "TV-AUR-55U7"] < 0.9 * a.loc[False, "TV-AUR-55U7"],
          f"55U7 {a.loc[False, 'TV-AUR-55U7']:.1f} -> {a.loc[True, 'TV-AUR-55U7']:.1f}/wk; 50U5 {a.loc[False, 'TV-AUR-50U5']:.1f} -> {a.loc[True, 'TV-AUR-50U5']:.1f}/wk")
    kp = tr["cannibalisation_truth"]
    kr = kp[kp.substitute_group == "TV_AUR_50_55"]
    check("S5", "true kappa for TV_AUR_50_55 (targeted) in 0.2-0.6", kr[kr.promo_source == "targeted"].kappa_same_group.between(0.2, 0.6).all() and len(kr) > 0,
          kr[["promo_source", "kappa_same_group", "kappa_total_shift"]].to_string(index=False).replace("\n", "; "))
    # S6
    rd = t["regional_demand"]
    ac = rd[(rd.category == "AC") & rd.week_start.between("2025-10-06", "2025-11-30")]
    ns = t["stores"].groupby("city_code").size()
    per = ac.groupby("city_code").units.sum() / ns
    north = per[["DEL", "JAI", "LKO", "CHD"]].mean()
    check("S6", "Oct-Nov AC units per store: Chennai >= 2x North", per["CHE"] >= 2 * north, f"Chennai {per['CHE']:.1f} vs North {north:.1f} units/store")
    ch = sn[sn.store_id.isin(["CHE-01", "CHE-02"]) & sn.sku_id.str.startswith("AC-")]
    ccov = ch.on_hand.sum() / max(ch.avg_daily_sales_28d.sum(), 1e-9)
    check("S6", "Chennai AC stock high (category cover >= 45 d)", ccov >= 45, f"{ch.on_hand.sum()} units, {ccov:.0f} days cover")
    nac = c[c.name.str.startswith("National AC Festive") | c.name.str.startswith("Winter AC Clearance")]
    check("S6", "national off-season AC campaigns earned little (T-C <= 1.5pp)", ((nac.treated_conv_rate - nac.control_conv_rate) <= 0.015).all(),
          "; ".join(f"{r.name}: T {r.treated_conv_rate:.2%} C {r.control_conv_rate:.2%}" for r in nac.itertuples()))
    # S7
    kl = rd[rd.category.isin(["TV", "REF"])].groupby(["city_code", "week_start"]).units.sum().reset_index()
    def lift(city, a, b):
        x = kl[kl.city_code == city].set_index("week_start").units
        return x[a:b].mean() / x["2025-07-01":"2025-08-31"].mean()
    kol = lift("KOL", "2025-09-22", "2025-09-29")
    oth = np.mean([lift(cc, "2025-09-22", "2025-09-29") for cc in ("MUM", "BLR", "CHE", "HYD")])
    check("S7", "Kolkata TV+REF Puja-week lift >= 1.7x and above other metros", kol >= 1.7 and kol > oth + 0.3, f"Kolkata {kol:.2f}x vs other metros {oth:.2f}x")
    kc = sn[sn.store_id.str.startswith("KOL") & sn.sku_id.str.match(r"^(TV|REF)-") & sn.is_ranged]
    kcov = kc.on_hand.sum() / max(kc.avg_daily_sales_28d.sum(), 1e-9)
    check("S7", "Kolkata TV/REF stock adequate (cover >= 30 d)", kcov >= 30, f"{kcov:.0f} days")
    # S8
    o = t["orders"]
    oc = o[(o.status == "completed") & o.customer_id.notna()].sort_values("order_date")
    gaps = oc.groupby("customer_id").order_date.apply(lambda s: s.diff().dt.days.dropna().median())
    popg = oc.groupby("customer_id").order_date.apply(lambda s: s.diff().dt.days.dropna()).median()
    lastd = oc.groupby("customer_id").order_date.max()
    eg = gaps.reindex(lastd.index).fillna(popg).clip(lower=30)
    since = (today - lastd).dt.days
    atrisk = since[(since >= 1.5 * eg) & (since < 3 * eg) & (since <= 365)].index
    wmv = w[(w.category == "WM") & (w.date >= today - pd.Timedelta(days=14))].customer_id.unique()
    n8 = len(set(atrisk) & set(wmv))
    check("S8", "~1,300 at-risk customers viewed WM in the last 14 days (1,000-1,700)", 1000 <= n8 <= 1700, f"{n8:,} of {len(atrisk):,} at-risk customers")
    ra = c[c.name.str.startswith("Welcome Back") & c.treated_repeat_180d.notna()]
    check("S8", "appliance win-back campaigns raise repeat_180d (T > C)", (ra.treated_repeat_180d > ra.control_repeat_180d).mean() >= 0.6,
          f"T {ra.treated_repeat_180d.mean():.1%} vs C {ra.control_repeat_180d.mean():.1%} over {len(ra)} campaigns")
    # S9
    ib = t["install_bookings"]
    b2 = ib[(ib.store_id == "BLR-02") & ib.date.between("2026-11-02", "2026-11-08")]
    u = (b2.booked_slots / b2.install_slots).mean()
    others = ib[ib.is_forward & (ib.store_id != "BLR-02") & ib.date.between("2026-11-02", "2026-11-08")]
    check("S9", "BLR-02 installs 88-96% booked for 2-8 Nov", 0.88 <= u <= 0.96, f"{u:.0%} (other stores avg {(others.booked_slots / others.install_slots).mean():.0%})")
    # S10
    l = t["order_lines"].merge(o[["order_id", "store_id", "status"]], on="order_id").merge(t["stores"][["store_id", "city_code"]], on="store_id")
    l = l[l.status == "completed"]
    lap = l[l.sku_id.str.startswith("LAP-")].groupby("city_code").order_id.nunique()
    bag = l[l.sku_id.str.startswith("ACC-") & l.order_id.isin(l[l.sku_id.str.startswith("LAP-")].order_id)]
    bag = bag.merge(t["products"][["sku_id", "subcategory"]], on="sku_id")
    bag = bag[bag.subcategory == "ACC_BAG"].groupby("city_code").order_id.nunique()
    rate = (bag / lap).fillna(0)
    peer = rate.drop("HYD").mean()
    check("S10", "Hyderabad laptop-bag attach ~9% vs ~22% peers (gap >= 8pp)", rate["HYD"] <= 0.13 and peer - rate["HYD"] >= 0.08,
          f"HYD {rate['HYD']:.1%} vs peer avg {peer:.1%}")


def determinism_note():
    p = SYNTH_DIR / "_determinism.json"
    if p.exists():
        d = json.loads(p.read_text())
        check("determinism", "SEED=42 twice -> identical table hashes", d.get("identical", False), d.get("detail", ""))


# ============================================================================ report
def write_report(t, tr):
    man = json.loads((SYNTH_DIR / "_manifest.json").read_text())
    df = pd.DataFrame(RESULTS)
    n_fail = (df.status == "FAIL").sum()
    L = ["# Data Validation Report - Prometheus Digital Twin", "",
         f"Generated by `python -m data_gen.validate` · seed {man['seed']} · generation time {man['elapsed_s']} s", "",
         f"**{(df.status == 'PASS').sum()} passed · {(df.status == 'WARN').sum()} warnings · {n_fail} failed**", "",
         "## Row counts", "", "| table | rows |", "|---|---:|"]
    L += [f"| {k} | {v['rows']:,} |" for k, v in man["tables"].items()]
    L += ["", "Hidden truth tables (`data/_truth`, tests only):", "", "| table | rows |", "|---|---:|"]
    L += [f"| {k} | {v['rows']:,} |" for k, v in man["truth"].items()]
    for sec in df.section.unique():
        L += ["", f"## {sec}", "", "| status | check | detail |", "|---|---|---|"]
        for r in df[df.section == sec].itertuples():
            L.append(f"| {r.status} | {r.check} | {str(r.detail).replace('|', '/')} |")
    o, l = t["orders"], t["order_lines"]
    oc = o[o.status == "completed"]
    L += ["", "## Key distributions", "",
          f"- Orders: {len(oc):,} completed, {o.status.eq('cancelled').sum():,} cancelled; guests {oc.is_guest.mean():.1%}; "
          f"channel mix " + ", ".join(f"{k} {v:.0%}" for k, v in oc.channel.value_counts(normalize=True).items()),
          f"- Lines per order {len(l) / len(o):.2f}; median order value Rs {oc.total.median():,.0f}; mean Rs {oc.total.mean():,.0f}",
          f"- Payment mix: " + ", ".join(f"{k} {v:.0%}" for k, v in oc.payment_type.value_counts(normalize=True).items()),
          f"- Revenue by category: " + ", ".join(f"{k} {v / 1e7:.1f} Cr" for k, v in l.groupby("category").line_total.sum().sort_values(ascending=False).items()),
          f"- Late deliveries (online): {o[o.channel != 'store'].is_late.mean():.1%} (Olist reference 6.8%)",
          f"- Review rating distribution: " + ", ".join(f"{k}* {v:.0%}" for k, v in t["reviews"].rating.value_counts(normalize=True).sort_index().items()),
          f"- Returns: {len(t['returns']):,} lines ({len(t['returns']) / len(l):.1%})",
          f"- Exposures: {len(t['exposures']):,}; treated {t['exposures'].group.eq('T').mean():.1%}",
          ""]
    (REPO_DIR / "docs").mkdir(exist_ok=True)
    (REPO_DIR / "docs" / "DATA_VALIDATION_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    html = ["<!doctype html><html><head><meta charset='utf-8'><title>Prometheus data report</title>",
            "<style>body{font:14px system-ui;margin:24px;max-width:1100px}td,th{border-bottom:1px solid #ddd;padding:4px 8px;text-align:left}"
            ".PASS{color:#12915A}.FAIL{color:#D12C3E}.WARN{color:#B7800F}</style></head><body><h1>Prometheus digital twin - validation</h1>"]
    html.append(f"<p>{(df.status == 'PASS').sum()} passed, {(df.status == 'WARN').sum()} warnings, {n_fail} failed</p><table>")
    for r in df.itertuples():
        html.append(f"<tr><td class='{r.status}'>{r.status}</td><td>{r.section}</td><td>{r.check}</td><td>{r.detail}</td></tr>")
    html.append("</table>")
    for title, b64 in CHARTS:
        html.append(f"<h3>{title}</h3>" + (f"<img src='data:image/png;base64,{b64}'/>" if b64 else ""))
    html.append("</body></html>")
    (DATA_DIR / "_report.html").write_text("\n".join(html), encoding="utf-8")
    return n_fail


def main():
    t, tr = load()
    for fn in (row_counts, integrity):
        fn(t)
    realism(t, tr)
    stories(t, tr)
    determinism_note()
    n_fail = write_report(t, tr)
    df = pd.DataFrame(RESULTS)
    with pd.option_context("display.max_colwidth", 130, "display.width", 250):
        print(df[["status", "section", "check", "detail"]].to_string(index=False))
    print(f"\n{(df.status == 'PASS').sum()} PASS / {(df.status == 'WARN').sum()} WARN / {n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
