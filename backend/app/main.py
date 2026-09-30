"""PromoForge API.  Run from repo root:  python -m uvicorn app.main:app --app-dir backend --port 8765"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import engine as E

app = FastAPI(title="Prometheus PromoForge")
WORLD = E.World()
E.generate_candidates(WORLD)  # warm cache
STATIC = Path(__file__).parent / "static"
CAMPAIGNS: dict[str, dict] = {}
LENSES = ("marketing", "merchandising", "store_ops")


class Sim(BaseModel):
    segment: str
    sku: str
    city: str
    offer_idx: int = 1
    channel: str = "WhatsApp + App"
    cap: int | None = None
    window: str = E.DEFAULT_WINDOW


class Seal(BaseModel):
    lens: str
    decision: str
    note: str = ""


def _eval(s: Sim):
    try:
        return E.evaluate(WORLD, s.segment, s.sku, s.city, s.offer_idx, s.channel, s.cap, s.window)
    except KeyError as e:
        raise HTTPException(400, f"unknown {e}")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/meta")
def meta():
    return {"today": str(E.DEMO_TODAY.date()), "segments": {k: v * E.SCALE for k, v in WORLD.seg_size.items()}, "scale": E.SCALE,
            "products": [{"sku": k, "name": v["name"], "cat": v["cat"], "price": v["price"]} for k, v in WORLD.products.items()],
            "cities": [{"code": k, "name": v["city"]} for k, v in WORLD.cities.items()],
            "offers": [o[0] for o in E.OFFERS], "channels": list(E.CHANNELS),
            "windows": {k: {"name": v[0], "start": v[1], "end": v[2]} for k, v in E.WINDOWS.items()},
            "guardrails": E.GUARDRAILS, "weights": E.W,
            "data": {"customers": int(len(WORLD.customers)), "stores": int(len(WORLD.stores)), "skus": int(len(WORLD.all_products)),
                     "campaigns": int(len(WORLD.memory)), "dnc": WORLD.dnc}}


@app.get("/api/recommendations")
def recommendations(objective: str = "profit", window: str = E.DEFAULT_WINDOW, city: str | None = None, category: str | None = None):
    recs = E.generate_candidates(WORLD, objective, window)
    if city:
        recs = [r for r in recs if r["city"] == city]
    if category:
        recs = [r for r in recs if r["category"] == category]
    go = [r for r in recs if r["verdict"] in ("GO", "CONDITIONAL GO")]
    blocked = [r for r in recs if r["verdict"] == "BLOCK"]
    top = go[:15]
    tot_gp = sum(r["net_gp"] for r in top)
    counts = {v: sum(r["verdict"] == v for r in recs) for v in ("GO", "CONDITIONAL GO", "HOLD", "BLOCK")}
    reasons = {}
    for r in blocked:
        for b in r["blocks"]:
            k = "Stock-out risk" if "stock-out" in b else "Margin floor" if "margin" in b else "k-anonymity" if "anonymity" in b else "Other"
            reasons[k] = reasons.get(k, 0) + 1
    main_reason = max(reasons, key=reasons.get) if reasons else "n/a"
    insight = (f"Top {len(top)} plans add {E.inr(tot_gp)} net profit for {E.WINDOWS[window][0]}; {len(blocked)} candidates "
               f"blocked by guardrails, mostly for {main_reason.lower()}.") if top else "No feasible promotions for this filter."
    by_cat = {}
    for r in go:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["net_gp"]
    top_cat = max(by_cat, key=by_cat.get) if by_cat else None
    n_go = counts["GO"] + counts["CONDITIONAL GO"]
    insights = {
        "verdict": f"{n_go:,} of {len(recs):,} candidates ({n_go / max(len(recs), 1):.0%}) are safe to run; {counts['BLOCK']:,} are blocked outright.",
        "block": (f"{main_reason} is the top reason ({reasons.get(main_reason, 0):,} of {len(blocked):,} blocks)." if blocked else "Nothing blocked for this filter."),
        "cat": (f"{top_cat} leads with {E.inr(by_cat[top_cat])} net profit across runnable plans ({by_cat[top_cat] / max(sum(by_cat.values()), 1):.0%} of total)." if top_cat else "No runnable plans."),
        "funnel": f"{len(recs):,} evaluated → {n_go:,} pass guardrails → top {len(top)} recommended.",
    }
    return {"insights": insights, "kpis": {"candidates": len(recs), "net_gp_top": E.inr(tot_gp), "counts": counts,
                     "avg_readiness": round(sum(r["readiness"] for r in top) / max(len(top), 1), 1),
                     "leakage_all": E.inr(sum(r["leakage"] for r in recs))},
            "insight": insight, "top": top, "blocked": blocked[:16], "block_reasons": reasons, "gp_by_cat": by_cat,
            "opportunities": opportunities(window)}


def opportunities(window):
    rows, transfers = E.mismatch(WORLD, window)
    ops = []
    for r in sorted([r for r in rows if r["status"] == "EXCESS"], key=lambda r: -r["cover_days"])[:3]:
        ops.append({"type": "Excess stock", "text": f"{r['product']} in {r['city_name']}: {r['cover_days']:.0f} days of cover. Clearance candidate."})
    for r in sorted([r for r in rows if r["demand_per_day"] > 0.1 * E.SCALE], key=lambda r: r["cover_days"])[:3]:
        ops.append({"type": "Stock-out risk", "text": f"{r['product']} in {r['city_name']}: {r['cover_days']:.1f} days of cover. Don't promote; replenish first."})
    for (c, cat), v in sorted(WORLD.intent.items(), key=lambda kv: -kv[1])[:3]:
        ops.append({"type": "Demand surge", "text": f"Search intent for {cat} in {WORLD.cities[c]['city']} up {v - 1:.0%} (14d vs prior 60d)"})
    _, ws, we = E.WINDOWS[window]
    ev = WORLD.events[(WORLD.events.start <= we) & (WORLD.events.end >= ws)]
    for e in ev.itertuples():
        ops.append({"type": "Festival", "text": f"{e.name} ({e.start:%d %b}–{e.end:%d %b}) overlaps this window"})
    ops.append({"type": "At-risk customers", "text": f"{WORLD.seg_size.get('At-Risk Lapsers', 0) * E.SCALE:,} contactable lapsing customers: retention window"})
    return ops


@app.post("/api/simulate")
def simulate(s: Sim):
    r = _eval(s)
    fr = []
    for i in range(len(E.OFFERS)):
        x = E.evaluate(WORLD, s.segment, s.sku, s.city, i, s.channel, s.cap, s.window)
        fr.append({"offer": E.OFFERS[i][0], **{k: x[k] for k in ("net_gp", "incr_units", "p_stockout", "readiness", "verdict")}})
    r["frontier"] = fr
    cat = r["category"]
    hist = WORLD.regional[(WORLD.regional.city_code == s.city) & (WORLD.regional.category == cat)].sort_values("week_start").tail(52)
    r["history"] = {"weeks": hist.week_start.dt.strftime("%d %b %y").tolist(), "units": hist.units.fillna(0).tolist(),
                    "searches": hist.web_searches.fillna(0).tolist()}
    m = WORLD.memory.copy()
    m["d"] = (m.discount_pct - E.OFFERS[s.offer_idx][1]).abs() + (m.pred_roi - r["roi"]).abs() * 0.1
    fr_best = max(fr, key=lambda x: x["net_gp"])
    u = hist.units.fillna(0)
    r["insights"] = {
        "frontier": f"Highest-profit offer is {fr_best['offer']} ({E.inr(fr_best['net_gp'])}); deeper discounts buy units but erode margin.",
        "history": (f"Last 8 weeks averaged {u.tail(8).mean():,.0f} units/week vs {u.mean():,.0f} over the year ({u.tail(8).mean() / max(u.mean(), 1e-9) - 1:+.0%})." if len(u) else "No history for this city and category."),
        "waterfall": f"Of {E.inr(r['incr_gp'])} incremental profit, {E.inr(r['leakage'])} leaks to customers who'd buy anyway; {E.inr(r['net_gp'])} is kept.",
        "burn": (f"Runs out on day {r['stockout_day']}." if r["stockout_day"] else "Stock holds for the full window.") + f" Opening stock {r['stock']:,.0f}; {len(r['inbound'])} inbound PO(s).",
    }
    r["twins"] = [{"name": t.name, "pred_roi": round(t.pred_roi, 2), "actual_roi": round(t.actual_roi, 2),
                   "stockouts": int(t.oos_store_days_during), "disc": t.discount_pct} for t in m.nsmallest(3, "d").itertuples()]
    avg_a = sum(t["actual_roi"] for t in r["twins"]) / max(len(r["twins"]), 1)
    r["insights"]["twins"] = f"The 3 most similar past campaigns returned {avg_a:.2f}× on average vs {r['roi']}× predicted here."
    return r


@app.get("/api/mismatch")
def mismatch_api(window: str = E.DEFAULT_WINDOW):
    rows, transfers = E.mismatch(WORLD, window)
    cities = [{"city": v["city"], "lat": v["lat"], "lon": v["lon"], "stores": v["stores"],
               "short": sum(r["city"] == c and r["status"] == "SHORT" for r in rows),
               "excess": sum(r["city"] == c and r["status"] == "EXCESS" for r in rows)} for c, v in WORLD.cities.items()]
    return {"rows": rows, "transfers": transfers, "cities": cities,
            "insight": f"{len(transfers)} stock transfers would unlock promotions in short cities without new purchase orders."}


@app.get("/api/audiences")
def audiences():
    out = []
    for seg, n in WORLD.seg_size.items():
        u = WORLD.seg_uplift.get(seg, {})
        aff = {c: v for (s, c), v in WORLD.affinity.items() if s == seg}
        top = sorted(aff.items(), key=lambda kv: -kv[1])[:3]
        out.append({"segment": seg, "size": n * E.SCALE, "persuadable": WORLD.seg_persuadable.get(seg, 0), "fatigue": WORLD.fatigue.get(seg, 0),
                    "treated": u.get("treated", 0), "control": u.get("control", 0), "lift": u.get("lift", 0),
                    "top_categories": [f"{c} ×{v:.2f}" for c, v in top]})
    best = max(out, key=lambda x: x["lift"]) if out else None
    ins = f"{best['segment']} respond most to offers (+{best['lift'] * 100:.2f} pts conversion vs holdout)." if best else ""
    return {"segments": out, "model": WORLD.model_card, "dnc": WORLD.dnc * E.SCALE, "chart_insight": ins}


@app.post("/api/campaigns")
def create_campaign(s: Sim):
    r = _eval(s)
    if r["verdict"] == "BLOCK":
        raise HTTPException(409, {"msg": "Blocked by guardrails", "blocks": r["blocks"], "fix": r["what_would_change"]})
    cid = f"PF-{len(CAMPAIGNS) + 101}"
    CAMPAIGNS[cid] = {"id": cid, "rec": r, "status": "Pending sign-off", "seals": {l: None for l in LENSES}, "log": []}
    return CAMPAIGNS[cid]


@app.get("/api/campaigns")
def list_campaigns():
    return list(CAMPAIGNS.values())


@app.post("/api/campaigns/{cid}/seal")
def seal(cid: str, s: Seal):
    c = CAMPAIGNS.get(cid)
    if not c:
        raise HTTPException(404, "no campaign")
    if s.lens not in LENSES:
        raise HTTPException(400, "bad lens")
    c["seals"][s.lens] = s.decision
    c["log"].append(f"{s.lens}: {s.decision}" + (f": {s.note}" if s.note else ""))
    vals = list(c["seals"].values())
    c["status"] = "Rejected" if "reject" in vals else "Approved" if all(v == "approve" for v in vals) else "Pending sign-off"
    return c


@app.post("/api/campaigns/{cid}/timewarp")
def warp(cid: str):
    c = CAMPAIGNS.get(cid)
    if not c:
        raise HTTPException(404, "no campaign")
    if c["status"] != "Approved":
        raise HTTPException(409, "Campaign must be approved by all three lenses first")
    c["outcome"] = E.time_warp(WORLD, c["rec"])
    c["status"] = "Completed"
    return c


@app.get("/api/memory")
def memory():
    m = WORLD.memory.sort_values("start", ascending=False)
    rows = [{"id": r.campaign_id, "name": r.name, "objective": r.objective, "start": str(r.start.date()),
             "pred_roi": round(r.pred_roi, 2), "actual_roi": round(r.actual_roi, 2), "stockouts": int(r.oos_store_days_during),
             "leakage_pct": round(r.leak * 100), "gp": E.inr(r.gross_profit)} for r in m.itertuples()]
    c = WORLD.calib
    return {"rows": rows, "calibration": c,
            "insight": f"{c['n']} completed campaigns. Leave-one-out ROI forecast: mean abs. error {c['mae']}, bias {c['bias']}. Time Warp outcomes use this error band."}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
