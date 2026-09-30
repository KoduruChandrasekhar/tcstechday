"""Fictional consumer-electronics catalogue: 320 physical SKUs + 12 service SKUs.

All brands are invented (PLAN §6.2). Named "story" SKUs (Aurex 55U7 etc.) are placed
into the generated grid so that the planted scenarios have concrete anchors.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import CATEGORIES, HISTORY_START, DEMO_TODAY

CATEGORY_NAMES = {
    "TV": "Televisions", "PHN": "Smartphones", "LAP": "Laptops", "TAB": "Tablets", "AC": "Air conditioners",
    "REF": "Refrigerators", "WM": "Washing machines", "KIT": "Kitchen appliances", "AUD": "Audio",
    "WEA": "Wearables", "GAM": "Gaming & imaging", "ACC": "Accessories", "SRV": "Services",
}
# PLAN §6.2 margin bands, lifespans (months a model stays in the range), price erosion per month
CAT_SPEC = {
    #       margin band      life  erosion replacement_cycle_months  install
    "TV":  ((0.08, 0.14), 24, 0.007, 72, True),
    "PHN": ((0.05, 0.09), 16, 0.012, 30, False),
    "LAP": ((0.07, 0.11), 20, 0.008, 48, False),
    "TAB": ((0.07, 0.10), 22, 0.009, 40, False),
    "AC":  ((0.12, 0.18), 30, 0.003, 96, True),
    "REF": ((0.12, 0.18), 36, 0.002, 110, False),
    "WM":  ((0.12, 0.18), 36, 0.002, 96, True),
    "KIT": ((0.18, 0.26), 36, 0.002, 60, False),
    "AUD": ((0.20, 0.35), 20, 0.006, 30, False),
    "WEA": ((0.15, 0.25), 16, 0.008, 30, False),
    "GAM": ((0.06, 0.12), 30, 0.004, 48, False),
    "ACC": ((0.35, 0.55), 30, 0.000, 18, False),
}
BRAND_CODES = {"Aurex": "AUR", "Lumeo": "LUM", "Stellix": "STX", "Nimbus": "NIM", "Zyrox": "ZYR", "Aeris": "AER",
               "Kairo": "KAI", "Novix": "NVX", "Tessera": "TES", "Frostline": "FRL", "Coolara": "COO", "Voltra": "VOL",
               "Prometheus Essentials": "PRE", "Zenwave": "ZEN", "Orbix": "ORB", "Hexa": "HEX", "Pixelon": "PIX"}

# category, subcategory, n, price_lo, price_hi, brands(weights), label, weight_kg
SUBCATS = [
    ("TV", "TV_32", 6, 14000, 22000, {"Aurex": .4, "Lumeo": .35, "Stellix": .25}, '32" HD Smart TV', 6),
    ("TV", "TV_43", 7, 22000, 38000, {"Aurex": .4, "Lumeo": .35, "Stellix": .25}, '43" 4K Smart TV', 9),
    ("TV", "TV_50", 6, 32000, 48000, {"Lumeo": .55, "Stellix": .45}, '50" 4K Smart TV', 13),
    ("TV", "TV_55", 8, 42000, 95000, {"Lumeo": .5, "Stellix": .5}, '55" 4K Smart TV', 16),
    ("TV", "TV_65", 6, 65000, 160000, {"Aurex": .45, "Lumeo": .3, "Stellix": .25}, '65" 4K Smart TV', 24),
    ("TV", "TV_75", 3, 120000, 220000, {"Aurex": .5, "Stellix": .5}, '75" 4K Smart TV', 34),
    ("PHN", "PHN_BUDGET", 14, 8000, 15000, {"Nimbus": .35, "Zyrox": .4, "Aeris": .25}, "Smartphone", 0.4),
    ("PHN", "PHN_MID", 16, 15000, 35000, {"Nimbus": .4, "Zyrox": .35, "Aeris": .25}, "Smartphone", 0.4),
    ("PHN", "PHN_PREMIUM", 12, 35000, 80000, {"Nimbus": .5, "Zyrox": .25, "Aeris": .25}, "Smartphone", 0.45),
    ("PHN", "PHN_FLAGSHIP", 6, 80000, 150000, {"Nimbus": .7, "Aeris": .3}, "Smartphone", 0.45),
    ("LAP", "LAP_14", 10, 30000, 70000, {"Kairo": .45, "Novix": .35, "Tessera": .2}, '14" Laptop', 2.3),
    ("LAP", "LAP_15", 10, 35000, 85000, {"Kairo": .4, "Novix": .4, "Tessera": .2}, '15.6" Laptop', 2.8),
    ("LAP", "LAP_GAMING", 8, 75000, 180000, {"Tessera": .6, "Novix": .4}, "Gaming Laptop", 3.5),
    ("LAP", "LAP_PREMIUM", 8, 90000, 200000, {"Kairo": .6, "Novix": .4}, "Ultrabook", 2.0),
    ("TAB", "TAB_ENTRY", 6, 12000, 25000, {"Nimbus": .5, "Kairo": .5}, "Tablet", 0.8),
    ("TAB", "TAB_MID", 6, 25000, 50000, {"Nimbus": .5, "Kairo": .5}, "Tablet", 0.8),
    ("TAB", "TAB_PRO", 4, 50000, 90000, {"Nimbus": .6, "Kairo": .4}, "Pro Tablet", 0.9),
    ("AC", "AC_1T", 8, 28000, 40000, {"Frostline": .6, "Coolara": .4}, "1 Ton Inverter Split AC", 32),
    ("AC", "AC_15T", 10, 33000, 55000, {"Frostline": .6, "Coolara": .4}, "1.5 Ton Inverter Split AC", 38),
    ("AC", "AC_2T", 6, 45000, 75000, {"Frostline": .6, "Coolara": .4}, "2 Ton Inverter Split AC", 45),
    ("REF", "REF_SD", 8, 15000, 25000, {"Frostline": .5, "Voltra": .5}, "Single Door Refrigerator", 40),
    ("REF", "REF_DD", 10, 25000, 60000, {"Frostline": .55, "Voltra": .45}, "Double Door Refrigerator", 60),
    ("REF", "REF_SBS", 6, 70000, 120000, {"Frostline": .6, "Voltra": .4}, "Side-by-Side Refrigerator", 100),
    ("WM", "WM_SEMI", 6, 14000, 20000, {"Voltra": .6, "Frostline": .4}, "Semi-Automatic Washing Machine", 28),
    ("WM", "WM_TL", 7, 20000, 35000, {"Voltra": .55, "Frostline": .45}, "Top Load Washing Machine", 35),
    ("WM", "WM_FL", 7, 30000, 60000, {"Voltra": .55, "Frostline": .45}, "Front Load Washing Machine", 65),
    ("KIT", "KIT_MW", 8, 6000, 20000, {"Voltra": .6, "Prometheus Essentials": .4}, "Microwave Oven", 14),
    ("KIT", "KIT_MIX", 8, 2000, 8000, {"Voltra": .5, "Prometheus Essentials": .5}, "Mixer Grinder", 5),
    ("KIT", "KIT_AF", 6, 5000, 15000, {"Voltra": .5, "Prometheus Essentials": .5}, "Air Fryer", 5),
    ("KIT", "KIT_CHM", 6, 12000, 45000, {"Voltra": 1.0}, "Kitchen Chimney", 18),
    ("AUD", "AUD_EARBUDS", 10, 1000, 25000, {"Zenwave": .6, "Aurex": .4}, "True Wireless Earbuds", 0.2),
    ("AUD", "AUD_HP", 8, 1500, 35000, {"Zenwave": .65, "Aurex": .35}, "Wireless Headphones", 0.5),
    ("AUD", "AUD_SPK", 8, 1500, 30000, {"Zenwave": .6, "Aurex": .4}, "Bluetooth Speaker", 1.5),
    ("AUD", "AUD_SB", 6, 8000, 40000, {"Aurex": .6, "Zenwave": .4}, "Soundbar", 6),
    ("WEA", "WEA_WATCH", 12, 2000, 45000, {"Orbix": .65, "Zenwave": .35}, "Smartwatch", 0.3),
    ("WEA", "WEA_BAND", 8, 2000, 8000, {"Orbix": .6, "Zenwave": .4}, "Fitness Band", 0.2),
    ("GAM", "GAM_CON", 3, 30000, 60000, {"Hexa": 1.0}, "Gaming Console", 5),
    ("GAM", "GAM_CTRL", 3, 3000, 7000, {"Hexa": 1.0}, "Wireless Controller", 0.4),
    ("GAM", "GAM_CAM", 6, 8000, 60000, {"Pixelon": 1.0}, "Camera", 1.0),
    ("ACC", "ACC_CASE", 4, 300, 1500, {"Prometheus Essentials": .7, "Zenwave": .3}, "Phone Case", 0.1),
    ("ACC", "ACC_CHG", 4, 800, 3000, {"Prometheus Essentials": .7, "Zenwave": .3}, "Fast Charger", 0.2),
    ("ACC", "ACC_CBL", 3, 300, 1200, {"Prometheus Essentials": 1.0}, "Charging Cable", 0.1),
    ("ACC", "ACC_BAG", 3, 1200, 4000, {"Prometheus Essentials": 1.0}, "Laptop Backpack", 0.9),
    ("ACC", "ACC_MSE", 3, 500, 2500, {"Prometheus Essentials": .7, "Zenwave": .3}, "Wireless Mouse", 0.15),
    ("ACC", "ACC_MNT", 3, 1000, 4000, {"Prometheus Essentials": 1.0}, "TV Wall Mount", 2.5),
    ("ACC", "ACC_NET", 4, 1500, 6000, {"Prometheus Essentials": .6, "Zenwave": .4}, "Wi-Fi Router", 0.6),
]

# named story SKUs: sku_id -> overrides (placed into their subcategory's grid)
NAMED = {
    "TV-AUR-50U5": dict(subcategory="TV_50", brand="Aurex", name='Aurex 50" U5 4K Smart TV', launch_price=38990,
                        launch_date=date(2025, 2, 10), eol_date=None),
    "TV-AUR-55U7": dict(subcategory="TV_55", brand="Aurex", name='Aurex 55" U7 4K Smart TV', launch_price=52990,
                        launch_date=date(2025, 3, 15), eol_date=None),
    "TV-AUR-55Q8": dict(subcategory="TV_55", brand="Aurex", name='Aurex 55" Q8 QLED 4K TV', launch_price=69990,
                        launch_date=date(2025, 5, 20), eol_date=None),
    "LAP-KAI-14A25": dict(subcategory="LAP_14", brand="Kairo", name='Kairo Air 14" (2025)', launch_price=58990,
                          launch_date=date(2025, 6, 10), eol_date=date(2026, 8, 1)),
    "LAP-KAI-14A26": dict(subcategory="LAP_14", brand="Kairo", name='Kairo Air 14" (2026)', launch_price=62990,
                          launch_date=date(2026, 8, 5), eol_date=None),
    "ACC-PRE-BAG15": dict(subcategory="ACC_BAG", brand="Prometheus Essentials", name='Prometheus Essentials 15" Laptop Backpack',
                          launch_price=1799, launch_date=date(2023, 6, 1), eol_date=None),
    "ACC-PRE-MSE01": dict(subcategory="ACC_MSE", brand="Prometheus Essentials", name="Prometheus Essentials Silent Wireless Mouse",
                          launch_price=899, launch_date=date(2023, 6, 1), eol_date=None),
    "ACC-PRE-WMT55": dict(subcategory="ACC_MNT", brand="Prometheus Essentials", name='Prometheus Essentials Tilt Wall Mount 43-65"',
                          launch_price=1999, launch_date=date(2023, 6, 1), eol_date=None),
    "AUD-AUR-SB5": dict(subcategory="AUD_SB", brand="Aurex", name="Aurex SB5 3.1 Soundbar", launch_price=14990,
                        launch_date=date(2024, 11, 1), eol_date=None),
}

SERVICES = [
    # sku_id, name, price, margin, applies_to
    ("SRV-INS-TV", "TV installation", 799, 0.70, "TV"),
    ("SRV-WMT-TV", "TV wall-mount fitting", 1299, 0.72, "TV"),
    ("SRV-INS-AC", "AC installation", 1499, 0.62, "AC"),
    ("SRV-INS-WM", "Washing machine installation", 599, 0.70, "WM"),
    ("SRV-DEM-REF", "Refrigerator delivery & demo", 499, 0.65, "REF"),
    ("SRV-SET-LAP", "Laptop setup & data migration", 999, 0.80, "LAP"),
    ("SRV-SET-PHN", "Phone setup & data transfer", 499, 0.80, "PHN"),
    ("SRV-PP-1Y-S", "ProtectPlus 1-year (devices < Rs 30k)", 1499, 0.75, "ALL"),
    ("SRV-PP-1Y-L", "ProtectPlus 1-year (devices Rs 30k+)", 4999, 0.72, "ALL"),
    ("SRV-PP-2Y-S", "ProtectPlus 2-year (devices < Rs 30k)", 2499, 0.74, "ALL"),
    ("SRV-PP-2Y-L", "ProtectPlus 2-year (devices Rs 30k+)", 8999, 0.70, "ALL"),
    ("SRV-PP-2Y-XL", "ProtectPlus 2-year Premium (devices Rs 1L+)", 11999, 0.68, "ALL"),
]
INSTALL_SERVICE = {"TV": "SRV-INS-TV", "AC": "SRV-INS-AC", "WM": "SRV-INS-WM", "REF": "SRV-DEM-REF"}

SERIES = {
    "TV": ["M", "N", "S", "V", "X"],
    "PHN": ["N", "Z", "A"], "LAP": ["Air", "Book", "Pro", "Blade", "Flex"],
}


def _round_price(p: float) -> int:
    if p < 1000:
        return int(round(p / 10) * 10 - 1)
    if p < 10000:
        return int(round(p / 100) * 100 - 1)
    return int(round(p / 1000) * 1000 - 10)


def _months_between(a: date, b: date) -> float:
    return (b - a).days / 30.44


def build_catalog(rng: np.random.Generator):
    rows = []
    used_ids: set[str] = set()
    for cat, sub, n, lo, hi, brands, label, wt in SUBCATS:
        (mlo, mhi), life, erosion, cycle, install = CAT_SPEC[cat]
        named_here = [(k, v) for k, v in NAMED.items() if v["subcategory"] == sub]
        # spread launches so ~70% of a subcategory is sellable at any time
        span_start = HISTORY_START - timedelta(days=int(life * 30.44 * 0.75))
        span_end = date(2026, 8, 31)
        span_days = (span_end - span_start).days
        bnames, bw = list(brands.keys()), np.array(list(brands.values()))
        for k in range(n):
            launch = span_start + timedelta(days=int((k + rng.uniform(0.05, 0.95)) * span_days / n))
            price = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            brand = bnames[int(rng.choice(len(bnames), p=bw / bw.sum()))]
            spec = dict(subcategory=sub, brand=brand, launch_price=_round_price(price), launch_date=launch,
                        eol_date=launch + timedelta(days=int(life * 30.44 * rng.uniform(0.85, 1.2))))
            sku_id = None
            if k < len(named_here):
                sku_id, ov = named_here[k]
                spec.update(ov)
            b3 = BRAND_CODES[spec["brand"]]
            if sku_id is None:
                code = _model_code(cat, sub, spec["launch_price"], k, rng)
                sku_id = f"{cat}-{b3}-{code}"
                while sku_id in used_ids:
                    sku_id = sku_id + "X"
                spec["name"] = _model_name(cat, sub, spec["brand"], code, label)
            used_ids.add(sku_id)
            eol = spec["eol_date"]
            if eol is not None and eol > date(2027, 3, 31):
                eol = None
            margin = rng.uniform(mlo, mhi)
            rows.append(dict(
                sku_id=sku_id, name=spec["name"], brand=spec["brand"], brand_code=b3, category=cat,
                category_name=CATEGORY_NAMES[cat], subcategory=sub, launch_price=int(spec["launch_price"]),
                launch_date=spec["launch_date"], eol_date=eol, margin_pct=round(float(margin), 4),
                replacement_cycle_months=cycle, requires_install=bool(install), is_service=False,
                pack_weight_kg=round(float(wt * rng.uniform(0.85, 1.15)), 2),
                erosion_per_month=erosion,
            ))
    df = pd.DataFrame(rows)

    # tiers: category-level price terciles on launch price
    df["tier"] = ""
    for cat, g in df.groupby("category"):
        q1, q2 = np.quantile(g["launch_price"], [1 / 3, 2 / 3])
        df.loc[g.index, "tier"] = np.where(g["launch_price"] <= q1, "entry", np.where(g["launch_price"] <= q2, "mid", "premium"))
    # substitute groups: brand x adjacent-size band for TVs, brand x subcategory elsewhere
    tv_band = {"TV_32": "32_43", "TV_43": "32_43", "TV_50": "50_55", "TV_55": "50_55", "TV_65": "65_75", "TV_75": "65_75"}
    df["substitute_group"] = [
        f"TV_{b}_{tv_band[s]}" if c == "TV" else f"{s}_{b}" if c in ("PHN", "LAP", "TAB", "AC", "REF", "WM") else s
        for c, s, b in zip(df["category"], df["subcategory"], df["brand_code"])]
    df["is_imported"] = df["tier"].eq("premium") & df["category"].isin(["TV", "PHN", "LAP", "TAB", "WEA", "GAM", "AUD"])
    df["case_pack"] = np.where(df["category"].eq("ACC"), 5, 1)
    df["warranty_months"] = df["category"].map({"TV": 12, "PHN": 12, "LAP": 12, "TAB": 12, "AC": 60, "REF": 120, "WM": 24,
                                                "KIT": 24, "AUD": 12, "WEA": 12, "GAM": 12, "ACC": 6})
    df["mrp"] = [(_round_price(p * rng.uniform(1.08, 1.25))) for p in df["launch_price"]]
    df["install_service_sku"] = df["category"].map(INSTALL_SERVICE)

    # services
    srows = []
    for sid, name, price, margin, applies in SERVICES:
        srows.append(dict(sku_id=sid, name=name, brand="Prometheus Services", brand_code="PRS", category="SRV",
                          category_name="Services", subcategory="SRV_" + sid.split("-")[1], launch_price=price,
                          launch_date=date(2020, 1, 1), eol_date=None, margin_pct=margin, replacement_cycle_months=0,
                          requires_install=False, is_service=True, pack_weight_kg=0.0, erosion_per_month=0.0,
                          tier="service", substitute_group="SRV_" + sid.split("-")[1], is_imported=False, case_pack=1,
                          warranty_months=0, mrp=price, install_service_sku=None))
    df = pd.concat([df, pd.DataFrame(srows)], ignore_index=True)
    df = df.sort_values(["is_service", "category", "subcategory", "launch_date", "sku_id"]).reset_index(drop=True)

    # current (DEMO_TODAY) prices after erosion
    ref_day = DEMO_TODAY
    cur = []
    for r in df.itertuples():
        ref = min(ref_day, r.eol_date) if r.eol_date is not None else ref_day
        m = max(0.0, _months_between(r.launch_date, ref))
        cur.append(_round_price(r.launch_price * max(0.72, 1 - r.erosion_per_month * m)) if not r.is_service else r.launch_price)
    df["list_price"] = cur
    df["unit_cost"] = (df["list_price"] * (1 - df["margin_pct"])).round(2)
    df["gross_margin_pct"] = df["margin_pct"]
    df["price_band"] = pd.cut(df["list_price"], [0, 2000, 10000, 25000, 50000, 100000, 10 ** 7],
                              labels=["<2k", "2k-10k", "10k-25k", "25k-50k", "50k-1L", "1L+"]).astype(str)

    def lifecycle(r):
        if r.is_service:
            return "current"
        if r.launch_date > DEMO_TODAY:
            return "upcoming"
        if r.eol_date is not None and r.eol_date <= DEMO_TODAY:
            return "end_of_life"
        if (DEMO_TODAY - r.launch_date).days <= 90:
            return "new"
        return "current"
    df["lifecycle"] = [lifecycle(r) for r in df.itertuples()]
    df["complements"] = _complements(df)
    return df


def _model_code(cat, sub, price, k, rng):
    if cat == "TV":
        size = sub.split("_")[1]
        return f"{size}{SERIES['TV'][int(rng.integers(0, len(SERIES['TV'])))]}{int(rng.integers(2, 9)) * 10}"
    if cat == "PHN":
        tier = {"PHN_BUDGET": "E", "PHN_MID": "M", "PHN_PREMIUM": "P", "PHN_FLAGSHIP": "U"}[sub]
        return f"{tier}{int(rng.integers(10, 99))}"
    if cat == "LAP":
        return f"{sub.split('_')[1][:2]}{int(rng.integers(100, 999))}"
    return f"{sub.split('_')[1][:3]}{int(rng.integers(10, 999))}"


def _model_name(cat, sub, brand, code, label):
    if cat == "TV":
        size = sub.split("_")[1]
        return f'{brand} {size}" {code[len(size):]} {label.split(" ", 1)[1]}'
    if cat == "PHN":
        return f"{brand} {code} 5G"
    return f"{brand} {code} {label}"


def _complements(df: pd.DataFrame) -> list[str]:
    by_sub = {s: g["sku_id"].tolist() for s, g in df.groupby("subcategory")}
    out = []
    for r in df.itertuples():
        comp: list[str] = []
        pp = ("SRV-PP-2Y-XL" if r.list_price >= 100000 else "SRV-PP-1Y-L" if r.list_price >= 30000 else "SRV-PP-1Y-S")
        if r.category == "TV":
            sb = [s for s in by_sub["AUD_SB"] if s.startswith("AUD-" + r.brand_code)] or by_sub["AUD_SB"]
            comp = ["SRV-INS-TV", "SRV-WMT-TV", "ACC-PRE-WMT55", sb[0], pp]
        elif r.category == "LAP":
            comp = ["ACC-PRE-BAG15", "ACC-PRE-MSE01", by_sub["ACC_BAG"][0], pp, "SRV-SET-LAP"]
        elif r.category == "PHN":
            comp = [by_sub["ACC_CASE"][0], by_sub["ACC_CHG"][0], by_sub["AUD_EARBUDS"][0], "SRV-SET-PHN", pp]
        elif r.category == "TAB":
            comp = [by_sub["ACC_CASE"][1], by_sub["ACC_CHG"][0], pp]
        elif r.category == "AC":
            comp = ["SRV-INS-AC", pp]
        elif r.category == "WM":
            comp = ["SRV-INS-WM", pp]
        elif r.category == "REF":
            comp = ["SRV-DEM-REF", pp]
        elif r.sku_id.startswith("GAM") and r.subcategory == "GAM_CON":
            comp = by_sub["GAM_CTRL"][:2] + [pp]
        comp = list(dict.fromkeys(c for c in comp if c != r.sku_id))
        out.append(json.dumps(comp))
    return out


def build_relationships(products: pd.DataFrame) -> pd.DataFrame:
    rows = []
    phys = products[~products["is_service"]]
    for r in products.itertuples():
        for i, c in enumerate(json.loads(r.complements)):
            rows.append(dict(sku_id=r.sku_id, related_sku_id=c, relation="complement",
                             strength=round(1.0 - 0.15 * i, 2), source="catalog_rule"))
    for g, grp in phys.groupby("substitute_group"):
        ids, prices = grp["sku_id"].tolist(), grp["list_price"].to_numpy(float)
        for a in range(len(ids)):
            for b in range(len(ids)):
                if a != b:
                    sim = float(np.exp(-abs(np.log(prices[a] / prices[b])) / 0.35))
                    rows.append(dict(sku_id=ids[a], related_sku_id=ids[b], relation="substitute",
                                     strength=round(sim, 3), source="substitute_group"))
    # successor: next launched model of the same brand in the same subcategory
    for (sub, br), grp in phys.groupby(["subcategory", "brand"]):
        grp = grp.sort_values("launch_date")
        ids = grp["sku_id"].tolist()
        for a, b in zip(ids[:-1], ids[1:]):
            rows.append(dict(sku_id=a, related_sku_id=b, relation="successor", strength=1.0, source="model_generation"))
    if not any(r["sku_id"] == "LAP-KAI-14A25" and r["related_sku_id"] == "LAP-KAI-14A26" for r in rows):
        rows.append(dict(sku_id="LAP-KAI-14A25", related_sku_id="LAP-KAI-14A26", relation="successor", strength=1.0,
                         source="model_generation"))
    return pd.DataFrame(rows)
