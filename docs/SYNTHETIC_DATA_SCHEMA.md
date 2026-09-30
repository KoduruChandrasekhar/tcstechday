# Synthetic data schema (`data/synthetic/*.parquet`)
Regenerate: `cd backend && python -m data_gen.generate --seed 42`; validate: `python -m data_gen.validate`.

| Table | Grain / key | Notes |
|---|---|---|
| regions, cities, stores, warehouses, store_capacity | region / city_code / store_id / warehouse_id | 4 regions, 12 cities, 36 stores (Flagship/Standard/Express), 4 DCs |
| products | sku_id | 320 physical + 12 service SKUs, fictional brands, tier, mrp/list/cost, lifecycle, substitute_group, complements, rating (from reviews) |
| product_relationships | sku_id, related_sku_id, relation | complement / substitute / successor |
| customers | customer_id | anonymous; city, home store, loyalty tier, consent/WhatsApp/email/app/DND, unsubscribed_on, age band, income proxy |
| customer_behavior_summary | customer_id | observed roll-up as of 2026-10-01 |
| orders / order_lines | order_id / (order_id, line_no) | channel store/web/app, campaign_id, discounts, promo_source, bundle_id, payment, delivery, status |
| returns, reviews | return_id / review_id | driven by lateness, quality, install waits |
| web_daily | customer, date, category, subcategory | views, searches, compares, wishlist, atc, remove_from_cart, promo_views, checkout_starts, purchases |
| city_search_index | city, category(+ALL), date | 100 = 2-year mean |
| regional_demand | city, category, week | units, revenue, GP, avg discount, web, OOS |
| events | event_id | festivals/seasons/sales with category uplift + regional intensity (source: backend/data_gen/events.csv) |
| markdown_calendar | week, scope | open markdowns, deals of the week, clearance |
| campaigns_hist, exposures, campaign_outcomes | campaign / (campaign, customer) / (campaign, group, date) | 140 campaigns, 10% holdout, T/C conversions 7d/30d, repeat_180d (NULL when not yet observable) |
| inventory_snapshot, inventory_weekly, inbound_po, stock_transfers, install_bookings | store x sku / week / po / day | FIFO aging, (s,S) replenishment, open POs, forward install bookings |

Hidden truth (`data/_truth`, tests only): customers_truth, product_truth, elasticity_truth, demand_truth, uplift_truth, cannibalisation_truth, festival_truth, lost_demand_events, lifecycle_events, attach_truth, attach_city_multipliers, story_truth, campaign_design_truth, simulation_params.
