# Reference data usage
Only aggregate statistics are used (`backend/data_gen/reference_analysis.py` -> `data/processed/reference_stats.json`). No reference rows enter the twin.

| Dataset | Inspected | Used for |
|---|---|---|
| Online Retail II (1.07M lines, 40k invoices, 5.9k customers, 2009-11) | invoices, guests, repeat, gaps, prices, SKU concentration, cancellations | guest-order share (7.8%), SKU popularity Zipf slope (0.63), return-rate scale (cancel share 1.8%) |
| Instacart (3.4M orders, 32M lines) | basket size, reorder rate, dow/hour, department co-occurrence lift | online day-of-week and hour profiles; complement-lift sanity range |
| Olist (99k orders, reviews, payments, geo) | items/order, delivery days, late share, review score vs lateness, instalments by price | late-delivery share, review score by lateness band, EMI share by price quartile, multi-item share, cancellation share, same- vs cross-region delivery ratio |

Not available in any reference set (generated from PLAN §6): Indian geography, electronics catalogue, festivals, inventory, campaigns with holdouts, uplift types, installation capacity.
