"""Global configuration for the Prometheus digital-twin generator."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = REPO_DIR / "data"
RAW_SEARCH_ROOTS = [DATA_DIR / "raw", DATA_DIR / "online_retail_ii", DATA_DIR / "instacart", DATA_DIR / "olist"]
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_STATS_PATH = PROCESSED_DIR / "reference_stats.json"
SYNTH_DIR = DATA_DIR / "synthetic"
TRUTH_DIR = DATA_DIR / "_truth"
EVENTS_CSV = Path(__file__).resolve().parent / "events.csv"

# ---------------------------------------------------------------- clock
SEED = int(os.environ.get("SEED", "42"))
HISTORY_START = date(2024, 10, 1)
HISTORY_END = date(2026, 9, 30)          # inclusive; DEMO_TODAY = 2026-10-01
DEMO_TODAY = date(2026, 10, 1)
WARMUP_DAYS = 90                          # simulated but not written (initialises stock, recency)
FORWARD_DAYS = 60                         # forward installation bookings after DEMO_TODAY

# ---------------------------------------------------------------- scale targets (PLAN §6)
N_CUSTOMERS = 25_000
TARGETS = {
    "customers": 25_000, "stores": 36, "products": 332, "orders": 190_000, "order_lines": 280_000,
    "web_daily": 1_200_000, "campaigns_hist": 140, "exposures": 420_000,
    "inventory_weekly": 300_000, "inventory_snapshot": 36 * 332,
}
TOLERANCE = 0.20

CATEGORIES = ["TV", "PHN", "LAP", "TAB", "AC", "REF", "WM", "KIT", "AUD", "WEA", "GAM", "ACC"]
CAT_INDEX = {c: i for i, c in enumerate(CATEGORIES)}
