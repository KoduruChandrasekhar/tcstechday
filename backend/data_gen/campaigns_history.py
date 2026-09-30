"""The historical campaign calendar of a *naive* past marketing team (PLAN §6.5).

Campaigns are specified by the team's intent (objective, offer, scope, targeting
rule on *observable* attributes, channels, dates). Who is actually exposed,
who converts and what it earns are decided later by the world simulator.
The ``template`` label (e.g. ``wrong_audience``) is design truth and is only
written to ``_truth``.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

METRO = ["MUM", "DEL", "BLR", "HYD", "CHE", "KOL", "PUN"]
NORTH = ["DEL", "JAI", "LKO", "CHD"]
SOUTH = ["BLR", "HYD", "CHE", "KOC"]
WEST = ["MUM", "PUN", "AMD"]
ALL = "ALL"


def _c(name, objective, template, start, days, scope, rule, offer_type, depth=0.0, cities=ALL, channels=None,
       cap=8000, flat=0, free_service=None, bundle=None, role="marketing"):
    return dict(name=name, objective=objective, template=template, start=start, end=start + timedelta(days=days - 1),
                sku_scope=scope, target_rule=rule, offer_type=offer_type, discount_pct=depth, flat_inr=flat,
                free_service_sku=free_service, bundle_skus=bundle or [], cities=cities,
                channels=channels or ["sms", "email", "whatsapp"], cap=cap, approved_by_role=role)


def cat(*c):
    return {"type": "category", "values": list(c)}


def sub(*s):
    return {"type": "subcategory", "values": list(s)}


def skus(*s):
    return {"type": "skus", "values": list(s)}


def broad(min_orders=1, cities=ALL):
    return {"type": "broad", "min_orders": min_orders, "cities": cities}


def build_campaign_plan(rng: np.random.Generator) -> list[dict]:
    D = date
    P = []
    # ---------------------------------------------------------------- A. festival pushes
    P += [
        _c("Diwali TV Dhamaka 2024", "festival_push", "festival_broad_deep", D(2024, 10, 18), 17, cat("TV"), broad(), "pct_off", 0.20, cap=12000),
        _c("Diwali Appliance Fest 2024", "festival_push", "festival_broad", D(2024, 10, 20), 15, cat("REF", "WM"), broad(), "pct_off", 0.15, cap=9000),
        _c("Dhanteras Kitchen Utsav 2024", "festival_push", "festival_regional", D(2024, 10, 24), 7, cat("KIT"), broad(cities=NORTH + WEST), "pct_off", 0.12, cities=NORTH + WEST, cap=6000),
        _c("Navratri Phone Fiesta 2024", "festival_push", "festival_broad", D(2024, 10, 1), 12, cat("PHN"), broad(), "pct_off", 0.10, cap=8000),
        _c("Christmas Gifting 2024", "festival_push", "festival_broad", D(2024, 12, 18), 14, cat("AUD", "WEA"), broad(), "pct_off", 0.15, cap=8000),
        _c("Pongal Home Upgrade 2025", "festival_push", "festival_regional", D(2025, 1, 8), 9, cat("TV", "REF"), broad(cities=SOUTH), "pct_off", 0.10, cities=SOUTH, cap=5000),
        _c("Diwali TV Dhamaka 2025", "festival_push", "festival_broad_deep", D(2025, 10, 6), 18, cat("TV"), broad(), "pct_off", 0.20, cap=12000),
        _c('Hyderabad Festive 55" Upgrade 2025', "festival_push", "targeted_intent_bundle", D(2025, 10, 6), 17, sub("TV_55"),
           {"type": "category_browsers", "category": "TV", "days": 30, "cities": ["HYD"]}, "bundle_pct", 0.10, cities=["HYD"],
           channels=["whatsapp", "app_push"], cap=1500, bundle=["SRV-INS-TV", "SRV-PP-1Y-L"]),
        _c("Diwali Appliance Fest 2025", "festival_push", "festival_broad", D(2025, 10, 8), 16, cat("REF", "WM"), broad(), "pct_off", 0.15, cap=9000),
        _c("Dhanteras Kitchen Utsav 2025", "festival_push", "festival_regional", D(2025, 10, 12), 7, cat("KIT"), broad(cities=NORTH + WEST), "pct_off", 0.12, cities=NORTH + WEST, cap=6000),
        _c("Navratri Phone Fiesta 2025", "festival_push", "festival_broad", D(2025, 9, 20), 12, cat("PHN"), broad(), "pct_off", 0.10, cap=8000),
        _c("Christmas Gifting 2025", "festival_push", "festival_broad", D(2025, 12, 18), 14, cat("AUD", "WEA"), broad(), "pct_off", 0.15, cap=8000),
        _c("Pongal Home Upgrade 2026", "festival_push", "festival_regional", D(2026, 1, 8), 9, cat("TV", "REF"), broad(cities=SOUTH), "pct_off", 0.10, cities=SOUTH, cap=5000),
        _c("Holi Colours of Sound 2025", "festival_push", "festival_regional", D(2025, 3, 8), 7, cat("AUD"), broad(cities=NORTH), "pct_off", 0.10, cities=NORTH, cap=4000),
        _c("Eid Celebration 2026", "festival_push", "festival_regional", D(2026, 3, 12), 9, cat("PHN", "TV"), broad(cities=["HYD", "LKO", "KOL"]), "pct_off", 0.08, cities=["HYD", "LKO", "KOL"], cap=4000),
        _c("Akshaya Tritiya Appliances 2026", "festival_push", "festival_regional", D(2026, 4, 14), 7, cat("REF", "WM", "KIT"), broad(cities=SOUTH + WEST), "pct_off", 0.08, cities=SOUTH + WEST, cap=5000),
        _c("Dussehra Laptop Deals 2025", "festival_push", "festival_broad", D(2025, 9, 25), 11, cat("LAP"), broad(), "pct_off", 0.10, cap=8000),
    ]
    # ---------------------------------------------------------------- B. deal blasts (S3 fatigue)
    deal_scopes = [cat("ACC"), sub("AUD_EARBUDS"), cat("WEA"), sub("PHN_BUDGET"), sub("KIT_AF", "KIT_MIX"), sub("AUD_SPK")]
    rule_dh = {"type": "deal_hunters", "cities": METRO, "min_promo_share": 0.4, "min_orders": 2}
    starts = [D(2025, 1, 10) + timedelta(days=int(38 * k + rng.integers(-3, 4))) for k in range(15)]
    starts += [D(2026, 8, 2) + timedelta(days=int(round(6.5 * k))) for k in range(9)]
    for k, s in enumerate(starts):
        depth = float(rng.choice([0.15, 0.20, 0.25]))
        P.append(_c(f"Flash Deals #{k + 1:02d}", "deal_blast", "deal_blast", s, 3, deal_scopes[k % len(deal_scopes)], rule_dh,
                    "pct_off", depth, cities=METRO, channels=["whatsapp", "sms", "app_push"], cap=4000))
    # ---------------------------------------------------------------- C. elite phone buyers (S4 sure things)
    rule_el = {"type": "category_buyers", "category": "PHN", "tiers": ["elite", "gold"], "days": 900}
    for s, dp, ot in [(D(2024, 10, 3), 0.10, "pct_off"), (D(2025, 3, 5), 0.12, "pct_off"), (D(2025, 9, 7), 0.10, "pct_off"),
                      (D(2025, 12, 10), 0.08, "pct_off"), (D(2026, 3, 4), 0.0, "early_access"), (D(2026, 9, 7), 0.10, "pct_off")]:
        nm = "Nimbus Launch Early Access (Circle)" if ot == "early_access" else "Nimbus Launch Privilege (Circle)"
        P.append(_c(f"{nm} {s:%b %Y}", "launch", "elite_discount" if ot == "pct_off" else "elite_nonprice", s, 21,
                    sub("PHN_PREMIUM", "PHN_FLAGSHIP"), rule_el, ot, dp, channels=["whatsapp", "email", "app_push"], cap=2500))
    # ---------------------------------------------------------------- D. Aurex 50U5 value weeks (S5 cannibalisation)
    for s, dp in [(D(2025, 4, 12), 0.15), (D(2025, 7, 19), 0.18), (D(2025, 10, 4), 0.18), (D(2026, 1, 17), 0.15), (D(2026, 5, 16), 0.20)]:
        P.append(_c(f'Aurex 50" Value Week {s:%b %Y}', "category_push", "single_sku_discount", s, 10, skus("TV-AUR-50U5"),
                    {"type": "category_browsers", "category": "TV", "days": 45, "cities": ALL}, "pct_off", dp,
                    channels=["whatsapp", "sms", "email"], cap=5000, role="merchandising"))
    # ---------------------------------------------------------------- E. AC (S6)
    P += [
        _c("Winter AC Clearance 2024", "clearance", "national_ac_offseason", D(2024, 10, 15), 27, cat("AC"), broad(), "pct_off", 0.15, cap=10000, role="merchandising"),
        _c("Pre-summer AC Booking 2025", "category_push", "national_ac", D(2025, 3, 10), 22, cat("AC"), broad(), "pct_off", 0.10, cap=9000),
        _c("North Summer Cool Deals 2025", "category_push", "regional_ac_inseason", D(2025, 4, 10), 30, cat("AC"), broad(cities=NORTH), "pct_off", 0.12, cities=NORTH, cap=6000),
        _c("AC Free Installation 2025", "category_push", "free_service", D(2025, 5, 5), 21, cat("AC"), broad(), "free_service", 0.0, free_service="SRV-INS-AC", cap=9000),
        _c("Monsoon AC Clearance 2025", "clearance", "national_ac", D(2025, 8, 1), 20, cat("AC"), broad(), "pct_off", 0.18, cap=9000, role="merchandising"),
        _c("National AC Festive Offer 2025", "festival_push", "national_ac_offseason", D(2025, 10, 20), 27, cat("AC"), broad(), "pct_off", 0.15, cap=10000),
        _c("Chennai All-Weather AC Offer 2026", "category_push", "regional_ac_inseason", D(2026, 2, 1), 20, cat("AC"), broad(cities=["CHE"]), "pct_off", 0.10, cities=["CHE"], cap=3000),
        _c("North Summer Cool Deals 2026", "category_push", "regional_ac_inseason", D(2026, 4, 8), 30, cat("AC"), broad(cities=NORTH), "pct_off", 0.12, cities=NORTH, cap=6000),
    ]
    # ---------------------------------------------------------------- F. regional festivals (S7 etc.)
    P += [
        _c("Durga Puja Home Utsav 2024", "festival_push", "festival_regional", D(2024, 10, 1), 13, cat("REF", "TV"), broad(cities=["KOL"]), "pct_off", 0.10, cities=["KOL"], cap=4000),
        _c("Durga Puja Home Utsav 2025", "festival_push", "festival_regional", D(2025, 9, 20), 13, cat("REF", "TV"), broad(cities=["KOL"]), "pct_off", 0.10, cities=["KOL"], cap=4000),
        _c("Onam Sadya Savings 2025", "festival_push", "festival_regional", D(2025, 8, 20), 17, cat("TV", "REF", "WM"), broad(cities=["KOC"]), "pct_off", 0.10, cities=["KOC"], cap=2500),
        _c("Onam Sadya Savings 2026", "festival_push", "festival_regional", D(2026, 8, 12), 15, cat("TV", "REF", "WM"), broad(cities=["KOC"]), "pct_off", 0.10, cities=["KOC"], cap=2500),
        _c("Ganpati Bappa TV Offer 2025", "festival_push", "festival_regional", D(2025, 8, 22), 16, cat("TV"), broad(cities=["MUM", "PUN"]), "pct_off", 0.10, cities=["MUM", "PUN"], cap=5000),
        _c("Ganpati Bappa TV Offer 2026", "festival_push", "festival_regional", D(2026, 9, 8), 17, cat("TV"), broad(cities=["MUM", "PUN"]), "pct_off", 0.10, cities=["MUM", "PUN"], cap=5000),
        _c("Navratri Garba Deals 2025", "festival_push", "festival_regional", D(2025, 9, 18), 14, cat("PHN", "AUD"), broad(cities=["AMD"]), "pct_off", 0.10, cities=["AMD"], cap=2500),
        _c("Kochi Christmas Gifting 2025", "festival_push", "festival_regional", D(2025, 12, 15), 17, cat("WEA", "AUD"), broad(cities=["KOC"]), "pct_off", 0.12, cities=["KOC"], cap=2500),
    ]
    # ---------------------------------------------------------------- G. reactivation / win-back (S8 retention)
    rule_react = {"type": "lapsed", "min_days": 120, "max_days": 420, "categories": ["WM", "REF", "AC"], "browse_days": 30}
    for s in [D(2025, 1, 20), D(2025, 3, 25), D(2025, 6, 10), D(2025, 8, 18), D(2025, 11, 24), D(2026, 2, 9), D(2026, 5, 4), D(2026, 7, 13)]:
        P.append(_c(f"Welcome Back: Free Install + Rs1,500 Off {s:%b %Y}", "reactivation", "reactivation_appliance", s, 14,
                    cat("WM", "REF", "AC"), rule_react, "flat_off", 0.0, flat=1500, free_service="INSTALL",
                    channels=["whatsapp", "sms", "email"], cap=3000))
    rule_wb = {"type": "lapsed", "min_days": 180, "max_days": 720, "categories": None, "browse_days": None}
    for s in [D(2025, 2, 15), D(2025, 5, 20), D(2025, 9, 1), D(2025, 12, 1), D(2026, 3, 23), D(2026, 6, 15)]:
        P.append(_c(f"We Miss You 10% {s:%b %Y}", "reactivation", "winback_generic", s, 14,
                    cat("TV", "PHN", "LAP", "TAB", "AUD", "WEA", "KIT", "ACC"), rule_wb, "pct_off", 0.10,
                    channels=["email", "sms"], cap=5000))
    # ---------------------------------------------------------------- H. clearance of end-of-life models
    rule_ps = {"type": "promo_sensitive", "min_promo_share": 0.3, "min_orders": 1, "cities": ALL}
    for s, c in [(D(2025, 1, 6), "LAP"), (D(2025, 4, 21), "PHN"), (D(2025, 6, 23), "TV"), (D(2025, 9, 15), "LAP"),
                 (D(2025, 11, 24), "PHN"), (D(2026, 2, 23), "TV"), (D(2026, 4, 27), "LAP"), (D(2026, 6, 22), "PHN")]:
        P.append(_c(f"Clearance: Last-gen {c} {s:%b %Y}", "clearance", "clearance_eol", s, 14, {"type": "eol_in_category", "values": [c]},
                    rule_ps, "pct_off", 0.22, channels=["sms", "email", "app_push"], cap=6000, role="merchandising"))
    # ---------------------------------------------------------------- I. cross-sell
    for s in [D(2025, 2, 3), D(2025, 7, 7), D(2025, 10, 27), D(2026, 2, 2), D(2026, 7, 6)]:
        P.append(_c(f"Laptop Buddy Bundle {s:%b %Y}", "cross_sell", "cross_sell", s, 14, sub("ACC_BAG", "ACC_MSE"),
                    {"type": "recent_buyers", "category": "LAP", "days": 60}, "bundle_pct", 0.10,
                    bundle=["ACC-PRE-BAG15", "ACC-PRE-MSE01"], channels=["email", "app_push"], cap=2500))
    for s in [D(2025, 1, 27), D(2025, 4, 28), D(2025, 8, 25), D(2025, 12, 8), D(2026, 5, 25)]:
        P.append(_c(f"Earbuds for your new phone {s:%b %Y}", "cross_sell", "cross_sell", s, 14, sub("AUD_EARBUDS"),
                    {"type": "recent_buyers", "category": "PHN", "days": 45}, "pct_off", 0.15, channels=["whatsapp", "app_push"], cap=2500))
    for s in [D(2025, 1, 13), D(2025, 6, 2), D(2025, 11, 10), D(2026, 6, 8)]:
        P.append(_c(f"Complete your home theatre {s:%b %Y}", "cross_sell", "cross_sell", s, 14, sub("AUD_SB"),
                    {"type": "recent_buyers", "category": "TV", "days": 60}, "pct_off", 0.10, channels=["whatsapp", "email"], cap=2500))
    # ---------------------------------------------------------------- J. back to college
    for s in [D(2025, 6, 16), D(2025, 7, 7), D(2025, 7, 21), D(2026, 6, 15), D(2026, 7, 6), D(2026, 7, 20)]:
        P.append(_c(f"Back to College {s:%d %b %Y}", "category_push", "age_targeted", s, 12, cat("LAP", "TAB"),
                    {"type": "age", "bands": ["18-24", "25-34"], "browse_category": "LAP", "browse_days": 45}, "pct_off", 0.10,
                    channels=["app_push", "email", "sms"], cap=5000))
    # ---------------------------------------------------------------- K. wrong audiences
    P += [
        _c("Premium TV Upgrade", "category_push", "wrong_audience", D(2025, 3, 3), 14, sub("TV_65", "TV_75"),
           {"type": "age", "bands": ["18-24"], "browse_category": None}, "pct_off", 0.15, cap=4000),
        _c("Kitchen Essentials Week", "category_push", "wrong_audience", D(2025, 5, 12), 10, cat("KIT"),
           {"type": "age", "bands": ["18-24"], "browse_category": None}, "pct_off", 0.12, cap=4000),
        _c("Gaming Weekend", "category_push", "wrong_audience", D(2025, 11, 3), 7, cat("GAM"),
           {"type": "age", "bands": ["55+", "45-54"], "browse_category": None}, "pct_off", 0.15, cap=4000),
        _c("Side-by-Side Fridge Deal", "category_push", "wrong_audience", D(2026, 1, 5), 14, sub("REF_SBS"),
           {"type": "age", "bands": ["18-24"], "browse_category": None}, "pct_off", 0.12, cap=4000),
    ]
    # ---------------------------------------------------------------- L. loyalty / non-price
    rule_loy = {"type": "loyalty", "tiers": ["gold", "elite"]}
    P += [
        _c("Circle Double Points Feb 2025", "loyalty", "loyalty_points", D(2025, 2, 24), 14, cat("TV", "PHN", "LAP", "AUD", "WEA", "REF", "WM"), rule_loy, "loyalty_points", 0.10, channels=["email", "app_push", "whatsapp"], cap=5000),
        _c("Circle Double Points Aug 2025", "loyalty", "loyalty_points", D(2025, 8, 4), 14, cat("TV", "PHN", "LAP", "AUD", "WEA", "REF", "WM"), rule_loy, "loyalty_points", 0.10, channels=["email", "app_push", "whatsapp"], cap=5000),
        _c("Circle Double Points May 2026", "loyalty", "loyalty_points", D(2026, 5, 11), 14, cat("TV", "PHN", "LAP", "AUD", "WEA", "REF", "WM"), rule_loy, "loyalty_points", 0.10, channels=["email", "app_push", "whatsapp"], cap=5000),
        _c("Circle Early Access: Aurex Q8", "launch", "early_access", D(2025, 5, 12), 14, skus("TV-AUR-55Q8"), {"type": "loyalty", "tiers": ["silver", "gold", "elite"]}, "early_access", 0.0, channels=["email", "app_push", "whatsapp"], cap=6000),
        _c("Circle Early Access: Kairo Air 2026", "launch", "early_access", D(2026, 7, 28), 16, skus("LAP-KAI-14A26"), {"type": "loyalty", "tiers": ["silver", "gold", "elite"]}, "early_access", 0.0, channels=["email", "app_push", "whatsapp"], cap=6000),
        _c("Circle Free ProtectPlus Month", "loyalty", "free_service", D(2025, 11, 17), 14, cat("PHN", "LAP", "TV"), rule_loy, "free_service", 0.0, free_service="PROTECTPLUS", channels=["email", "app_push", "whatsapp"], cap=5000),
    ]
    # ---------------------------------------------------------------- M. retailer sale events
    for s, cats_ in [(D(2025, 1, 21), ("TV", "LAP")), (D(2025, 1, 22), ("PHN", "AUD")), (D(2026, 1, 21), ("TV", "LAP")), (D(2026, 1, 22), ("PHN", "AUD")),
                     (D(2025, 8, 8), ("TV", "REF")), (D(2025, 8, 9), ("PHN", "WEA")), (D(2026, 8, 8), ("TV", "REF")), (D(2026, 8, 9), ("PHN", "WEA"))]:
        nm = "Republic Day Sale" if s.month == 1 else "Independence Day Sale"
        P.append(_c(f"{nm} {s.year}: {' & '.join(cats_)}", "festival_push", "retailer_sale_broad", s, 6, cat(*cats_), broad(), "pct_off", 0.10, cap=10000))
    # ---------------------------------------------------------------- N. partner-bank cashback
    rule_hv = {"type": "high_value", "min_spend": 60000}
    for s in [D(2024, 10, 20), D(2025, 1, 22), D(2025, 8, 9), D(2025, 10, 10), D(2026, 1, 22), D(2026, 8, 9)]:
        P.append(_c(f"Partner Bank Cashback {s:%b %Y}", "festival_push", "bank_cashback", s, 10, cat("PHN", "LAP", "TV"), rule_hv,
                    "bank_cashback", 0.10, channels=["email", "sms"], cap=6000))
    # ---------------------------------------------------------------- O. launches / early access
    P += [
        _c("Nimbus Flagship Pre-book", "launch", "early_access", D(2025, 9, 1), 14, sub("PHN_FLAGSHIP"), {"type": "category_browsers", "category": "PHN", "days": 45, "cities": ALL}, "early_access", 0.0, channels=["app_push", "email"], cap=5000),
        _c("Orbix Watch Launch", "launch", "early_access", D(2025, 10, 27), 14, sub("WEA_WATCH"), {"type": "category_browsers", "category": "WEA", "days": 45, "cities": ALL}, "early_access", 0.0, channels=["app_push", "email"], cap=4000),
        _c("Hexa Console Pre-order", "launch", "early_access", D(2025, 11, 17), 14, sub("GAM_CON"), {"type": "category_browsers", "category": "GAM", "days": 60, "cities": ALL}, "early_access", 0.0, channels=["app_push", "email"], cap=3000),
        _c("Tessera Gaming Launch", "launch", "early_access", D(2026, 4, 6), 14, sub("LAP_GAMING"), {"type": "category_browsers", "category": "LAP", "days": 45, "cities": ALL}, "early_access", 0.0, channels=["app_push", "email"], cap=4000),
    ]
    # ---------------------------------------------------------------- P. misc
    P += [
        _c("Monsoon Kitchen Fest 2025", "category_push", "category_broad", D(2025, 7, 14), 10, cat("KIT"), broad(), "pct_off", 0.12, cap=8000),
        _c("Fitness January 2026", "category_push", "age_targeted", D(2026, 1, 5), 12, cat("WEA"), {"type": "age", "bands": ["25-34", "35-44"], "browse_category": None}, "pct_off", 0.12, cap=6000),
    ]
    P.sort(key=lambda c: (c["start"], c["name"]))
    counters: dict[int, int] = {}
    for c in P:
        y = c["start"].year
        counters[y] = counters.get(y, 0) + 1
        c["campaign_id"] = f"CMP-{y}-{counters[y]:03d}"
    return P
