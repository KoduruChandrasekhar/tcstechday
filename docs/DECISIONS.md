# Decisions (data phase)
- Outputs go to `data/synthetic` and `data/_truth` (user instruction) instead of `backend/data`.
- Reference data lives in `data/raw/...`; analysis locates files by name.
- PLAN §6.1 per-city store counts sum to 34; added MUM-05 and DEL-05 (Express) to reach 36.
- Purchase rate Gamma(k=2, theta=3.9) instead of theta=1.1: with churn Beta(1.5,20) theta=1.1 yields ~75k orders vs the 190k target.
- Cameras sit in GAM ("Gaming & imaging"); monitors/printers omitted to respect PLAN's 12 categories and price bands.
- Web data is `web_daily` (customer-day-category aggregates, PLAN §6.6), not raw event rows.
- converted_7d/30d and repeat_180d are NULL when the window extends past 2026-09-30.
- UI is ordered as a 7-step story (spot → stock → audience → forge → guardrails → approve → learn) with a presenter mode; chart insight sentences are served by the API (`insights` fields).
