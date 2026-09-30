"""Regions, cities, stores and regional distribution centres of Prometheus."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .config import CATEGORIES

REGIONS = [
    ("WEST", "West"), ("NORTH", "North"), ("SOUTH", "South"), ("EAST", "East"),
]

# code, name, region, lat, lng, state, market_size_index, premium_index, online_index, climate
CITIES = [
    ("MUM", "Mumbai", "WEST", 19.0760, 72.8777, "Maharashtra", 1.30, 1.30, 1.25, "coastal_humid"),
    ("PUN", "Pune", "WEST", 18.5204, 73.8567, "Maharashtra", 0.85, 1.10, 1.15, "moderate"),
    ("AMD", "Ahmedabad", "WEST", 23.0225, 72.5714, "Gujarat", 0.75, 0.95, 0.95, "hot_dry"),
    ("DEL", "Delhi NCR", "NORTH", 28.6139, 77.2090, "Delhi", 1.35, 1.20, 1.10, "continental"),
    ("JAI", "Jaipur", "NORTH", 26.9124, 75.7873, "Rajasthan", 0.55, 0.90, 0.85, "hot_dry"),
    ("LKO", "Lucknow", "NORTH", 26.8467, 80.9462, "Uttar Pradesh", 0.55, 0.85, 0.80, "continental"),
    ("CHD", "Chandigarh", "NORTH", 30.7333, 76.7794, "Chandigarh", 0.50, 1.10, 0.90, "continental"),
    ("BLR", "Bengaluru", "SOUTH", 12.9716, 77.5946, "Karnataka", 1.25, 1.20, 1.35, "mild"),
    ("HYD", "Hyderabad", "SOUTH", 17.3850, 78.4867, "Telangana", 1.05, 1.05, 1.10, "hot_dry"),
    ("CHE", "Chennai", "SOUTH", 13.0827, 80.2707, "Tamil Nadu", 0.95, 1.00, 1.00, "tropical_hot"),
    ("KOC", "Kochi", "SOUTH", 9.9312, 76.2673, "Kerala", 0.50, 1.00, 0.95, "tropical_humid"),
    ("KOL", "Kolkata", "EAST", 22.5726, 88.3639, "West Bengal", 0.95, 0.90, 0.85, "coastal_humid"),
]
CITY_CODES = [c[0] for c in CITIES]
CITY_INDEX = {c: i for i, c in enumerate(CITY_CODES)}

# per-city category propensity multipliers (local demand structure; applied to customer intent)
CITY_CATEGORY_MULT = {
    "MUM": {"PHN": 1.15, "LAP": 1.10, "AUD": 1.15, "WEA": 1.20, "AC": 0.90, "KIT": 0.90, "WM": 0.95},
    "PUN": {"LAP": 1.20, "TV": 1.10, "PHN": 1.05, "TAB": 1.10},
    "AMD": {"AC": 1.20, "REF": 1.10, "KIT": 1.10, "WM": 1.10, "LAP": 0.85},
    "DEL": {"AC": 1.30, "TV": 1.05, "REF": 1.05, "PHN": 1.05},
    "JAI": {"AC": 1.20, "PHN": 0.95, "LAP": 0.85},
    "LKO": {"AC": 1.20, "REF": 1.05, "LAP": 0.80},
    "CHD": {"AC": 1.10, "TV": 1.05, "LAP": 0.95},
    "BLR": {"LAP": 1.35, "PHN": 1.15, "TAB": 1.20, "WEA": 1.30, "AUD": 1.20, "GAM": 1.30, "AC": 0.45, "TV": 0.95},
    "HYD": {"TV": 1.15, "PHN": 1.10, "LAP": 1.15},
    "CHE": {"AC": 1.70, "REF": 1.05},
    "KOC": {"REF": 1.05, "WM": 1.05, "AC": 0.80, "PHN": 1.05},
    "KOL": {"REF": 1.10, "TV": 1.05, "AC": 0.95, "LAP": 0.90, "KIT": 0.95},
}

# store_id, name, format, size_sqft
STORES = [
    ("MUM-01", "Prometheus Lower Parel", "Flagship"), ("MUM-02", "Prometheus Andheri West", "Standard"),
    ("MUM-03", "Prometheus Powai", "Standard"), ("MUM-04", "Prometheus Thane West", "Express"),
    ("PUN-01", "Prometheus Baner", "Standard"), ("PUN-02", "Prometheus Viman Nagar", "Standard"),
    ("PUN-03", "Prometheus Kothrud", "Express"),
    ("AMD-01", "Prometheus SG Highway", "Standard"), ("AMD-02", "Prometheus Navrangpura", "Express"),
    ("DEL-01", "Prometheus Connaught Place", "Flagship"), ("DEL-02", "Prometheus Saket", "Standard"),
    ("DEL-03", "Prometheus Gurugram Cyber City", "Standard"), ("DEL-04", "Prometheus Noida Sector 18", "Express"),
    ("JAI-01", "Prometheus Malviya Nagar", "Standard"), ("JAI-02", "Prometheus Vaishali Nagar", "Express"),
    ("LKO-01", "Prometheus Gomti Nagar", "Standard"), ("LKO-02", "Prometheus Hazratganj", "Express"),
    ("CHD-01", "Prometheus Sector 17", "Standard"), ("CHD-02", "Prometheus Sector 35", "Express"),
    ("BLR-01", "Prometheus Indiranagar", "Flagship"), ("BLR-02", "Prometheus Whitefield", "Standard"),
    ("BLR-03", "Prometheus Koramangala", "Standard"), ("BLR-04", "Prometheus Jayanagar", "Express"),
    ("HYD-01", "Prometheus Banjara Hills", "Flagship"), ("HYD-02", "Prometheus Gachibowli", "Standard"),
    ("HYD-03", "Prometheus Kukatpally", "Standard"),
    ("CHE-01", "Prometheus T. Nagar", "Flagship"), ("CHE-02", "Prometheus Velachery", "Standard"),
    ("CHE-03", "Prometheus Anna Nagar", "Express"),
    ("KOC-01", "Prometheus Edappally", "Standard"), ("KOC-02", "Prometheus Kakkanad", "Express"),
    ("KOL-01", "Prometheus Park Street", "Flagship"), ("KOL-02", "Prometheus Salt Lake", "Standard"),
    ("KOL-03", "Prometheus Gariahat", "Express"),
    # PLAN §6.1 per-city counts sum to 34; two extra metro Express stores bring the network to 36
    ("MUM-05", "Prometheus Borivali West", "Express"), ("DEL-05", "Prometheus Dwarka", "Express"),
]

FORMAT_SPEC = {
    #            sqft range      install demo  sfs_cap  attractiveness  staff
    "Flagship": ((18000, 26000), 28, 24, 60, 1.60, 42),
    "Standard": ((8000, 14000), 16, 12, 30, 1.00, 22),
    "Express": ((2500, 4500), 8, 0, 12, 0.55, 9),
}

WAREHOUSES = [
    ("DC-WEST", "Prometheus DC Bhiwandi", "WEST", 19.2813, 73.0483, 180000),
    ("DC-NORTH", "Prometheus DC Manesar", "NORTH", 28.3515, 76.9428, 200000),
    ("DC-SOUTH", "Prometheus DC Hoskote", "SOUTH", 13.0707, 77.7982, 190000),
    ("DC-EAST", "Prometheus DC Dankuni", "EAST", 22.6800, 88.2900, 90000),
]


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_geography(rng: np.random.Generator):
    regions = pd.DataFrame(REGIONS, columns=["region", "region_name"])
    cities = pd.DataFrame(CITIES, columns=["city_code", "city", "region", "lat", "lng", "state",
                                           "market_size_index", "premium_index", "online_index", "climate"])
    cities["category_mult_json"] = [json.dumps({c: CITY_CATEGORY_MULT[cc].get(c, 1.0) for c in CATEGORIES}) for cc in cities["city_code"]]
    regions["n_cities"] = regions["region"].map(cities.groupby("region").size())

    city_lookup = cities.set_index("city_code")
    rows = []
    for sid, name, fmt in STORES:
        cc = sid[:3]
        c = city_lookup.loc[cc]
        (lo, hi), inst, demo, sfs, attr, staff = FORMAT_SPEC[fmt]
        lat = c["lat"] + rng.uniform(-0.08, 0.08)
        lng = c["lng"] + rng.uniform(-0.08, 0.08)
        size = int(round(rng.uniform(lo, hi) / 100) * 100)
        opened = pd.Timestamp("2012-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 11)))
        local = {cat: round(float(np.exp(rng.normal(0, 0.15))), 3) for cat in CATEGORIES}
        rows.append(dict(
            store_id=sid, store_name=name, city=c["city"], city_code=cc, region=c["region"],
            lat=round(lat, 5), lng=round(lng, 5), format=fmt, size_sqft=size,
            install_slots_per_day=inst, demo_zone=bool(demo > 0), demo_slots_per_day=demo,
            ship_from_store=bool(fmt != "Express" or rng.random() < 0.3), sfs_orders_per_day=sfs,
            staff_count=int(staff + rng.integers(-3, 4)), opened_on=opened.date(),
            attractiveness=round(attr * float(np.exp(rng.normal(0, 0.1))), 3),
            local_mult_json=json.dumps(local),
        ))
    stores = pd.DataFrame(rows)
    stores.loc[~stores["ship_from_store"], "sfs_orders_per_day"] = 0
    stores = stores.sort_values("store_id").reset_index(drop=True)

    wh = pd.DataFrame(WAREHOUSES, columns=["warehouse_id", "warehouse_name", "region", "lat", "lng", "capacity_units"])
    region_dc = dict(zip(wh["region"], wh["warehouse_id"]))
    stores["warehouse_id"] = stores["region"].map(region_dc)
    stores["dc_distance_km"] = [round(haversine_km(r.lat, r.lng, *wh.set_index("warehouse_id").loc[r.warehouse_id, ["lat", "lng"]]), 1)
                                for r in stores.itertuples()]
    wh["n_stores_served"] = wh["warehouse_id"].map(stores.groupby("warehouse_id").size()).fillna(0).astype(int)
    cities["n_stores"] = cities["city_code"].map(stores.groupby("city_code").size()).astype(int)
    return regions, cities, stores, wh


def store_distance_matrix(stores: pd.DataFrame) -> np.ndarray:
    n = len(stores)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            d[i, j] = haversine_km(stores.lat[i], stores.lng[i], stores.lat[j], stores.lng[j])
    return d
