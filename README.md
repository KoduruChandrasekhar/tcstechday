# Prometheus PromoForge: AI promotion & inventory alignment planner

Problem Statement 3 (Retail / E-commerce). Decision support that recommends personalized, stock-safe, profitable promotions and explains each one.

## Run

```bash
cd backend
python -m data_gen.generate --seed 42 --customers 8000   # only if data/synthetic is empty
cd ..
python -m uvicorn app.main:app --app-dir backend --port 8765
```

Open http://localhost:8765

### Next.js frontend (recommended for demos)

With the backend running on port 8765, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The Next.js app proxies every `/api/*` call to the backend (set `API_URL` to point elsewhere).
The original single-file UI is still served at http://localhost:8765.

## What's inside

| Page | What it shows |
|---|---|
| Mission Control | Ranked recommendations by objective (profit, growth, clear stock, retain) and planning window, verdict mix, block reasons, profit by category, opportunity feed |
| Promotion Forge | Editable promo sentence with live re-simulation: verdict, readiness breakdown, drivers, risks, "what would change this", stock burn-down with inbound POs, discount frontier, 52-week demand and search signal, profit waterfall, campaign twins |
| Mismatch Map | Demand vs stock cover by city, with animated stock-transfer arcs |
| Audience Studio | Consent-filtered segments, persuadable share, fatigue, affinity, and a T-learner uplift model card with holdout validation |
| Guardrail Court | Blocked promotions, the evidence against each, and what would make it admissible |
| Approval Board | Three-lens sign-off (Marketing, Merchandising, Store Ops) on one shared readiness score, then Time Warp to simulate the outcome and learn |
| Campaign Memory | 134 past campaigns, predicted vs actual ROI calibration |

## Engine (backend/app/engine.py)

Built from `data/synthetic/*.parquet` (never `data/_truth`):
- **Uplift**: a T-learner (two logistic regressions) on 175K treated/holdout campaign exposures. It targets persuadables only, which cuts discount leakage.
- **Demand**: 90-day city × SKU sales × festival multipliers (events × regional intensity) × search intent.
- **Stock**: current inventory projected to the window start, plus inbound POs that arrive during the window. Stock-out probability comes from a normal approximation.
- **Economics**: incremental GP plus basket attach margin, minus leakage, channel costs and stock-out cost. Readiness = 0.30 profit + 0.25 stock + 0.20 uplift + 0.15 ops capacity + 0.10 fatigue.
- **Guardrails**: margin floor, stock-out probability, k-anonymity, install capacity, leakage, fatigue. Verdicts are GO / CONDITIONAL GO / HOLD / BLOCK.

The 8,000-customer twin is treated as a 1:50 sample of the customer base. Quantities are scaled uniformly, so verdicts don't change.
