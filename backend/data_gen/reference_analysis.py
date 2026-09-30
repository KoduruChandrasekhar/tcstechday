"""Reference-data analysis.

Inspects the three downloaded reference datasets (Online Retail II, Instacart,
Olist) and extracts *aggregate* behavioural statistics that are used to
calibrate the Prometheus digital twin. No reference rows are ever copied into
the synthetic world; only summary statistics flow into ``reference_stats.json``.

Run:  python -m data_gen.reference_analysis        (from ./backend)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from .config import PROCESSED_DIR, RAW_SEARCH_ROOTS, REFERENCE_STATS_PATH


# ----------------------------------------------------------------------------
# locate files (the folders are named "archive (1)" etc., so search by filename)
# ----------------------------------------------------------------------------
def _find(name: str) -> Path | None:
    for root in RAW_SEARCH_ROOTS:
        if not root.exists():
            continue
        hits = sorted(root.rglob(name))
        if hits:
            return hits[0]
    return None


def _q(s: pd.Series | np.ndarray, qs=(0.1, 0.25, 0.5, 0.75, 0.9, 0.99)) -> dict:
    arr = np.asarray(s, dtype=float)
    arr = arr[~np.isnan(arr)]
    return {f"p{int(q * 100)}": round(float(np.quantile(arr, q)), 4) for q in qs}


def _profile(counts: pd.Series) -> list[float]:
    v = counts.sort_index().astype(float).values
    return [round(float(x), 4) for x in v / v.mean()]


def _schema(df: pd.DataFrame | pl.DataFrame) -> dict:
    if isinstance(df, pl.DataFrame):
        return {c: str(t) for c, t in zip(df.columns, df.dtypes)}
    return {c: str(t) for c, t in df.dtypes.items()}


def _gamma_k(x: np.ndarray) -> float:
    """Method-of-moments Gamma shape."""
    m, v = float(np.mean(x)), float(np.var(x))
    return round(m * m / v, 3) if v > 0 else float("nan")


# ----------------------------------------------------------------------------
# Online Retail II  (UK gift-ware retailer, invoices 2009-2011)
# ----------------------------------------------------------------------------
def analyse_online_retail() -> dict:
    path = _find("online_retail_II.xlsx")
    if path is None:
        return {"available": False}
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    frames = []
    for sheet in wb.sheet_names:
        rows = wb.get_sheet_by_name(sheet).to_python()
        frames.append(pd.DataFrame(rows[1:], columns=rows[0]))
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    df["Invoice"] = df["Invoice"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Customer ID"] = pd.to_numeric(df["Customer ID"].astype(str).str.strip(), errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    n_raw = len(df)
    dup = int(df.duplicated().sum())

    cancel = df["Invoice"].str.startswith("C")
    sales = df[~cancel & (df["Quantity"] > 0) & (df["Price"] > 0)].copy()
    sales["value"] = sales["Quantity"] * sales["Price"]

    inv = sales.groupby("Invoice").agg(
        cust=("Customer ID", "first"), ts=("InvoiceDate", "first"),
        lines=("StockCode", "size"), value=("value", "sum"), country=("Country", "first"))
    guest_invoice_share = float(inv["cust"].isna().mean())

    known = inv.dropna(subset=["cust"])
    per_cust = known.groupby("cust").agg(n=("ts", "size"), first=("ts", "min"), last=("ts", "max"))
    span_days = (known["ts"].max() - known["ts"].min()).days
    annual_rate = per_cust["n"] / (span_days / 365.0)
    # inter-purchase gaps
    ks = known.sort_values(["cust", "ts"])
    gaps = ks.groupby("cust")["ts"].diff().dt.days.dropna()
    gaps = gaps[gaps > 0]

    # product popularity concentration
    prod_rev = sales.groupby("StockCode")["value"].sum().sort_values(ascending=False)
    top20 = float(prod_rev.head(max(1, int(len(prod_rev) * 0.2))).sum() / prod_rev.sum())
    ranks = np.arange(1, len(prod_rev) + 1)
    sl = np.polyfit(np.log(ranks[:500]), np.log(prod_rev.values[:500]), 1)[0]

    month = inv.groupby(inv["ts"].dt.month).size()
    dow = inv.groupby(inv["ts"].dt.dayofweek).size().reindex(range(7), fill_value=0)
    hour = inv.groupby(inv["ts"].dt.hour).size()

    # cancellations relative to sales (value)
    canc_val = float((df.loc[cancel, "Quantity"].abs() * df.loc[cancel, "Price"]).sum())
    sale_val = float(sales["value"].sum())

    return {
        "available": True,
        "file": str(path.name),
        "sheets": wb.sheet_names,
        "rows": n_raw,
        "duplicate_rows": dup,
        "columns": _schema(df[["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]]),
        "date_range": [str(df["InvoiceDate"].min().date()), str(df["InvoiceDate"].max().date())],
        "n_invoices": int(inv.shape[0]),
        "n_customers": int(per_cust.shape[0]),
        "n_products": int(sales["StockCode"].nunique()),
        "n_countries": int(sales["Country"].nunique()),
        "home_country_invoice_share": round(float((inv["country"] == "United Kingdom").mean()), 4),
        "guest_invoice_share": round(guest_invoice_share, 4),
        "cancel_line_share": round(float(cancel.mean()), 4),
        "cancel_value_ratio": round(canc_val / sale_val, 4),
        "repeat_customer_share": round(float((per_cust["n"] >= 2).mean()), 4),
        "invoices_per_customer": _q(per_cust["n"]),
        "annual_invoice_rate": _q(annual_rate),
        "annual_invoice_rate_gamma_k": _gamma_k(annual_rate.values),
        "inter_purchase_gap_days": _q(gaps),
        "lines_per_invoice": _q(inv["lines"]),
        "quantity_per_line": _q(sales["Quantity"]),
        "unit_price": _q(sales["Price"]),
        "log_price_sigma": round(float(np.log(sales["Price"]).std()), 4),
        "invoice_value": _q(inv["value"]),
        "top20pct_sku_revenue_share": round(top20, 4),
        "sku_rank_revenue_slope_top500": round(float(sl), 4),
        "month_profile": _profile(month),
        "dow_profile_mon_to_sun": _profile(dow),
        "hour_profile": {int(h): round(float(v), 4) for h, v in (hour / hour.mean()).items()},
    }


# ----------------------------------------------------------------------------
# Instacart  (online grocery baskets, 3.4M orders)
# ----------------------------------------------------------------------------
def analyse_instacart() -> dict:
    p_orders = _find("orders.csv")
    # olist also has an orders file with a different name; make sure it is instacart's
    p_prior = _find("order_products__prior.csv")
    p_train = _find("order_products__train.csv")
    p_prod = _find("products.csv")
    p_dept = _find("departments.csv")
    p_aisle = _find("aisles.csv")
    if p_orders is None or p_prior is None:
        return {"available": False}

    orders = pl.read_csv(p_orders, schema_overrides={"days_since_prior_order": pl.Float64})
    prior = pl.scan_csv(p_prior)
    prod = pl.read_csv(p_prod)
    dept = pl.read_csv(p_dept)

    n_prior = prior.select(pl.len()).collect().item()
    n_train = pl.scan_csv(p_train).select(pl.len()).collect().item()

    basket = prior.group_by("order_id").agg(
        pl.len().alias("size"), pl.col("reordered").mean().alias("reorder_share")).collect()
    reorder_rate = prior.select(pl.col("reordered").mean()).collect().item()
    reorder_by_pos = (prior.with_columns(pl.col("add_to_cart_order").clip(1, 20).alias("pos"))
                      .group_by("pos").agg(pl.col("reordered").mean()).sort("pos").collect())

    per_user = orders.group_by("user_id").agg(pl.col("order_number").max().alias("n"))
    dsp = orders["days_since_prior_order"].drop_nulls().to_numpy()

    # department co-occurrence lift on a deterministic sample of orders
    sample_ids = basket.filter(pl.col("order_id") % 17 == 0).select("order_id")
    lines = (prior.join(sample_ids.lazy(), on="order_id").join(prod.lazy().select("product_id", "department_id"), on="product_id")
             .select("order_id", "department_id").unique().collect())
    n_orders_s = lines["order_id"].n_unique()
    dsupp = lines.group_by("department_id").agg(pl.len().alias("n"))
    pairs = lines.join(lines, on="order_id").filter(pl.col("department_id") < pl.col("department_id_right"))
    psupp = pairs.group_by("department_id", "department_id_right").agg(pl.len().alias("n_ab"))
    psupp = (psupp.join(dsupp.rename({"n": "n_a"}), on="department_id")
             .join(dsupp.rename({"department_id": "department_id_right", "n": "n_b"}), on="department_id_right")
             .with_columns((pl.col("n_ab") * n_orders_s / (pl.col("n_a") * pl.col("n_b"))).alias("lift"),
                           (pl.col("n_ab") / pl.col("n_a")).alias("conf_a_to_b")))
    psupp = psupp.filter(pl.col("n_ab") >= 50)
    dname = dict(zip(dept["department_id"].to_list(), dept["department"].to_list()))
    top_pairs = psupp.sort("lift", descending=True).head(8)
    top_pairs_list = [
        {"a": dname[a], "b": dname[b], "lift": round(l, 3), "confidence": round(c, 3)}
        for a, b, l, c in zip(top_pairs["department_id"], top_pairs["department_id_right"], top_pairs["lift"], top_pairs["conf_a_to_b"])]

    prod_pop = prior.group_by("product_id").agg(pl.len().alias("n")).sort("n", descending=True).collect()["n"].to_numpy()
    top1 = float(prod_pop[: max(1, len(prod_pop) // 100)].sum() / prod_pop.sum())

    dow = orders.group_by("order_dow").agg(pl.len()).sort("order_dow")["len"].to_numpy().astype(float)
    hour = orders.group_by("order_hour_of_day").agg(pl.len()).sort("order_hour_of_day")["len"].to_numpy().astype(float)

    return {
        "available": True,
        "files": {p.name: None for p in [p_orders, p_prior, p_train, p_prod, p_dept, p_aisle] if p},
        "rows": {"orders": orders.height, "order_products__prior": n_prior, "order_products__train": n_train,
                 "products": prod.height, "departments": dept.height},
        "columns": {"orders": _schema(orders), "products": _schema(prod)},
        "n_users": int(per_user.height),
        "n_orders": int(orders.height),
        "orders_per_user": _q(per_user["n"].to_numpy()),
        "days_since_prior": _q(dsp),
        "days_since_prior_capped30_share": round(float((dsp >= 30).mean()), 4),
        "basket_size": _q(basket["size"].to_numpy()),
        "basket_size_mean": round(float(basket["size"].mean()), 3),
        "reorder_rate": round(float(reorder_rate), 4),
        "reorder_rate_by_cart_position": [round(float(x), 4) for x in reorder_by_pos["reordered"].to_list()],
        "department_pair_lift": _q(psupp["lift"].to_numpy()),
        "department_pair_top": top_pairs_list,
        "top1pct_product_line_share": round(top1, 4),
        "dow_profile_0_to_6": [round(float(x), 4) for x in dow / dow.mean()],
        "hour_profile": [round(float(x), 4) for x in hour / hour.mean()],
    }


# ----------------------------------------------------------------------------
# Olist  (Brazilian marketplace, 100k orders with delivery + reviews)
# ----------------------------------------------------------------------------
ELECTRONICS_CATS = {"electronics", "computers_accessories", "telephony", "computers", "audio",
                    "consoles_games", "small_appliances", "home_appliances", "home_appliances_2",
                    "air_conditioning", "tablets_printing_image", "fixed_telephony",
                    "small_appliances_home_oven_and_coffee", "cine_photo"}


def analyse_olist() -> dict:
    p = {n: _find(n) for n in ["olist_orders_dataset.csv", "olist_customers_dataset.csv", "olist_order_items_dataset.csv",
                               "olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv",
                               "olist_products_dataset.csv", "olist_sellers_dataset.csv",
                               "product_category_name_translation.csv", "olist_geolocation_dataset.csv"]}
    if p["olist_orders_dataset.csv"] is None:
        return {"available": False}
    orders = pd.read_csv(p["olist_orders_dataset.csv"], parse_dates=[
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date"])
    cust = pd.read_csv(p["olist_customers_dataset.csv"])
    items = pd.read_csv(p["olist_order_items_dataset.csv"])
    pay = pd.read_csv(p["olist_order_payments_dataset.csv"])
    rev = pd.read_csv(p["olist_order_reviews_dataset.csv"], parse_dates=["review_creation_date"])
    prods = pd.read_csv(p["olist_products_dataset.csv"])
    sellers = pd.read_csv(p["olist_sellers_dataset.csv"])
    trans = pd.read_csv(p["product_category_name_translation.csv"], encoding="utf-8-sig")
    geo_rows = sum(1 for _ in open(p["olist_geolocation_dataset.csv"], encoding="utf-8")) - 1

    prods = prods.merge(trans, on="product_category_name", how="left")
    oc = orders.merge(cust, on="customer_id", how="left")
    per_unique = oc.groupby("customer_unique_id").size()

    items_per_order = items.groupby("order_id").size()
    it = items.merge(prods[["product_id", "product_category_name_english"]], on="product_id", how="left")
    elec = it[it["product_category_name_english"].isin(ELECTRONICS_CATS)]

    dlv = orders.dropna(subset=["order_delivered_customer_date"]).copy()
    dlv["delivery_days"] = (dlv["order_delivered_customer_date"] - dlv["order_purchase_timestamp"]).dt.total_seconds() / 86400
    dlv["late"] = dlv["order_delivered_customer_date"].dt.normalize() > dlv["order_estimated_delivery_date"]
    dlv["late_days"] = (dlv["order_delivered_customer_date"] - dlv["order_estimated_delivery_date"]).dt.days.clip(lower=0)
    dr = dlv.merge(rev[["order_id", "review_score"]], on="order_id", how="inner")
    score_by_late = dr.groupby("late")["review_score"].mean()
    dr["late_band"] = pd.cut(dr["late_days"], [-1, 0, 3, 7, 14, 1000], labels=["on_time", "1-3", "4-7", "8-14", "15+"])
    score_by_band = dr.groupby("late_band", observed=True)["review_score"].mean()

    # same-state vs cross-state delivery (distance proxy)
    ss = items.merge(sellers[["seller_id", "seller_state"]], on="seller_id").merge(
        oc[["order_id", "customer_state"]], on="order_id").drop_duplicates("order_id")
    ss = ss.merge(dlv[["order_id", "delivery_days"]], on="order_id")
    same_state = ss.groupby(ss["seller_state"] == ss["customer_state"])["delivery_days"].median()

    state_share = oc["customer_state"].value_counts(normalize=True)
    hhi = float((state_share ** 2).sum())

    p1 = pay[pay["payment_sequential"] == 1]
    ip = p1.merge(items.groupby("order_id")["price"].sum().rename("order_price"), on="order_id")
    ip["price_band"] = pd.qcut(ip["order_price"], 4, labels=["q1", "q2", "q3", "q4"])
    inst_by_band = ip.groupby("price_band", observed=True)["payment_installments"].apply(lambda s: float((s > 1).mean()))

    return {
        "available": True,
        "rows": {"orders": len(orders), "customers": len(cust), "order_items": len(items), "payments": len(pay),
                 "reviews": len(rev), "products": len(prods), "sellers": len(sellers), "geolocation": geo_rows},
        "columns": {"orders": _schema(orders), "order_items": _schema(items), "reviews": _schema(rev[["review_id", "order_id", "review_score", "review_creation_date"]])},
        "date_range": [str(orders["order_purchase_timestamp"].min().date()), str(orders["order_purchase_timestamp"].max().date())],
        "order_status_share": {k: round(float(v), 4) for k, v in orders["order_status"].value_counts(normalize=True).items()},
        "unique_customers": int(per_unique.shape[0]),
        "repeat_customer_share": round(float((per_unique >= 2).mean()), 4),
        "items_per_order": _q(items_per_order),
        "multi_item_order_share": round(float((items_per_order > 1).mean()), 4),
        "item_price": _q(items["price"]),
        "electronics_item_price": _q(elec["price"]),
        "electronics_line_share": round(float(len(elec) / len(it)), 4),
        "freight_to_price_ratio": _q(items["freight_value"] / items["price"]),
        "delivery_days": _q(dlv["delivery_days"]),
        "late_share": round(float(dlv["late"].mean()), 4),
        "delivery_days_same_state_median": round(float(same_state.get(True, np.nan)), 2),
        "delivery_days_cross_state_median": round(float(same_state.get(False, np.nan)), 2),
        "review_score_share": {int(k): round(float(v), 4) for k, v in rev["review_score"].value_counts(normalize=True).sort_index().items()},
        "review_score_mean": round(float(rev["review_score"].mean()), 3),
        "review_score_on_time": round(float(score_by_late.get(False, np.nan)), 3),
        "review_score_late": round(float(score_by_late.get(True, np.nan)), 3),
        "review_score_by_late_band": {str(k): round(float(v), 3) for k, v in score_by_band.items()},
        "review_comment_share": round(float(rev["review_comment_message"].notna().mean()), 4),
        "payment_type_share": {k: round(float(v), 4) for k, v in p1["payment_type"].value_counts(normalize=True).items()},
        "installments_gt1_share_by_price_quartile": {str(k): round(v, 4) for k, v in inst_by_band.items()},
        "customer_state_top3_share": round(float(state_share.head(3).sum()), 4),
        "customer_state_hhi": round(hhi, 4),
        "n_customer_states": int(state_share.shape[0]),
    }


# ----------------------------------------------------------------------------
# calibration: map reference statistics -> twin parameters
# ----------------------------------------------------------------------------
def derive_calibration(orii: dict, ic: dict, ol: dict) -> dict:
    cal: dict = {}
    if orii.get("available"):
        # share of orders placed without a loyalty/customer ID -> anonymous walk-in orders
        cal["guest_order_share"] = round(min(0.25, orii["guest_invoice_share"]), 4)
        cal["purchase_rate_gamma_k"] = orii["annual_invoice_rate_gamma_k"]
        cal["return_rate_scale"] = round(orii["cancel_line_share"] / 0.02, 3)
        cal["sku_popularity_zipf"] = round(-orii["sku_rank_revenue_slope_top500"], 3)
        cal["repeat_customer_share_ref"] = orii["repeat_customer_share"]
    if ic.get("available"):
        cal["online_dow_profile_sun_first"] = ic["dow_profile_0_to_6"]
        cal["online_hour_profile"] = ic["hour_profile"]
        cal["complement_lift_median"] = ic["department_pair_lift"]["p50"]
        cal["complement_lift_p90"] = ic["department_pair_lift"]["p90"]
        cal["reorder_rate_ref"] = ic["reorder_rate"]
    if ol.get("available"):
        cal["multi_item_order_share"] = ol["multi_item_order_share"]
        cal["delivery_days_median_same_region"] = ol["delivery_days_same_state_median"]
        cal["delivery_days_median_cross_region"] = ol["delivery_days_cross_state_median"]
        cal["late_share"] = ol["late_share"]
        cal["review_score_share"] = ol["review_score_share"]
        cal["review_score_on_time"] = ol["review_score_on_time"]
        cal["review_score_late"] = ol["review_score_late"]
        cal["review_score_by_late_band"] = ol["review_score_by_late_band"]
        cal["installment_share_by_price_quartile"] = ol["installments_gt1_share_by_price_quartile"]
        cal["canceled_share"] = ol["order_status_share"].get("canceled", 0.006)
        cal["geo_top3_share"] = ol["customer_state_top3_share"]
    return cal


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print("analysing Online Retail II ...", flush=True)
    orii = analyse_online_retail()
    print("analysing Instacart ...", flush=True)
    ic = analyse_instacart()
    print("analysing Olist ...", flush=True)
    ol = analyse_olist()
    out = {"online_retail_ii": orii, "instacart": ic, "olist": ol,
           "calibration": derive_calibration(orii, ic, ol)}

    def _clean(o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, dict):
            return {str(k): _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return o

    REFERENCE_STATS_PATH.write_text(json.dumps(_clean(out), indent=2), encoding="utf-8")
    print(f"wrote {REFERENCE_STATS_PATH}")


if __name__ == "__main__":
    main()
