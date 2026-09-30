# PROMETHEUS PromoForge — Complete End-to-End Build Plan

> **AI-Driven Personalized Promotion & Inventory Alignment Planner**
> Retail / E-commerce · Problem Statement 3
> Company: **Prometheus** — a fictional omnichannel consumer-electronics retailer (Croma-style archetype: stores + website + app, India-wide)
> Product name: **PromoForge** — *"Forge promotions that are personalized, stock-safe and profitable."*

---

## 0. HOW TO USE THIS DOCUMENT WITH CLAUDE CODE

This file is the single source of truth. Put it in the repo root as `PLAN.md` and give Claude Code the kickoff prompt below. Build **phase by phase** (Section 17). Do not ask it to build everything in one prompt.

### 0.1 Kickoff prompt (paste into Claude Code)

```
Read PLAN.md fully. It is the spec for the whole product.
We are building it phase by phase exactly as described in Section 17.
Start with Phase 0 and Phase 1 only. Follow the repo structure (Section 5),
tech stack (Section 4) and data spec (Section 6) exactly.
After each phase: run the acceptance checks listed for that phase, fix failures,
then stop and summarise what was built and what the checks showed.
Never hard-code recommendation outputs; they must emerge from the engine.
Never read files under data/_truth/ from engine code (only tests may).
```

### 0.2 Per-phase prompt template

```
Continue with Phase <N> from PLAN.md (Section 17). Re-read the sections it references.
Meet every acceptance criterion. Run the checks. Stop and report.
```

### 0.3 Golden rules for Claude Code (also copy into CLAUDE.md)

1. The spec wins. If something is ambiguous, pick the simplest option consistent with the spec and write the decision in `docs/DECISIONS.md`.
2. All money is INR, formatted Indian style (₹4,52,300 · ₹12.4 L · ₹3.2 Cr).
3. All customer data is synthetic and anonymised. No names, phones or emails of customers anywhere.
4. Every number shown in the UI must come from the API. No mock numbers in frontend components after Phase 6.
5. Every chart must have a one-line **insight** sentence (served by the API) above or below it.
6. Every recommendation must have: verdict, readiness score, drivers, risks, reason codes, and a "what would change this" answer.
7. Respect `prefers-reduced-motion`. Motion is subtle and purposeful (Section 15).
8. Deterministic: `SEED=42` produces identical data, models and recommendations.

---

## 1. REVIEW OF THE ORIGINAL SOLUTION DOC & WHAT THIS PLAN CHANGES

### 1.1 Verdict
The original solution is **conceptually strong (8/10)**. It maps every clause of the problem statement to a feature, and it is framed as a *decision engine*, not a *recommender*. That is the right way to frame it.

### 1.2 Gaps this plan fixes

| # | Gap in original doc | Fix in this plan |
|---|---|---|
| 1 | 14 innovation features, no priority → risk of a shallow demo | P0/P1/P2 priorities + phased build (Section 17) |
| 2 | No formulas or thresholds → an implementer will invent them | Exact scoring math, guardrails, readiness weights (Section 8) |
| 3 | The problem says marketing, merchandising and store ops **lack a shared view of campaign readiness**; the doc gives only one generic approval board | **Three-Lens Sign-off**: same campaign, three role lenses, three seals, and one shared readiness score (Sections 10, 13.9) |
| 4 | "Operationally feasible" is treated as stock only | Adds **store operational capacity** (installation/demo slots per day, ship-from-store load) as a hard constraint |
| 5 | Mentions Croma/Reliance/Bajaj by name | Everything is branded **Prometheus**, with fictional product brands |
| 6 | No architecture, schema, API or UI spec | Full spec (Sections 4–16) |
| 7 | No proof that the AI works | Backtests, a Qini curve for uplift, forecast WAPE, and a calibration panel (predicted vs actual) |
| 8 | "Closed-loop learning" needs campaigns to run, which a demo can't wait for | **Time Warp**: simulate the campaign's run against the hidden ground-truth simulator, then learn from the result |
| 9 | Privacy/consent only listed as a "future extension" | Consent flags, DND, k-anonymity (min segment size 50) are in the MVP |

### 1.3 Signature USPs (what judges should remember)

1. **Promo Sentence Builder**: every campaign is one editable sentence — *"Offer **10% + free installation** to **Festive Upgraders (4,812)** on **Aurex 55″ 4K TVs** in **Hyderabad (3 stores)** from **1–8 Nov** via **WhatsApp + App**, capped at **240 units**."* Click any word to change it, and the impact recalculates live.
2. **Guardrail Court**: the AI also *rejects* promotions, with evidence ("exhibits") and "what would make it admissible".
3. **Three-Lens Sign-off**: Marketing, Merchandising and Store Ops each see the same campaign through their own lens and stamp a seal. Readiness is shared, not siloed.
4. **Stock Burn-down**: shows exactly which day each store runs out under the proposed promotion, with inbound replenishment and installation capacity.
5. **Discount Leakage & Uplift Quadrant**: shows how much money is going to customers who would have bought anyway ("Sure Things"), and redirects it.
6. **Mismatch Map**: an India map where demand heat meets stock cover, with animated **stock-transfer arcs** between stores.
7. **Time Warp + Campaign Memory**: fast-forward a campaign, compare predicted vs actual, and watch the engine recalibrate.
8. **Campaign Genome**: every campaign gets a visual fingerprint glyph, and the engine shows its three nearest "twin" past campaigns and what happened to them.
9. **Ask Prometheus (⌘K)**: *"profitable laptop campaigns in Hyderabad with low stock risk"* → parsed filters + ranked answers.

### 1.4 One-line pitch
> **PromoForge is Prometheus' promotion control room. It turns customer intent, store stock, local demand, festivals and margin rules into explainable, stock-safe, retention-aware campaigns. Three teams sign off on one shared readiness score, and every outcome makes the next plan smarter.**

---

## 2. PRODUCT OVERVIEW

### 2.1 What the system does (end-to-end journey)

```
[1 Set context]  window · region · category · objective (Profit-first / Growth / Clear stock / Retain / Festival max)
      ↓
[2 Sense]        demand + web intent + events + stock + aging + fatigue + campaign memory
      ↓
[3 Detect]       Opportunity Feed (surges, excess stock, cross-sell gaps, at-risk customers, festival windows)
      ↓
[4 Generate]     candidate promotions = (audience × products × locations × offer × window × channel)
      ↓
[5 Evaluate]     simulate each: incremental units, revenue, GP, leakage, cannibalisation, stock-out probability,
                 capacity load, retention lift, fatigue → readiness score + verdict
      ↓
[6 Guardrails]   GO / CONDITIONAL GO / HOLD / BLOCK (blocked → Guardrail Court)
      ↓
[7 Explore]      Forge workspace · Scenario Lab · Discount Frontier · Counterfactuals · Twins
      ↓
[8 Sign-off]     Marketing seal · Merchandising seal · Store Ops seal → Approved → Scheduled → Live
      ↓
[9 Learn]        Time Warp / actual outcome → predicted vs actual → calibration → Campaign Memory
```

### 2.2 Personas (demo users, no real auth; switch via role switcher)

| User | Role | Cares about | Default landing |
|---|---|---|---|
| **Ananya Rao** | Marketing Manager | audience, channel, response, fatigue, budget | Mission Control |
| **Rohan Mehta** | Merchandising / Category Manager | margin, sell-through, aging stock, cannibalisation | Promotion Forge |
| **Farhan Sheikh** | Store Operations Lead (South & West) | store stock, installation slots, staff load, transfers | Store Readiness |
| **Meera Iyer** | Head of Promotions (Admin / approver of overrides) | portfolio ROI, risk, guardrails | Mission Control |

Role affects: default page, which lens is shown first, which seal they can stamp, and permission to override a BLOCK (Admin only).

### 2.3 Scope priorities

- **P0 (must demo)**: synthetic data, models, engine, Mission Control, Promotion Forge (with Sentence Builder, burn-down, waterfall, explain, counterfactual), Mismatch Map, Guardrail Court, Approval Board with Three-Lens Sign-off.
- **P1 (strongly wanted)**: Scenario Lab + Discount Frontier, Audience Studio (uplift quadrant, lifecycle Sankey, fatigue), Festival Pulse, Campaign Memory + Time Warp, Store Readiness, ⌘K palette (non-LLM parsing), Live Pulse SSE.
- **P2 (polish)**: LLM narratives + NL ask, Opportunity Radar sweep, Settings (guardrails live-edit), Data Studio, Guided Demo Tour, campaign brief PDF export, drag-to-reschedule on timeline.

---

## 3. DEMO "NOW" AND CALENDAR

- The demo clock is frozen at **`DEMO_TODAY=2026-10-01`** (env var; used everywhere instead of the system date).
- Data history: **2024-10-01 → 2026-09-30** (24 months, covers Diwali 2024 and Diwali 2025).
- The planning horizon is **Oct 2026 – Jan 2027**, so the headline story is **Navratri → Dussehra → Dhanteras → Diwali 2026**.

`backend/data_gen/events.csv` (seeded; editable; dates approximate and must be verified against a panchang before a real pitch):

| event_id | name | start | end | peak | scope | notes |
|---|---|---|---|---|---|---|
| EV-DIW-24 | Diwali 2024 | 2024-10-25 | 2024-11-03 | 2024-10-31 | national | history |
| EV-DIW-25 | Diwali 2025 | 2025-10-13 | 2025-10-23 | 2025-10-20 | national | history |
| EV-NAV-26 | Navratri 2026 | 2026-10-12 | 2026-10-21 | 2026-10-21 | national (strong West) | |
| EV-DUR-26 | Durga Puja 2026 | 2026-10-16 | 2026-10-21 | 2026-10-19 | **Kolkata ×2.2**, East ×1.5 | regional variation story |
| EV-DUS-26 | Dussehra 2026 | 2026-10-21 | 2026-10-21 | 2026-10-21 | national | |
| EV-DHN-26 | Dhanteras 2026 | 2026-11-04 | 2026-11-06 | 2026-11-06 | national (appliances, TVs ×) | |
| EV-DIW-26 | Diwali 2026 | 2026-10-30 | 2026-11-11 | 2026-11-08 | national | headline |
| EV-MEGA-26 | Prometheus Mega Fest | 2026-10-30 | 2026-11-09 | – | retailer sale window | |
| EV-XMAS-26 | Christmas & New Year | 2026-12-20 | 2027-01-01 | – | national (Kochi, Goa ×) | |
| EV-SNK-27 | Sankranti / Pongal | 2027-01-13 | 2027-01-16 | – | South ×1.4 | |
| EV-RDS-27 | Republic Day Sale | 2027-01-22 | 2027-01-26 | – | retailer sale | |
| + history equivalents for 2024/2025 of every event, plus Independence Day sale (Aug), Back-to-College (Jun 15–Jul 31), Summer AC season (Apr–Jun, North ×2.5), Onam (Kochi, late Aug), payday effect (1st–5th of month ×1.12) |

Each event has `category_uplift` JSON (e.g. `{"TV":1.9,"REF":1.6,"WM":1.5,"PHN":1.4,"LAP":1.3,"ACC":1.3,"AC":0.8}`), a `pre_window_days` (demand starts rising N days before), a `post_dip` (demand dip after), and `regional_intensity` by city.

---

## 4. TECH STACK

### 4.1 Backend (Python 3.11)
| Concern | Choice | Why |
|---|---|---|
| API | **FastAPI** + Uvicorn, **Pydantic v2** | typed, fast, auto OpenAPI docs → TS type generation |
| Analytics store | **Parquet files + DuckDB** (in-process) | fast columnar queries over ~1M rows, zero ops |
| App state store | **SQLite** via **SQLAlchemy 2.0** (+ Alembic optional) | campaigns, sign-offs, comments, audit, settings |
| Data/ML | pandas 2, numpy, scikit-learn, **LightGBM 4** (incl. `pred_contrib` for explanations), scipy, statsmodels (elasticity) | explainable gradient boosting |
| Streaming | **sse-starlette** (Server-Sent Events) | Live Pulse feed |
| LLM (optional) | `anthropic` SDK; model from env `LLM_MODEL` (default `claude-sonnet-5-5`) | narratives + NL query parsing, **with deterministic fallback** |
| Tooling | ruff, mypy (lenient), pytest, `Makefile` | |

### 4.2 Frontend (Node 20)
| Concern | Choice |
|---|---|
| Build | **Vite 5 + React 18 + TypeScript 5** |
| Styling | **Tailwind CSS 3.4** + CSS variables for tokens; `tailwind-merge`, `clsx`, `class-variance-authority` |
| Components | **shadcn/ui** (Radix primitives), restyled to the Prometheus theme |
| Charts & map | **Apache ECharts 5** via `echarts-for-react` (geo map, lines-effect arcs, effectScatter, sankey, heatmap, custom series). One chart library only. Custom glyphs in hand-written SVG |
| Motion | **Framer Motion 11** |
| Server state | **TanStack Query 5** |
| UI/global state | **Zustand** (planning context, role, theme), synced to URL query params |
| Tables | **TanStack Table 8** |
| Routing | **React Router 6** |
| Command palette | **cmdk** |
| Forms | react-hook-form + zod |
| Toasts | sonner |
| Icons | lucide-react (+ 6 custom SVG icons: flame logo, seal, gavel, radar, genome, time-warp) |
| Dates | date-fns (+ `en-IN` locale) |
| API types | `openapi-typescript` generated from FastAPI's `/openapi.json` into `src/api/schema.d.ts` |
| Tour | custom lightweight tour component (P2) |
| Tests | Vitest + Testing Library; Playwright for 3 smoke E2E flows |

### 4.3 Dev experience
- `make setup` · `make seed` (generate data → train → precompute) · `make dev` (backend :8000, frontend :5173 with proxy `/api`) · `make test` · `make demo-reset`
- Optional `docker-compose.yml` with two services.
- `.env.example`: `SEED=42`, `DEMO_TODAY=2026-10-01`, `ANTHROPIC_API_KEY=` (optional), `LLM_MODEL=claude-sonnet-5-5`, `LLM_ENABLED=false`.

---

## 5. REPOSITORY STRUCTURE

```
prometheus-promoforge/
├─ PLAN.md                      # this file
├─ CLAUDE.md                    # golden rules (Section 0.3)
├─ Makefile
├─ docker-compose.yml
├─ .env.example
├─ docs/
│  ├─ DECISIONS.md
│  ├─ DEMO_SCRIPT.md            # Section 19
│  └─ METRICS_GLOSSARY.md       # every metric definition (also served by API for tooltips)
├─ backend/
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py                # FastAPI app, CORS, routers, startup (load artifacts, warm caches)
│  │  ├─ config.py              # settings from env
│  │  ├─ clock.py               # today() → DEMO_TODAY
│  │  ├─ db/
│  │  │  ├─ sqlite.py           # SQLAlchemy engine/session
│  │  │  ├─ models.py           # ORM: Campaign, Signoff, Comment, AuditEvent, Setting, Appeal, TimeWarpRun
│  │  │  └─ duck.py             # DuckDB connection over data/*.parquet (read-only views)
│  │  ├─ schemas/               # Pydantic request/response models (one file per domain)
│  │  ├─ routers/
│  │  │  ├─ meta.py  dashboard.py  pulse.py  opportunities.py  recommendations.py
│  │  │  ├─ simulate.py  blocked.py  map.py  stores.py  segments.py  calendar.py
│  │  │  ├─ campaigns.py  memory.py  settings.py  ask.py  data.py  admin.py
│  │  ├─ engine/
│  │  │  ├─ features.py         # feature builders (customer, sku-store, segment)
│  │  │  ├─ segmentation.py     # lifecycle, micro-segments, personas
│  │  │  ├─ forecast.py         # baseline demand model + daily disaggregation
│  │  │  ├─ elasticity.py
│  │  │  ├─ uplift.py           # T-learner response + retention models
│  │  │  ├─ affinity.py         # bundles, attach rates
│  │  │  ├─ cannibalization.py
│  │  │  ├─ fatigue.py
│  │  │  ├─ inventory.py        # projections, stock-out probability, capacity, transfers
│  │  │  ├─ opportunities.py    # detectors
│  │  │  ├─ candidates.py       # candidate generation
│  │  │  ├─ simulator.py        # evaluate(candidate) → metrics  (THE core function)
│  │  │  ├─ guardrails.py       # hard gates + reason codes
│  │  │  ├─ readiness.py
│  │  │  ├─ ranking.py          # objective presets → utility
│  │  │  ├─ explain.py          # drivers, why / why-not, templates
│  │  │  ├─ counterfactual.py
│  │  │  ├─ genome.py           # fingerprint vectors + kNN twins
│  │  │  ├─ insights.py         # one-line insight generators for every chart
│  │  │  ├─ timewarp.py         # outcome simulation vs ground-truth simulator + calibration
│  │  │  ├─ llm.py              # optional narrative + NL parse, number-safety check
│  │  │  └─ cache.py            # precomputed candidates per context key
│  │  └─ services/              # workflow state machine, audit logger, pulse event generator
│  ├─ data_gen/
│  │  ├─ generate.py            # entrypoint: python -m data_gen.generate --seed 42
│  │  ├─ catalog.py  stores.py  customers.py  calendar.py  world.py (causal simulator)
│  │  ├─ campaigns_history.py  web_events.py  inventory_sim.py  stories.py
│  │  ├─ events.csv
│  │  └─ validate.py            # sanity report: data/_report.html
│  ├─ training/
│  │  └─ train_all.py           # trains all models → artifacts/
│  ├─ artifacts/                # *.pkl, metrics.json (gitignored)
│  ├─ data/                     # *.parquet (gitignored), _truth/ (tests only)
│  └─ tests/
├─ frontend/
│  ├─ index.html
│  ├─ package.json  vite.config.ts  tailwind.config.ts  postcss.config.js
│  ├─ public/geo/india_states.geojson   # official-boundary India states map
│  └─ src/
│     ├─ main.tsx  App.tsx  routes.tsx
│     ├─ styles/ tokens.css  globals.css  echarts-theme.ts
│     ├─ api/ client.ts  schema.d.ts  hooks/*.ts        # TanStack Query hooks per domain
│     ├─ store/ context.ts  role.ts  ui.ts              # Zustand
│     ├─ lib/ format.ts (INR, lakh/crore, dates) · colors.ts · motion.ts · verdict.ts
│     ├─ components/
│     │  ├─ shell/  AppShell, SideRail, TopBar, ContextBar, RoleSwitcher, LiveTicker, NotificationsDrawer
│     │  ├─ primitives/ (shadcn restyled) Button, Card, Badge, Tabs, Tooltip, Popover, Sheet, Dialog, Slider, Select, Switch, Skeleton
│     │  ├─ data/  KpiTile, Sparkline, MetricDelta, InsightCallout, MetricTooltip, EmptyState, ErrorState
│     │  ├─ verdict/ VerdictChip, VerdictStamp, ReadinessRing, ReasonCode, GuardrailBadge
│     │  ├─ forge/ PromoSentence, TokenSlot, ImpactStrip, ConditionsList, ActionBar
│     │  ├─ charts/ BurnDownChart, MarginWaterfall, DiscountFrontier, UpliftQuadrant, MismatchMap, MismatchMatrix,
│     │  │          LifecycleSankey, FatigueStrip, FestivalTimeline, CategoryHeatRibbon, QiniCurve, PredVsActual, RadarSweep
│     │  ├─ glyphs/ GenomeGlyph, FlameLogo, SealIcon
│     │  ├─ workflow/ KanbanBoard, CampaignCard, SignoffSeals, PreflightChecklist, AuditTimeline, CommentThread, LensSwitch
│     │  └─ ask/ CommandPalette, AskAnswerPanel
│     └─ pages/
│        ├─ MissionControl.tsx  OpportunityRadar.tsx  PromotionForge.tsx  ScenarioLab.tsx
│        ├─ MismatchMapPage.tsx  StoreReadiness.tsx  AudienceStudio.tsx  FestivalPulse.tsx
│        ├─ GuardrailCourt.tsx  ApprovalBoard.tsx  CampaignMemory.tsx  Settings.tsx  DataStudio.tsx
└─ e2e/ (Playwright)
```

---

## 6. SYNTHETIC DATA — "PROMETHEUS DIGITAL TWIN"

Principle: we do not generate random rows. We build a **causal world simulator** (`data_gen/world.py`) with hidden true parameters. Data is produced by simulating customers living through 24 months. The engine only ever sees the *observed* data and must **learn** the parameters. The hidden truths are written to `data/_truth/` for tests only.

### 6.1 Geography & stores (`stores.parquet`, 36 rows)

12 cities, 4 regions:

| Region | City (stores) | City demand notes |
|---|---|---|
| West | Mumbai (4), Pune (3), Ahmedabad (2) | Mumbai: premium, high online share; **Pune: TV-constrained story** |
| North | Delhi NCR (4), Jaipur (2), Lucknow (2), Chandigarh (2) | hard summers (AC ×2.5 Apr–Jun), cold winters (AC ≈ 0.2) |
| South | Bengaluru (4), **Hyderabad (3)**, Chennai (3), Kochi (2) | Hyderabad: TV overstock story; Chennai: AC demand all year; Kochi: Onam |
| East | Kolkata (3) | Durga Puja ×2.2 |

Columns: `store_id` (e.g. `HYD-01`), `store_name` ("Prometheus Banjara Hills"), `city`, `region`, `lat`, `lng` (city centroid + jitter ≤ 0.08°), `format` (Flagship / Standard / Express), `size_sqft`, `install_slots_per_day` (Flagship 28, Standard 16, Express 8), `demo_zone` (bool), `ship_from_store` (bool), `opened_on`, `local_mult_json` (per-category demand multipliers ~ LogNormal(0, 0.15), overridden by stories).

### 6.2 Product catalog (`products.parquet`, ~320 SKUs + 12 service SKUs)

Fictional brands (never real ones): **Aurex** (TV, audio), **Nimbus** (smartphones), **Kairo** (laptops), **Voltra** (washing machines, kitchen), **Frostline** (AC, refrigerators), **Zenwave** (audio), **Orbix** (wearables), **Pixelon** (cameras), **Hexa** (gaming), **Prometheus Essentials** (private-label accessories, high margin).

| Category code | Category | SKUs | Price band (₹) | Gross margin band | Elasticity ε (hidden truth) | Needs install |
|---|---|---|---|---|---|---|
| TV | Televisions | 36 | 14,000 – 2,20,000 | 8–14% | 2.2 | yes |
| PHN | Smartphones | 48 | 8,000 – 1,50,000 | 5–9% | 1.6 | no |
| LAP | Laptops | 36 | 30,000 – 2,00,000 | 7–11% | 1.8 | no |
| TAB | Tablets | 16 | 12,000 – 90,000 | 7–10% | 1.7 | no |
| AC | Air conditioners | 24 | 28,000 – 75,000 | 12–18% | 2.4 | yes |
| REF | Refrigerators | 24 | 15,000 – 1,20,000 | 12–18% | 2.0 | no (delivery+demo) |
| WM | Washing machines | 20 | 14,000 – 60,000 | 12–18% | 2.0 | yes |
| KIT | Kitchen appliances | 28 | 2,000 – 45,000 | 18–26% | 1.5 | no |
| AUD | Audio | 32 | 1,000 – 40,000 | 20–35% | 1.4 | no |
| WEA | Wearables | 20 | 2,000 – 45,000 | 15–25% | 1.5 | no |
| GAM | Gaming | 12 | 3,000 – 60,000 | 6–12% | 1.3 | no |
| ACC | Accessories (bags, cases, cables, mounts, chargers) | 24 | 300 – 6,000 | 35–55% | 1.2 | no |
| SRV | Services: TV/AC/WM installation, **ProtectPlus** 1y/2y extended warranty, laptop setup | 12 | 499 – 12,000 | 60–80% | – | – |

Columns: `sku_id` (`TV-AUR-55U7`), `name` ("Aurex 55″ U7 4K Smart TV"), `brand`, `category`, `subcategory` (e.g. `TV_55`), `tier` (entry/mid/premium), `mrp`, `list_price`, `unit_cost`, `launch_date`, `lifecycle` (new / current / end_of_life), `replacement_cycle_months`, `requires_install`, `substitute_group` (e.g. `TV_AUR_50_55`), `complements` (list of sku_ids / service ids), `pack_weight_kg`.

### 6.3 Customers (`customers.parquet`, 25,000 rows)

Observed columns: `customer_id` (`PRM-C-004821`, hashed, no PII), `home_city`, `home_store_id`, `preferred_channel` (store/online/omni), `loyalty_tier` (Prometheus Circle: none/silver/gold/elite), `joined_on`, `marketing_consent` (bool, 88% true), `whatsapp_opt_in` (bool, 64%), `dnd` (bool, 6%), `age_band` (coarse: 18-24/25-34/35-44/45-54/55+), `income_band_proxy` (derived from basket tier; low/mid/high).

Hidden truth (only in `_truth/customers_truth.parquet`):
- `price_sensitivity` ~ Beta(2,3)
- `promo_responsiveness` ~ Beta(2,4)
- `category_affinity` ~ Dirichlet(α) over 12 categories, skewed by age band
- `base_purchase_rate` (purchases/yr) ~ Gamma(k=2, θ=1.1)
- `churn_hazard` monthly ~ Beta(1.5, 20)
- `uplift_type`: persuadable 28% / sure_thing 22% / lost_cause 45% / sleeping_dog 5%
- `fatigue_k` ~ U(0.08, 0.25) (response decay per exposure in 60 days)

### 6.4 Causal world simulator (`world.py`)

Loop day by day (730 days), vectorised across customers with numpy.

**(a) Intent** for customer i, category c, day t:
```
intent_ic(t) = affinity_ic × season_c(t) × event_mult(c, city_i, t) × replacement_due_ic(t) × (1 + 0.8·story_boost)
```
Intent produces web events with probability ∝ intent (views ~ Poisson, search, add_to_cart, wishlist). Web events **lead** purchases by 3–21 days. This lets "recent intent" genuinely predict demand, and the radar can detect surges before sales rise.

**(b) Purchase hazard**:
```
p_buy_ic(t) = sigmoid( β0 + log(intent_ic(t)) + β_rec·recency_i + payday(t) ) × active_i(t)
```
With an active promotion targeted at i (treatment) at depth d:
```
uplift_i = promo_responsiveness_i × g(d) × (1 + price_sensitivity_i) × exp(-fatigue_k_i × exposures_60d_i)
g(d) = 1 − exp(−d / 0.12)                  # diminishing returns on discount depth
persuadable → p_treat = p_buy + uplift_i · (1 − p_buy)
sure_thing  → p_treat = p_buy (already high base) + tiny
lost_cause  → p_treat ≈ p_buy + 0.1·uplift
sleeping_dog→ p_treat = p_buy − 0.5·uplift  (annoyed; also churn hazard ×1.3)
```
Non-price offers (early access, free service, bundle) have their own g(): stronger for sure_things/loyal (e.g. elite tier ×1.5) and weaker for price-sensitive customers.

**(c) SKU choice**: a multinomial logit within category over SKUs in stock at the chosen store/online: utility = tier match − price_sensitivity·log(price_after_discount) + brand affinity + promoted bonus. **This produces cannibalisation naturally**: discounting one SKU steals from its substitute group.

**(d) Channel & store**: the customer's preferred channel. Online orders are shipped from the nearest store with stock (ship-from-store). If the store is out of stock: 55% switch to a substitute, 20% go online to another store, 25% are lost (logged as `lost_demand_events`, which is *not* visible to the engine except via `oos_days`).

**(e) Basket attach**: after a TV/AC/WM purchase, add installation service (p = 0.7) and ProtectPlus (p = 0.18, ×2.2 if bundled). Laptop → bag (0.22), mouse (0.15), ProtectPlus (0.12). Phone → case/charger (0.35). Attach probabilities vary by city (this creates the "cross-sell gap" opportunity).

**(f) Inventory** (`inventory_sim.py`): store×SKU on-hand; weekly replenishment using an (s, S) policy with lead time LogNormal(mean 10 days; imported premium SKUs 21 days). Random supply delays (5% of POs +7–14 days). Aging tracked by receipt cohort (FIFO).

**(g) Lifecycle**: a customer becomes inactive via churn hazard; they can be re-activated by intent spikes or by promotions (with true uplift).

### 6.5 Historical promotions (`campaigns_hist.parquet`, ~140 campaigns; `exposures.parquet`, ~420k rows)

Generated by a "naïve past marketing team" policy (deliberately imperfect, so the engine has something to improve on): broad audiences, frequent deep discounts before festivals, some campaigns on low-stock SKUs, repeat blasts to the "deal hunter" audience.
- Every campaign has a **10% random holdout** (control group). This is essential for uplift learning.
- Campaign columns: `campaign_id` (`CMP-2025-041`), `name`, `objective`, `offer_type` (pct_off / flat_off / bundle / bundle_pct / free_service / early_access / bank_cashback / loyalty_points), `discount_pct`, `bundle_skus`, `target_rule` (JSON), `sku_scope` (JSON), `store_scope` (JSON), `channels`, `start`, `end`, `budget_inr`, `audience_size`, `holdout_pct`, `approved_by_role`, plus observed outcomes: `exposed`, `treated_conv_rate`, `control_conv_rate`, `revenue`, `gross_profit`, `discount_cost`, `oos_store_days_during`, `unsub_rate`.
- Exposure columns: `campaign_id`, `customer_id`, `group` (T/C), `channel`, `sent_at`, `opened`, `clicked`, `converted_7d`, `converted_30d`, `conv_revenue`, `repeat_180d`.

### 6.6 Other tables

| File | Rows (≈) | Columns |
|---|---|---|
| `orders.parquet` | 190k | order_id, date, customer_id, store_id, channel, campaign_id?, total, discount_total |
| `order_lines.parquet` | 280k | order_id, line_no, sku_id, qty, mrp, unit_price, discount_pct, unit_cost, bundle_id? |
| `web_daily.parquet` | ~1.2M | customer_id, date, category, views, searches, atc, wishlist (only customer-days with activity) |
| `city_search_index.parquet` | 12×13×730 | city, category, date, search_index (normalised 100 = 2-yr mean) |
| `inventory_snapshot.parquet` | 36×332 | store_id, sku_id, on_hand, reserved, safety_stock, reorder_point, avg_age_days, last_receipt |
| `inventory_weekly.parquet` | ~300k | store_id, sku_id, week, on_hand_end, sales, receipts, oos_days |
| `inbound_po.parquet` | ~2k open | po_id, store_id, sku_id, qty, eta, status |
| `install_bookings.parquet` | 36×120 days | store_id, date, booked_slots (baseline, forward 60 days) |
| `channel_costs` (config) | – | sms ₹0.15, email ₹0.05, app_push ₹0.02, whatsapp ₹0.80, in_store_pos ₹0, creative fixed ₹15,000/campaign |

### 6.7 Planted "stories" (`stories.py`) — the demo must discover these, not hard-code them

| # | Story | How it is planted | What the engine should conclude |
|---|---|---|---|
| S1 | **Diwali TV — Hyderabad vs Pune** | 55″ TV intent in Hyderabad & Pune +40% over the last 21 days (web events). HYD stores: 46–60 days cover on Aurex 55U7 / 55Q8. PUN-01/02: 7–9 days cover, next PO ETA 12 Nov (after Diwali). Mumbai MUM-03 holds excess | **GO** targeted TV + installation + ProtectPlus bundle at ~10% in Hyderabad for high-intent "Festive Upgraders". **BLOCK** broad 20% in Pune (stock-out day ≈ 4). Suggest **transfer MUM-03 → PUN-01 (~60 units)**, after which Pune becomes CONDITIONAL GO with a cap |
| S2 | **Aging laptops — Delhi NCR** | Kairo 14″ 2025 model (end_of_life), 130+ days aged, 210 units in DEL stores; 2026 model launched Aug | Clearance to price-sensitive students/young professionals in Delhi NCR + Jaipur, **bundle with bag + mouse** instead of a deep discount |
| S3 | **Deal-hunter fatigue** | Segment "Deal Seekers – Metro" got 9 promos in 60 days; response fell 6.1% → 1.8% | Flags a fatigue alert. Any new pct-off to them → **BLOCK (R-FAT-001)**; suggest pausing for 21 days or a non-price offer |
| S4 | **Elite loyalists = Sure Things** | Elite-tier phone buyers have 34% baseline conversion before launches; historical discounts showed ~0 uplift | **BLOCK** deep discount (R-LEAK-001); recommend **early access + ProtectPlus** (non-price) instead. Leakage avoided ≈ ₹38 L |
| S5 | **Cannibalisation** | Discounting Aurex 50U5 historically pulled sales from Aurex 55U7 (same substitute group) | Shows ~35% of "uplift" as *shifted*; prefers promoting the 55″ or bundle |
| S6 | **AC regional split** | Oct–Nov: north AC demand collapses, Chennai stays warm; Chennai AC stock high | Localised AC promo in Chennai only; **national AC promo = BLOCK (R-LOC-001 weak national incremental value)** |
| S7 | **Kolkata Durga Puja** | Refrigerator + TV demand ×2.2 in Kolkata 16–21 Oct; stock adequate | Region-specific GO 10–20 Oct |
| S8 | **At-risk washing-machine browsers** | 1,300 customers whose lifecycle = at_risk viewed WM pages in the last 14 days | Reactivation campaign with free installation + ₹1,500 off; retention lift shown |
| S9 | **Installation capacity crunch** | BLR-02 installation slots 92% booked for 2–8 Nov | TV/AC bundle in BLR-02 → CONDITIONAL (shift installs to BLR-01/03 or extend window) |
| S10 | **Cross-sell gap** | Laptop-bag attach rate in Hyderabad 9% vs 22% peer average | CROSS_SELL_GAP opportunity → bundle campaign |

`data_gen/validate.py` must assert that each story is visible in the observed data (e.g. Pune cover < 10 days, the HYD intent index rising) and write `data/_report.html` with charts.

---

## 7. APP DATABASE (SQLite) SCHEMA

```
campaigns(
  id TEXT PK,                       -- CMP-2026-0xx
  source TEXT,                      -- 'ai' | 'manual' | 'appeal'
  recommendation_id TEXT NULL,
  spec_json TEXT,                   -- CandidateSpec (Section 9.2)
  metrics_json TEXT,                -- last SimulationResult snapshot
  verdict TEXT, readiness INT,
  status TEXT,                      -- see state machine (Section 10)
  owner_role TEXT, created_by TEXT, created_at, updated_at,
  scheduled_start, scheduled_end,
  override_flag BOOL DEFAULT 0, override_reason TEXT NULL)

signoffs(id PK, campaign_id FK, role TEXT /*marketing|merchandising|store_ops*/,
         decision TEXT /*approved|changes_requested|rejected*/, reason TEXT, user_name, created_at)

comments(id PK, campaign_id FK, user_name, role, body, created_at, mentions_json)

audit_events(id PK, campaign_id FK NULL, actor, role, action, before_json, after_json, created_at)

appeals(id PK, blocked_candidate_id, justification, requested_by, status, decided_by, created_at)

timewarp_runs(id PK, campaign_id FK, predicted_json, actual_json, error_json, created_at)

settings(key PK, value_json, updated_by, updated_at)   -- guardrails, objective weights, channel costs

notifications(id PK, role, title, body, link, read BOOL, created_at)
```

Seed on first boot: 6 historical demo campaigns in various states (1 Live, 1 Scheduled, 2 In Review with partial seals, 1 Completed with Time Warp result, 1 Rejected) so the Approval Board is never empty.

---

## 8. AI / ANALYTICS ENGINE (backend/app/engine)

All models are trained in `training/train_all.py` (run by `make seed`). Artifacts are saved to `artifacts/` with a `metrics.json`. At startup the API loads the artifacts and precomputes a candidate cache for the default context (and lazily for others, with an LRU cache keyed by context).

### 8.1 Feature builders (`features.py`)
Customer features "as of" a date T (no leakage: only data before T):

| Family | Features |
|---|---|
| Recency | days_since_last_purchase, days_since_last_web_event, days_since_last_exposure |
| Frequency/value | orders_12m, aov_12m, spend_12m_band, categories_bought_count |
| Affinity | share_of_spend by category (12), top_category, brand_share_top, tier_preference |
| Promo sensitivity | promo_order_share, avg_discount_taken, response_rate_hist, response_by_depth_band (0–10/10–20/20+) |
| Intent (last 7/14/28 d) | views_c, searches_c, atc_c, wishlist_c for the campaign category; intent_trend = 7d/28d |
| Lifecycle | lifecycle_state (8.2), tenure_days, loyalty_tier |
| Fatigue | exposures_30d, exposures_60d, response_decay_slope |
| Location | home_city, city_demand_index_c, nearest_store_cover_c |
| Time | days_to_next_event, event_phase (pre/peak/post/none), payday_flag |
| Offer (for response model) | offer_type, depth, is_bundle, channel, duration_days |

SKU-store features: on_hand, days_of_cover, avg_age_days, inbound_before(date), oos_days_28d, local_search_index, sales lags, price, lifecycle.

### 8.2 Segmentation (`segmentation.py`)

**Lifecycle rules** (as of DEMO_TODAY; thresholds in settings):
| State | Rule |
|---|---|
| new | first purchase ≤ 60 d ago and orders = 1 |
| growing | orders ≥ 2 in 12m and spend trend ↑ |
| active | purchased within expected interval (≤ 1.5× median inter-purchase gap) |
| at_risk | 1.5×–3× the expected gap since last purchase |
| dormant | > 3× the expected gap or > 365 days |
| reactivated | purchased in the last 60 d after being dormant/at_risk |

**Micro-segments** = lifecycle × top_category_affinity × price_sensitivity_band (from promo_order_share & avg_discount_taken: low/med/high) × city. Keep micro-segments with ≥ 50 customers (k-anonymity); merge the rest into "Other".

**Personas** (named clusters used in the UI): KMeans (k=8) over standardised features, then name each cluster with deterministic rules on its centroid:
- "Festive Upgraders" (high intent pre-event, mid-premium TV/appliance)
- "Deal Seekers" (high promo_order_share, high fatigue)
- "Elite Loyalists" (elite/gold, high base rate, low sensitivity)
- "Young Techies" (phones/laptops/audio, 18–34, online)
- "Home Makers" (kitchen/WM/REF)
- "Lapsing Appliance Buyers" (at_risk + appliance affinity)
- "Students & Starters" (entry tier laptops/tabs/accessories)
- "Gadget Gifters" (wearables/audio spikes near events)

Each persona has an auto-generated `persona_card`: size, lifecycle mix, top categories, median AOV, price sensitivity, best-responding offer type (from the uplift model), preferred channel, consent coverage.

### 8.3 Baseline demand forecaster (`forecast.py`)
- Grain: **week × store × subcategory** (LightGBM, Tweedie objective). Features: lags 1/2/4/52, rolling means 4/8, week-of-year, event features (event uplift prior, phase, days_to_peak), city search index lagged 1–3 weeks, avg discount in the week, oos_days (censoring flag), store format.
- Disaggregation: subcategory → SKU by the trailing 8-week SKU share (adjusted for SKUs out of stock); week → day by the store's day-of-week profile × event-day curve.
- Uncertainty: quantile models at P10 and P90 (LightGBM `objective=quantile`). This gives the burn-down confidence band.
- Backtest: rolling origin over the last 12 weeks + Diwali 2025. Report **WAPE**, bias, and P10–P90 coverage in `metrics.json` (target WAPE < 30% at store-subcategory-week; show honestly whatever it is).

### 8.4 Price elasticity (`elasticity.py`)
Log-log regression per category on weekly store×category data:
`log(units) = α_store + γ_week + Σ event + ε_c · log(1 − avg_discount) + noise`
Output ε̂_c with 95% CI, and per price-sensitivity band multipliers. Used for **open (non-targeted) offers** and as a prior for the frontier. Test: recovered ε̂ within ±30% of truth for ≥ 9/12 categories.

### 8.5 Response & uplift models (`uplift.py`)
- **T-learner**: two LightGBM classifiers trained on `exposures` (target: `converted_30d` in campaign category): M_T on treatment rows, M_C on control rows. Features = customer features as of `sent_at` + offer features (offer_type, depth, bundle, channel).
- `uplift_i(offer) = M_T(x_i, offer) − M_C(x_i)`, clipped to [−0.3, 0.6].
- **Quadrant assignment** per customer (thresholds in settings): base = M_C, uplift = τ̂.
  - Persuadable: τ̂ ≥ 0.03
  - Sure Thing: base ≥ 0.20 and τ̂ < 0.03
  - Sleeping Dog: τ̂ ≤ −0.02
  - Lost Cause: otherwise
- **Retention model**: the same T-learner with target `repeat_180d` → Δretention per customer.
- Evaluation: **Qini curve + AUUC** on a held-out 20% of campaigns (by campaign, not by row). Store the curve points for the Data Studio and Memory pages. Also report the accuracy of recovering `uplift_type` from truth (tests only).
- Speed: at startup, precompute for each (customer, category) the vectors `p_ctrl` and `p_treat[depth ∈ {0,5,10,15,20,25,30}, offer_family ∈ {pct, bundle, service, early_access}]` for customers with consent. Store as numpy arrays → the simulator is a vectorised lookup + interpolation (< 50 ms).

### 8.6 Affinity & bundles (`affinity.py`)
- Basket + 30-day sequential co-purchase association rules (support, confidence, lift) at subcategory level.
- Attach rate per city for each (anchor → complement) pair; peer average; gap = peer − city.
- Bundle candidates = top complements by `lift × complement_margin`. Output bundle GP per anchor unit.

### 8.7 Cannibalisation (`cannibalization.py`)
For each substitute_group: regress the deviation of non-promoted SKUs' weekly sales from forecast on the promoted SKUs' discount intensity → κ_group = share of promoted incremental units that are *shifted* from substitutes (0–0.8). Default κ = 0.15 when evidence is thin (with a flag "low evidence").

### 8.8 Fatigue (`fatigue.py`)
Per segment: exposures per customer in 30/60 days, response-rate time series across its last N campaigns, decay slope (linear fit on log response). **Fatigue index** 0–100 = 50·min(1, exposures_60d / cap) + 50·clip(−slope / slope_ref, 0, 1). Status: healthy < 40, warming 40–70, fatigued > 70.

### 8.9 Inventory projection, stock-out probability & capacity (`inventory.py`)
For each store l and SKU s over the window W = [t0, t1]:
```
available_l(t) = on_hand − reserved + Σ inbound with eta ≤ t (eta shifted by +2 days safety buffer)
demand_l(t)   = baseline_l(t) + promo_incremental_l(t) (+ shifted-in demand from substitutes)
proj_l(t)     = available_l(t) − Σ_{u ≤ t} demand_l(u)
stockout_day  = first t where proj_l(t) < safety_stock_l  (None if never)
P(stockout)   = 1 − Φ( (available_l(t1) − D_l) / σ_l ),  D_l = Σ demand over W,
                σ_l = sqrt( D_l·(1 + φ) ) with φ from forecast P10–P90 spread
cover_after   = proj_l(t1) / post_window_daily_run_rate
```
**Installation capacity**:
```
install_demand_l(d) = baseline_install_bookings_l(d) + promo_units_needing_install_l(d) × attach_install
utilisation_l = max_d install_demand_l(d) / install_slots_per_day_l
```
Status: ok < 85%, tight 85–100%, over > 100%.

**Transfers** (`suggest_transfers`): for a SKU where store A has cover < 10 days in the window and store B has cover > 35 days with distance(A, B) ≤ 400 km (Haversine), propose `qty = min(excess_B above 30-day cover, need_A to reach 21-day cover)`, cost = ₹4/unit/km × pack_weight factor, lead time = 2 + km/300 days. Ranked by GP protected per ₹ of transfer cost.

### 8.10 Opportunity detectors (`opportunities.py`)
Run for the current context; each returns `Opportunity{id, type, title, subtitle, severity(1–5), size_inr, evidence[], scope{cities, stores, skus, segments}, suggested_actions[]}`.

| Type | Trigger | Size estimate |
|---|---|---|
| DEMAND_SURGE | city×category search index 7d vs 28d ≥ +25% AND forecast ↑ | extra GP from capturing 60% of surge |
| EXCESS_STOCK | days_of_cover > 60 OR avg_age > 90 days (value ≥ ₹10 L) | holding cost + markdown avoided |
| STOCK_RISK | cover < 10 days AND demand rising / event within 21 d | GP at risk from lost sales |
| CROSS_SELL_GAP | attach gap ≥ 8 pp vs peer cities | complement GP from closing half the gap |
| REACTIVATION | ≥ 300 at_risk customers with intent in category (14 d) | Δretention × 12-month GP |
| FESTIVAL_WINDOW | event within 45 d with category uplift ≥ 1.3 | incremental GP of a festival campaign |
| FATIGUE_ALERT | segment fatigue index > 70 | discount cost avoidable |
| MARGIN_LEAK | past 90 d discount spend on Sure Things ≥ ₹5 L | leakage |
| TRANSFER | a transfer suggestion with GP protected ≥ ₹3 L | GP protected |

### 8.11 Candidate generation (`candidates.py`)
For each opportunity (and for the global context), build candidates from the combination grid, pruned by the opportunity scope:
- **Audience options**: persona in scope; persona ∩ intent (high intent only); persuadables-only; lifecycle-specific (at_risk, dormant); broad (all consenting customers in the city) — the broad one is included on purpose so that the Court can reject it.
- **Product options**: SKU, substitute group, subcategory; bundle variants (anchor + top 1–2 complements).
- **Location options**: single city, cluster of cities with the same signal, national, and "cities minus constrained stores".
- **Offer options**: pct_off {5,10,15,20,25}; bundle_pct {5,10}; free_service; early_access; flat_off; bank_cashback (cost shared 50% by bank).
- **Window**: aligned to event pre-window (e.g. 1–8 Nov), or 7 days starting next Monday.
- **Channel**: by persona preference and consent (WhatsApp only if opted in; exclude DND).
- **Cap**: none, or default = 80% of the safe stock capacity.

Typically ~2,000 raw candidates for the Diwali context → evaluated (vectorised) → deduplicated by keeping the best depth per (audience, product, location, window) family → **top 30 recommendations + ~25 blocked** (worst offenders with the most instructive reasons) for the Court.

### 8.12 THE SIMULATOR — `evaluate(spec) → SimulationResult` (`simulator.py`)

Inputs: `CandidateSpec` (Section 9.2). Steps:

1. **Audience resolution**: customer set A (consent-filtered, DND/WhatsApp rules), size N, reach rate by channel (WhatsApp 0.92, push 0.55, SMS 0.85, email 0.35 opens → effective reach r).
2. **Per-customer conversions**: `conv_T = Σ_i r·p_treat_i(offer)`, `conv_C = Σ_i r·p_ctrl_i`. Apply the fatigue multiplier `exp(−k̂·exposures_60d)` to the uplift part.
3. **Incremental conversions** `ΔN = conv_T − conv_C`. **Promo units** `U = conv_T × units_per_conv` (from history for the category). **Baseline-that-would-buy-anyway** `U_base = conv_C × units_per_conv`.
4. **Cannibalisation**: `U_shift = κ × ΔN × units_per_conv`; `U_incr = ΔN × units_per_conv − U_shift`.
5. **Cap**: if the cap is set, scale U down to the cap (proportionally reduce U_incr and U_base).
6. **Allocation to stores**: by the audience's home-store/online split → per-store units → **inventory projection (8.9)** incl. non-audience baseline demand in those stores.
7. **Financials** (per SKU price p, cost c, depth d; bundle adds complement GP):
```
promo_revenue      = U · p · (1 − d) + bundle_units · p_comp · (1 − d_comp)
discount_cost      = U · p · d
leakage_cost       = U_base · p · d                    # paid to people who'd buy anyway
Δrevenue           = U_incr · p(1−d) − U_base · p · d − U_shift · (p_sub − p(1−d)) + bundle_rev_incr
ΔGP                = U_incr · (p(1−d) − c) − U_base · p·d − U_shift · margin_sub
                     + bundle_gp_incr − channel_cost − creative_cost − lost_sales_gp_from_stockout
ROI                = ΔGP / (discount_cost + channel_cost + creative_cost)
margin_pct_promo   = (promo_revenue − U·c − bundle_cost) / promo_revenue
lost_sales_gp      = expected units beyond available stock × (p − c) × 0.25 (share truly lost)
```
8. **Retention**: `Δretained = Σ_i r·Δretention_i`; `retention_value = Δretained × avg_12m_GP_per_customer(segment)`.
9. **Capacity**: installation utilisation per store.
10. **Fatigue after**: the projected fatigue index of the segment after this campaign.
11. **Evidence**: model confidence = f(training support near this spec: number of historical exposures with similar offer/category/segment), kNN twin similarity (8.16).
12. Return everything + **per-day series** for charts (burn-down per store, daily incremental units, install load).

### 8.13 Guardrails & reason codes (`guardrails.py`)
Configurable in Settings (defaults below). **Hard gates → BLOCK**; soft → warnings/conditions.

| Code | Type | Rule (default) | Human message template |
|---|---|---|---|
| R-STK-001 | hard | P(stockout) > 0.35 in any store in scope | "Projected demand exceeds safe stock at {store}; stock-out likely by {date}." |
| R-STK-002 | soft | cover_after < 7 days | "Leaves only {n} days of cover after the campaign." |
| R-MRG-001 | hard | promo margin % < category floor (TV 3%, PHN 2%, LAP 3%, AC 6%, REF/WM 6%, others 10%) | "Margin falls to {x}% — below the {floor}% floor for {category}." |
| R-MRG-002 | hard | depth > category max discount (TV 20, PHN 12, LAP 18, AC 25, ACC 40…) | "Discount exceeds the maximum allowed." |
| R-ROI-001 | hard | ΔGP < 0 | "Campaign destroys profit: ΔGP {₹}." |
| R-LEAK-001 | hard | leakage_cost / discount_cost > 0.6 | "{x}% of the discount goes to customers who would buy anyway." |
| R-FAT-001 | hard | segment fatigue index > 80 or exposures_60d > 6 | "Audience is fatigued: response fell {a}% → {b}%." |
| R-CAN-001 | soft/hard(>0.6) | κ > 0.4 | "{x}% of sales are shifted from {substitute}, not new." |
| R-LOC-001 | hard | national/broad scope where > 70% of incremental GP comes from ≤ 25% of cities | "Demand is concentrated in {cities}; national spend adds little." |
| R-CAP-001 | hard(>120%) / soft(>90%) | installation utilisation | "Installation slots at {store} {x}% booked." |
| R-BUD-001 | hard | cost > remaining budget for the objective | "Exceeds remaining budget ₹{x}." |
| R-CON-001 | hard | overlaps an approved campaign on the same audience ∩ > 40% within 7 days | "Collides with {campaign}." |
| R-PRV-001 | hard | resulting audience < 50 | "Audience too small to target safely (privacy)." |
| R-EVD-001 | soft | low evidence (support < threshold) | "Few comparable past campaigns; confidence is low." |

### 8.14 Readiness score (`readiness.py`)
7 components, each 0–1, weights sum to 100:

| Component | Weight | Mapping |
|---|---|---|
| Audience fit | 15 | share of audience that are persuadables + intent strength (scaled) |
| Demand signal | 15 | normalised search-index growth + forecast uplift + event proximity |
| Inventory safety | 20 | 1 − max P(stockout); penalised if cover_after < 14 |
| Margin safety | 15 | (margin% − floor) / (target − floor), clipped |
| Operational capacity | 10 | 1 − max(0, util − 0.7)/0.5 |
| Evidence & confidence | 15 | model support + twin similarity + forecast interval width |
| Customer health | 10 | 1 − fatigue_after/100, − sleeping-dog share |

`readiness = Σ weight × component` (integer 0–100).
**Verdict**: BLOCK if any hard gate; else GO if readiness ≥ 70 and no soft warnings of severity high; CONDITIONAL GO if 50–69 or has soft warnings (with explicit **conditions**, e.g. "Cap at 180 units", "Exclude PUN-02", "Shift installs to BLR-01"); HOLD if < 50.

### 8.15 Ranking by objective (`ranking.py`)
Normalise metrics across the candidate set (min-max). Utility = Σ w_k·metric_k × (0.5 + 0.5·readiness/100).

| Preset | ΔGP | ΔRevenue | Stock health (clearance or safety) | Retention value | Leakage (−) | Fatigue (−) |
|---|---|---|---|---|---|---|
| Profit-first (default) | .45 | .15 | .15 | .10 | .10 | .05 |
| Growth | .20 | .45 | .10 | .10 | .05 | .10 |
| Clear aging stock | .20 | .10 | .50 (clearance) | .05 | .10 | .05 |
| Retain & reactivate | .20 | .05 | .10 | .50 | .05 | .10 |
| Festival max | .30 | .35 | .15 | .05 | .10 | .05 |

Settings allow custom weights (sliders; live re-rank preview).

### 8.16 Explainability (`explain.py`, `genome.py`, `counterfactual.py`)

**Drivers**: aggregate LightGBM `pred_contrib` (SHAP-like) from the uplift model over the audience; map feature names → plain language ("Recent TV page views (last 14 d)", "Pre-Diwali window", "High stock cover in Hyderabad"). Show the top 5 positive + top 3 negative with signed bar values. Add rule-based drivers from the simulator (stock, margin, event, capacity).

**Why (narrative)**: template (always available):
> "We recommend **{offer}** for **{audience}** in **{location}** because {driver1}, {driver2} and {driver3}. We expect **{ΔN} extra buyers**, **{₹ΔGP} incremental profit** and ROI of **{roi}×**. Main risk: {top risk}. Similar past campaign **{twin}** delivered {twin outcome}."

The optional LLM rewrite (`llm.py`) receives only the JSON facts and must return prose; a **number-safety check** verifies that every number in the output exists in the input facts, otherwise it falls back to the template.

**Why not**: for blocked/held candidates, the reason codes with evidence objects (`{kind: 'burndown'|'stat'|'series'|'twin', data…}`) that the frontend renders as "exhibits".

**Counterfactuals** (`counterfactual.py`): search over single and double lever changes (depth ±5/±10; cap ∈ {50%, 70%, 90% of safe capacity}; drop the riskiest store; add a suggested transfer; narrow to persuadables; shift window ±3/±7 d; switch offer to bundle/non-price) → evaluate → return the **minimal changes that flip the verdict** (for BLOCK/HOLD → GO/COND) and the **breaking points** for GO (e.g. "BLOCK if discount ≥ 20%", "HOLD if the PO slips > 5 days"). Max 5 each, sorted by smallest change then by ΔGP.

**Campaign Genome** (`genome.py`): a 16-dim fingerprint, each dimension scaled 0–1:
`category_group, offer_type, depth, bundle, audience_intent, audience_loyalty, audience_price_sens, lifecycle_mix(at_risk+dormant share), stock_cover_band, event_phase, region_concentration, channel_mix(digital share), duration, audience_size_log, price_tier, fatigue_level`.
kNN (cosine) against the historical campaign fingerprints → 3 twins with similarity %, outcome (treated vs control conv, ΔGP, stock-outs), and one "lesson" line each.

### 8.17 Insights generator (`insights.py`)
Every chart endpoint returns `insight: {text, severity, highlight_ids[]}` computed from the data, e.g.:
- Map: "Hyderabad has 2.3× the national 55″ TV search growth and 52 days of cover — best place to push. Pune is the opposite: +38% searches, 8 days of cover."
- Uplift quadrant: "₹38.2 L (41%) of last quarter's discounts went to Sure Things."
- Frontier: "Profit peaks at 10%. Beyond 15%, each extra ₹1 of revenue costs ₹1.40 of margin."
- Fatigue: "Deal Seekers – Metro response fell 70% after 9 promos in 60 days."
- Festival: "Last Diwali, TV demand rose 11 days before the peak; this year that is 28 Oct."
Rules: ≤ 160 characters, always include a number, and name the entity.

### 8.18 Time Warp & closed-loop learning (`timewarp.py`)
- `POST /campaigns/{id}/timewarp`: runs the **ground-truth world simulator** (data_gen.world, seeded by the campaign id) over the campaign window with the campaign applied, plus a 10% holdout. Returns actuals: daily sales per store, treated vs control conversion, ΔGP, stock-outs, installs, unsubscribes.
- Compares with the prediction → error metrics; stores a `timewarp_runs` row; marks the campaign Completed → Learned.
- **Calibration**: keeps a running bias correction per (category, offer_type): `calib = median(actual_ΔN / predicted_ΔN)` over completed runs (shrunk toward 1 with n/(n+5)). Applied in the simulator as a multiplier and shown in Memory ("Engine now discounts TV bundle uplift by 8% based on 4 completed campaigns").
- This is the only place engine-side code may import from `data_gen.world` (document it in DECISIONS.md); it never reads `_truth` parameters directly.

### 8.19 LLM layer (`llm.py`, optional; `LLM_ENABLED=true` + key)
1. `narrate(facts_json)` → 3–5 sentence explanation (number-safety checked).
2. `parse_query(text)` → `{intent, filters:{categories, cities, stores, segments, objective, max_stock_risk, min_roi, window}, sort}`; validated by zod/pydantic. **Fallback parser**: keyword/regex dictionaries (city names, category synonyms like "telly/TV/television", "low stock risk" → max_stock_risk=0.15, "profitable" → objective=profit).
3. `brief(campaign)` → a campaign brief paragraph for the PDF export.
All prompts live in `engine/prompts/*.md`. Timeouts of 8 s → fallback.

---

## 9. BACKEND API

Base path `/api`. All list endpoints accept the **planning context** query params:
`window_start, window_end, region, city, category, objective, role`.
Every chart-bearing response includes `insight`. Errors: `{error: {code, message, details}}`.

### 9.1 Endpoint catalogue

| Method | Path | Purpose |
|---|---|---|
| GET | `/meta` | cities, stores, categories, personas, events, objectives, channels, reason-code catalogue, metric glossary, demo_today |
| GET | `/dashboard/summary` | KPI tiles (value, delta, sparkline, insight), readiness pipeline counts, festival countdowns, sign-off queue for role |
| GET | `/pulse/stream` | **SSE** live pulse events (see 9.4) |
| GET | `/pulse/recent?limit=30` | last events (for initial render) |
| GET | `/opportunities` | Opportunity list (8.10) |
| GET | `/opportunities/radar` | points for the radar: angle=category, radius=days_to_window, size=₹, type |
| POST | `/opportunities/{id}/forge` | generate + evaluate candidates for this opportunity → returns recommendation ids |
| GET | `/recommendations?verdict=&sort=utility&limit=` | ranked list (summary rows) |
| GET | `/recommendations/{id}` | full detail: spec, result, verdict, readiness breakdown, drivers, risks, conditions, narrative, reason codes |
| GET | `/recommendations/{id}/counterfactuals` | flips + breaking points |
| GET | `/recommendations/{id}/twins` | genome vector + 3 twins |
| GET | `/recommendations/{id}/lenses` | the same campaign summarised per role (marketing/merch/store_ops) |
| POST | `/simulate` | body CandidateSpec → SimulationResult (target p95 < 150 ms) |
| POST | `/simulate/frontier` | spec + depths[] + offer families → curve points |
| POST | `/simulate/compare` | up to 3 specs → results + per-metric winner |
| GET | `/blocked` | Guardrail Court cases (filters: reason code, category, city) + totals (risk avoided) |
| GET | `/blocked/{id}` | case file with exhibits + admissibility counterfactuals |
| POST | `/blocked/{id}/appeal` | admin override with justification → creates a campaign with override_flag |
| GET | `/map/cities?category=&window=` | per city: demand index, search growth, cover days, status, active campaigns, event intensity |
| GET | `/map/transfers?category=` | suggested transfers (from, to, sku, qty, km, cost, GP protected) |
| GET | `/map/matrix` | city × category cells: demand index, cover, mismatch score, opportunity id |
| GET | `/stores` | store readiness table |
| GET | `/stores/{id}` | store detail: cover of promoted SKUs, install utilisation calendar (next 45 d), inbound POs, campaigns touching store |
| GET | `/segments` | persona cards |
| GET | `/segments/{id}` | persona detail + members stats (no individual rows) |
| GET | `/segments/flows?days=90` | lifecycle Sankey nodes/links |
| GET | `/segments/uplift-quadrant` | per segment: base, uplift, size, discount spend 90 d |
| GET | `/segments/fatigue` | segment × week exposures + response series |
| GET | `/calendar/events` | events with category uplift + regional intensity |
| GET | `/calendar/heat` | category × week expected uplift matrix |
| GET | `/calendar/campaigns` | Gantt items (all non-rejected campaigns) |
| GET | `/calendar/collisions` | audience overlaps, stock contention, budget peaks |
| GET | `/campaigns?status=` | board items |
| POST | `/campaigns` | from recommendation id or from spec |
| GET / PATCH | `/campaigns/{id}` | detail / edit spec (re-simulates, resets seals if material change) |
| POST | `/campaigns/{id}/submit` | → in_review |
| POST | `/campaigns/{id}/signoff` | `{role, decision, reason}` |
| POST | `/campaigns/{id}/schedule` · `/launch` · `/cancel` | transitions |
| POST | `/campaigns/{id}/timewarp` | simulate outcome (8.18) |
| GET | `/campaigns/{id}/audit` · `/comments` (GET/POST) | |
| GET | `/campaigns/{id}/brief.pdf` | one-page brief (P2; WeasyPrint or client-side print CSS) |
| GET | `/memory/campaigns` | historical + completed campaigns with genome + outcome badge |
| GET | `/memory/campaigns/{id}` | predicted vs actual series, treated vs control, lessons |
| GET | `/memory/calibration` | calibration factors + error trend |
| GET / PUT | `/settings/guardrails` · `/settings/objectives` · `/settings/channels` | |
| POST | `/ask` | `{text}` → `{parsed, results[], narrative}` |
| GET | `/data/overview` | datasets (rows, ranges, synthetic flag), model cards (WAPE, AUUC, Qini points, elasticity table), privacy stats |
| POST | `/admin/reset-demo` | reset the app DB to seeded state |

### 9.2 Core types (Pydantic ⇄ generated TS)

```ts
type Verdict = 'GO' | 'CONDITIONAL' | 'HOLD' | 'BLOCK';

interface CandidateSpec {
  audience: { persona_ids?: string[]; lifecycle?: string[]; intent_min?: 'any'|'medium'|'high';
              quadrant_filter?: 'all'|'exclude_sure_things'|'persuadables_only'; cities: string[] };
  products: { sku_ids?: string[]; substitute_group?: string; subcategory?: string; category?: string };
  locations: { cities: string[]; exclude_store_ids?: string[] };
  offer: { type: 'pct_off'|'flat_off'|'bundle'|'bundle_pct'|'free_service'|'early_access'|'bank_cashback'|'loyalty_points';
           depth_pct?: number; flat_inr?: number; bundle_sku_ids?: string[]; service_sku_id?: string };
  window: { start: string; end: string };      // ISO dates
  channels: ('whatsapp'|'app_push'|'sms'|'email'|'in_store')[];
  cap_units?: number | null;
  transfers?: { from_store: string; to_store: string; sku_id: string; qty: number }[];
}

interface SimulationResult {
  audience: { size: number; reachable: number; consent_excluded: number;
              quadrant_mix: { persuadable: number; sure_thing: number; lost_cause: number; sleeping_dog: number };
              lifecycle_mix: Record<string, number> };
  impact: { incr_buyers: number; promo_units: number; incr_units: number; shifted_units: number;
            promo_revenue: number; delta_revenue: number; delta_gp: number; roi: number;
            discount_cost: number; leakage_cost: number; channel_cost: number; margin_pct: number;
            retention_uplift_customers: number; retention_value: number; bundle_attach_rate?: number;
            ci: { delta_gp_p10: number; delta_gp_p90: number } };
  inventory: { stores: StoreProjection[]; worst_stockout_prob: number; min_cover_after: number };
  capacity: { stores: { store_id: string; peak_util: number; daily: { date: string; booked: number; promo: number; slots: number }[] }[] };
  fatigue: { before: number; after: number; status: 'healthy'|'warming'|'fatigued' };
  readiness: { score: number; components: { key: string; label: string; weight: number; value: number; note: string }[] };
  verdict: Verdict;
  gates: ReasonHit[];        // hard
  warnings: ReasonHit[];     // soft
  conditions: string[];      // for CONDITIONAL
  daily: { date: string; incr_units: number; baseline_units: number }[];
  waterfall: { label: string; value: number; kind: 'start'|'plus'|'minus'|'total' }[];
  evidence: { support_n: number; confidence: 'low'|'medium'|'high'; calibration_factor: number };
}

interface StoreProjection {
  store_id: string; store_name: string; city: string; available_now: number; safety_stock: number;
  series: { date: string; p50: number; p10: number; p90: number; inbound?: number }[];
  stockout_date: string | null; stockout_prob: number; cover_after_days: number;
}

interface ReasonHit { code: string; severity: 'hard'|'soft'; message: string; evidence: Exhibit[] }
type Exhibit = { kind: 'stat'; label: string; value: string }
             | { kind: 'burndown'; store_id: string }
             | { kind: 'series'; label: string; points: [string, number][] }
             | { kind: 'twin'; campaign_id: string; outcome: string };

interface Recommendation {
  id: string; title: string; sentence: SentenceToken[];   // for the Promo Sentence
  spec: CandidateSpec; result: SimulationResult; utility: number; rank: number;
  opportunity_id?: string; drivers: Driver[]; risks: Risk[]; narrative: string; tags: string[];
}
interface SentenceToken { kind: 'text'|'slot'; text: string; slot?: 'offer'|'audience'|'products'|'locations'|'window'|'channels'|'cap' }
interface Driver { label: string; value: number; direction: 'up'|'down'; source: 'model'|'rule' }
```

### 9.3 Performance targets
- Startup (warm caches) < 25 s; `/recommendations` < 300 ms (cached); `/simulate` p95 < 150 ms; `/simulate/frontier` < 600 ms; `/recommendations/{id}/counterfactuals` < 1.5 s.

### 9.4 Live Pulse (SSE)
A background task emits one event every 6–12 s (random, seeded) derived from real data plus small noise, so the dashboard feels alive:
`{id, ts, type: 'search_spike'|'stock_alert'|'po_update'|'campaign_milestone'|'signoff'|'fatigue'|'competitor_price'?, title, detail, city?, store_id?, severity, link}`.
Examples: "🔥 Search spike · 55″ TVs · Hyderabad +42% vs 4-week avg", "⚠ Stock · PUN-01 · Aurex 55U7 cover 7 days", "✔ Seal · Rohan (Merchandising) approved CMP-2026-014".
Real workflow actions (sign-offs, launches) are also pushed immediately to the stream.

---

## 10. WORKFLOW STATE MACHINE & THREE-LENS SIGN-OFF

```
 ai_proposed ──create──► draft ──submit──► in_review ──(3 seals approved)──► approved ──schedule──► scheduled ──launch──► live ──timewarp/end──► completed ──learn──► learned
                           ▲                  │  any 'changes_requested' → back to draft (seals reset)
                           │                  │  any 'rejected' → rejected
 blocked ──appeal (admin)──┘ (override_flag, needs all 3 seals + admin)
```
- **Seals**: Marketing, Merchandising, Store Ops. Each role can only stamp its own seal. A reason is required for changes_requested/rejected (min 10 chars).
- A material spec edit (depth, audience, locations, window, cap, products) after any seal → seals reset + audit event "seals reset due to change in {fields}".
- **Pre-flight checklist** (auto + manual):
  - auto ✓ Stock verified (no hard stock gates) · ✓ Margin floor · ✓ Fatigue cap · ✓ Capacity · ✓ Budget · ✓ No collisions · ✓ Privacy/consent
  - manual ☐ Creative ready (Marketing) · ☐ T&C / legal copy (Marketing) · ☐ Store staff briefed (Store Ops) · ☐ Price updated in POS (Merchandising)
  - `approved` requires all auto checks green + 3 seals; `launch` requires the manual checks.
- **Lenses** (`/recommendations/{id}/lenses`), i.e. what each role sees first:
  - **Marketing lens**: audience size & mix, channel plan & cost, expected conversions, fatigue before/after, collisions, creative checklist.
  - **Merchandising lens**: ΔGP, margin %, leakage, cannibalisation, discount frontier position, sell-through / aging cleared.
  - **Store Ops lens**: per-store units, stock-out dates, transfers needed, installation utilisation calendar, staffing note ("+2 demo staff Sat–Sun at HYD-02").
- Every action → `audit_events` + notification to the other roles + SSE pulse.

---

## 11. FRONTEND DESIGN SYSTEM — "OBSIDIAN & EMBER"

Brand idea: Prometheus brought fire to humans, so PromoForge brings *heat* (demand) under control. It should feel like a **premium control room**: dark, warm, calm, with ember accents only where attention is needed. It should **not** look like a generic admin template.

### 11.1 Colour tokens (`styles/tokens.css`)
Dark is the default. Light theme via `[data-theme="light"]`; follow system preference on first load.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#0B0A09` | `#FAF7F3` | app background |
| `--surface-1` | `#141210` | `#FFFFFF` | cards |
| `--surface-2` | `#1C1916` | `#F3EEE8` | nested panels, inputs |
| `--surface-3` | `#25211D` | `#EAE3DA` | hover, selected |
| `--border` | `#2E2924` | `#E6DFD6` | 1px borders |
| `--border-strong` | `#3D3630` | `#D4CABD` | focus/active |
| `--text` | `#F4EFE9` | `#1A1612` | primary text |
| `--text-muted` | `#A89F95` | `#6B6259` | secondary |
| `--text-faint` | `#6F675F` | `#9A9087` | captions, axes |
| `--ember` (primary) | `#FF6A2B` | `#E8551C` | CTAs, focus, brand |
| `--ember-soft` | `rgba(255,106,43,.14)` | `rgba(232,85,28,.10)` | selected backgrounds |
| `--gold` | `#FFB547` | `#C98A12` | highlights, "hot" |
| `--go` | `#2FD18B` | `#12915A` | GO |
| `--cond` | `#F5B83D` | `#B7800F` | CONDITIONAL |
| `--hold` | `#8A9BB0` | `#5E6E82` | HOLD |
| `--block` | `#FF4D5E` | `#D12C3E` | BLOCK |
| `--info` | `#4CC9F0` | `#0E8FB5` | stock-rich, info |

- **Verdicts are never colour-only**: always icon + label (GO ✓ circle-check, CONDITIONAL ◐ circle-half, HOLD ⏸ pause, BLOCK ⛔ shield-x).
- **Categorical chart palette** (8): `#FF6A2B #4CC9F0 #A78BFA #2FD18B #F5B83D #F472B6 #94A3B8 #60A5FA`.
- **Ember heat ramp** (sequential, demand): `#1C1916 → #4A2312 → #8E3614 → #D9501F → #FF8A4C → #FFC27A → #FFF1C9`.
- **Mismatch diverging** (stock-rich ↔ balanced ↔ demand-hot/short): `#4CC9F0 → #2A6F85 → #3D3630 → #B8431B → #FF6A2B`.
- Background: a very subtle radial ember glow in the top-left corner of the app (opacity .06), plus a 32px faint grid pattern only on Mission Control and the Map (opacity .035) for the "control room" feel.

### 11.2 Typography
- Headings/display & KPI numbers: **Space Grotesk** (500/600).
- UI & body: **Inter** (400/500/600), `font-feature-settings: 'cv11','ss01'`.
- Numbers in tables/tiles: `font-variant-numeric: tabular-nums`; codes/IDs: **JetBrains Mono** 12px.
- Scale: 11 (micro caps, letter-spacing .08em), 12, 13 (default table), 14 (body), 16, 20 (section titles), 24 (page titles), 32 (KPI), 44 (hero countdown).

### 11.3 Layout, spacing, shape
- 4px base grid; card padding 20; gaps 16/24; page max-width 1600, 12-column grid.
- Radius: cards 14, inputs/buttons 10, chips 999.
- Card: `surface-1`, 1px `border`, inner top highlight `inset 0 1px 0 rgba(255,255,255,.03)`; hover lifts border to `border-strong` (no big shadows). Dialogs/sheets: `0 24px 60px rgba(0,0,0,.45)`.
- Desktop-first 1440; works at 1280; ≤ 1024 the side rail collapses to icons; ≤ 768 read-only views (Mission Control, Approval Board, campaign detail with sign-off) stack in one column.

### 11.4 Number & date formatting (`lib/format.ts`)
- `inr(452300)` → `₹4,52,300`; `inrCompact(1240000)` → `₹12.4 L`; `inrCompact(32000000)` → `₹3.2 Cr` (Intl `en-IN`).
- Percentages 1 decimal; deltas with sign and arrow `▲ 12.4%`; ROI `2.8×`.
- Dates: `Thu, 5 Nov`; ranges `1–8 Nov`; relative "in 36 days"; IST always.

### 11.5 Chart theme (`styles/echarts-theme.ts`)
A registered ECharts theme per mode: transparent background, axis lines `border`, labels `text-faint` 11px Inter, split lines dashed at 0.5 opacity, tooltip = card style (surface-2, border, radius 10, 12px), animationDuration 500, easing cubicOut. Every chart component accepts `insight` and renders an `InsightCallout` (small flame icon + sentence) above the chart.

### 11.6 Logo & custom icons
- **FlameLogo**: a minimal SVG flame formed by two nested curved strokes inside a rounded hexagon, filled with an ember→gold gradient. Wordmark "PROMETHEUS" (Space Grotesk 600, letter-spacing .18em) + "PromoForge" small below it.
- Custom SVGs: Seal (circular stamp with role initial), Gavel (Court), Radar, Genome (helix-petal), TimeWarp (clock with forward arrow).

---

## 12. APP SHELL & GLOBAL ELEMENTS

```
┌──────┬──────────────────────────────────────────────────────────────────────────────────────┐
│ 🔥   │ TOP BAR: [Planning Context: 🪔 Diwali 2026 · 1 Oct–15 Nov ▾ | All India ▾ | All categories ▾ | Objective: Profit-first ▾]   │
│ rail │           [⌘K Ask Prometheus…]                         [● Live] [🔔3] [Role: Ananya · Marketing ▾] [☾]  │
│      ├──────────────────────────────────────────────────────────────────────────────────────┤
│ Home │                                                                                      │
│ Radar│                              PAGE CONTENT                                            │
│ Forge│                                                                                      │
│ Lab  │                                                                                      │
│ Map  │                                                                                      │
│Stores│                                                                                      │
│Audnce│                                                                                      │
│Fest. │                                                                                      │
│ Court│                                                                                      │
│ Board│                                                                                      │
│Memory│                                                                                      │
│ ──── │                                                                                      │
│ Data │                                                                                      │
│ ⚙    ├──────────────────────────────────────────────────────────────────────────────────────┤
│      │ LIVE TICKER: 🔥 Search spike 55″ TV Hyderabad +42% · ⚠ PUN-01 cover 7d · ✔ Rohan sealed CMP-014 · …   │
└──────┴──────────────────────────────────────────────────────────────────────────────────────┘
```
- **Side rail** (72px collapsed / 232px expanded, remembers state): icons + labels; badges (Court: blocked count, Board: "your pending seals" count). The active item has an ember left bar + ember-soft background.
- **Planning Context bar**: 4 pill selects. Changing any of them triggers refetch across pages (TanStack Query keys include the context) and is synced to URL params, so views are shareable. The window select offers presets (Navratri–Dussehra, Dhanteras–Diwali, Diwali full season, Christmas–New Year, Custom range).
- **Role switcher**: avatar + name + role; switching animates a quick crossfade, changes the default lens and seal permissions, and shows a toast "Viewing as Farhan · Store Ops".
- **Live indicator**: a green dot pulsing slowly when SSE is connected; grey + "Reconnecting…" otherwise.
- **Notifications drawer** (right Sheet): sign-off requests, collisions, SSE critical events.
- **Live Ticker** (bottom, 32px): marquee of pulse events, 45 s loop, pauses on hover; click an item → deep link. Hidden when reduced motion is on (shows a static "Latest: …" instead).
- **⌘K Command palette**: navigation ("Go to Guardrail Court"), actions ("New campaign", "Reset demo"), entities (search campaigns, stores, SKUs, personas), and **Ask** mode (any free text → `/ask`). The answer panel shows parsed filter chips (removable), the top 5 matching recommendations as mini cards, and a narrative line. Example suggestions: "Profitable laptop campaigns in Hyderabad with low stock risk", "Which stores will stock out during Diwali?", "Where is discount money leaking?".
- **Metric tooltips**: every KPI label has an ⓘ that shows the definition from `/meta.glossary` (e.g. "Incremental GP = profit that would not have happened without the campaign, after discount leakage, cannibalisation and channel costs").
- **States**: skeletons that match the final layout (shimmer 1.2 s); empty states with an illustration line icon + one action; error states with retry + error code.

---

## 13. PAGE-BY-PAGE SPECIFICATION

### 13.1 Mission Control (Home) — `/`  [P0]
Purpose: in 10 seconds, know what's hot, what's risky and what needs *my* action.

```
┌ HERO ─────────────────────────────────────────────────────────────────────────────┐
│ Good morning, Ananya.                         🪔 DHANTERAS in 36d   DIWALI in 38d   │
│ "₹2.8 Cr of incremental profit is ready to forge for Diwali. 3 stores are          │
│  heading for stock-outs." (insight)                     [ 🔥 Forge Diwali plan → ] │
└───────────────────────────────────────────────────────────────────────────────────┘
┌ KPI ─┐┌ KPI ─┐┌ KPI ─┐┌ KPI ─┐┌ KPI ─┐┌ KPI ─┐
 Opportunity   Ready (GO)   Blocked by    Stock-out     Aging stock   Leakage
 pipeline ΔGP  campaigns    guardrails    risk (store×  value         avoided
 ₹2.8 Cr ▲     12           23 · ₹1.8 Cr  SKU) 17       ₹3.4 Cr       ₹38 L
 sparkline     sparkline    risk avoided  sparkline     sparkline     sparkline
┌ OPPORTUNITY FEED (8 cols) ───────────────┐┌ READINESS PIPELINE (4 cols) ──────┐
│ [🔥 DEMAND SURGE ●●●●○] 55″ TVs · Hyderabad│ Detected 41 → Candidates 1,960 →   │
│  +42% searches, 52 d cover · ₹46 L  [Forge]│ Passed guardrails 30 → In review 4 │
│ [⚠ STOCK RISK] Pune TVs · 8 d cover …      │ → Approved 2 → Live 1  (funnel)    │
│ [📦 EXCESS] Kairo 14″ 2025 · Delhi · 132 d │├ YOUR SEALS PENDING ───────────────┤
│ [💤 REACTIVATION] 1,312 at-risk WM browsers│ CMP-2026-014 Kolkata Puja REF ⏳   │
│ … (filter chips by type; "show all")       │ CMP-2026-016 HYD TV bundle ⏳      │
└───────────────────────────────────────────┘└────────────────────────────────────┘
┌ MINI MISMATCH MAP (7 cols) ──────────────┐┌ LIVE PULSE (5 cols) ───────────────┐
│ India map, city bubbles, 2 transfer arcs │ streaming list, newest on top,      │
│ click → full map                          │ slides in, max 12, severity dot     │
└───────────────────────────────────────────┘└────────────────────────────────────┘
```
- KPI tiles count up on first load (600 ms); the delta vs last week is shown with an arrow; click → relevant page with filters.
- Opportunity cards: type icon & colour strip, severity dots, ₹ size, 1-line evidence, mini sparkline of the signal, "Forge →" (calls `/opportunities/{id}/forge` then navigates to Forge filtered by that opportunity with a "Forged 14 candidates · 6 GO · 5 blocked" toast).
- Role variants: Merchandising shows "Aging stock" and "Margin at risk" first; Store Ops shows "Stores at risk" and "Installation crunch" first.

### 13.2 Opportunity Radar — `/radar`  [P2]
A full-height **radar scope** (custom ECharts polar + custom SVG sweep):
- 12 sectors = categories (labelled on the rim), rings = urgency (inner = window starts < 7 d, outer = 45 d+), dots = opportunities (colour = type, size = ₹ size, a glow if severity ≥ 4).
- A slow sweep line (8 s per rotation); when it passes a dot, the dot brightens briefly. Pause button; static if reduced motion.
- Right panel: the selected opportunity's detail + "Forge". Filter by type (toggle legend). Insight: "Most value sits in TVs & appliances within 21–35 days (pre-Dhanteras)."

### 13.3 Promotion Forge — `/forge` and `/forge/:recId`  [P0 — the heart of the product]

```
┌ LEFT: RECOMMENDATIONS (380px) ──┐┌ RIGHT: WORKSPACE ─────────────────────────────────────────────┐
│ [All 30][GO 12][COND 9][HOLD 9] ││ ┌ PROMO SENTENCE ─────────────────────────────────────────────┐ │
│ sort: Utility ▾   search        ││ │ Offer [10% off + free installation ▾] to                     │ │
│ ┌─────────────────────────────┐ ││ │ [Festive Upgraders · high intent · 4,812 ▾] on               │ │
│ │ ✓ GO   #1        ◔ 82       │ ││ │ [Aurex 55″ 4K TVs (U7, Q8) + ProtectPlus ▾] in               │ │
│ │ HYD 55″ TV festive bundle   │ ││ │ [Hyderabad · 3 stores ▾] from [1–8 Nov ▾] via                │ │
│ │ ΔGP ₹18.6 L · ROI 3.1×      │ ││ │ [WhatsApp + App ▾], capped at [240 units ▾]                  │ │
│ └─────────────────────────────┘ ││ └──────────────────────────────────────────────────────────────┘ │
│ ┌ ◐ COND #2 … ┐                 ││ ┌ VERDICT ──────────┐ ┌ IMPACT STRIP (8 mini tiles) ───────────┐ │
│ …                               ││ │  ✓ GO   stamp      │ │ +612 buyers │ ΔRev ₹1.9 Cr │ ΔGP ₹18.6 L │ │
│                                 ││ │  Readiness ring 82 │ │ ROI 3.1× │ Leakage ₹2.1 L │ Stock-out 6%│ │
│                                 ││ │  (7 segments)      │ │ Retention +214 │ Install util 71%      │ │
│                                 ││ └────────────────────┘ └──────────────────────────────────────────┘ │
│                                 ││ TABS: Impact | Inventory | Audience | Why | Twins | What-if | Frontier │
│                                 ││ [tab content]                                                    │
│                                 ││ ─ sticky ACTION BAR: [Save draft] [Open in Scenario Lab] [Send for sign-off →] │
└─────────────────────────────────┘└──────────────────────────────────────────────────────────────────┘
```

**Promo Sentence (signature)**: rendered from `sentence` tokens. Slots are ember-underlined chips. Click → a Popover editor:
- Offer: segmented control (% off / Bundle / Free service / Early access / Cashback) + depth slider (0–30, step 5, ticks show category max) + bundle picker.
- Audience: persona multi-select, intent level, quadrant filter ("Exclude Sure Things" toggle is highlighted as a smart default), shows live size.
- Products: SKU search with thumbnails (use generic category icons), substitute-group chip.
- Locations: city checklist with per-store toggles; each store shows a cover badge (red if < 10 d).
- Window: date-range with event bands drawn under the calendar days.
- Channels: toggles with consent-reachable counts and cost per send.
- Cap: numeric + "safe capacity: 262" hint.
On change → debounce 250 ms → `POST /simulate` → the metrics that changed **flash** (green up / red down background fade 800 ms), the verdict stamp re-animates if the verdict changes, and a small "Edited · not saved" pill appears. Undo/redo (⌘Z) for sentence edits.

**Verdict panel**: a large stamp (GO/CONDITIONAL/HOLD/BLOCK) + the **Readiness Ring** (7 arc segments proportional to weights, each filled by its value; hover a segment → tooltip with its note). For CONDITIONAL: a "Conditions" list with one-click "Apply" buttons (e.g. "Cap at 180 units" → modifies the spec).

**Tabs**
1. **Impact**: Margin Waterfall (Promo revenue → − discount on would-buy-anyway (leakage) → − shifted from substitutes → + bundle/service GP → − channel & creative → − expected lost sales → **Incremental GP**). Beside it: "Incremental vs shifted vs baseline" stacked bar and a P10–P90 range bar for ΔGP ("80% likely between ₹12.1 L and ₹24.9 L").
2. **Inventory**: **Stock Burn-down** (signature, see 14.2) with a store selector (small multiples toggle), a store table (available, inbound, stock-out date, P(stock-out), cover after), the **transfer suggestion** card ("Move 60 units MUM-03 → PUN-01, ₹14,200, arrives 27 Oct — flips Pune to CONDITIONAL"). [Apply transfer] adds it to the spec. Installation utilisation mini-heat calendar per store.
3. **Audience**: the quadrant mix bar (Persuadable/Sure/Lost/Sleeping) with ₹ leakage on Sure Things; lifecycle mix; persona card; fatigue gauge before → after; channel reach funnel (audience → consented → reachable → expected responders → incremental buyers).
4. **Why**: the narrative paragraph (LLM badge "AI-written, facts-checked" or "Template"), drivers diverging bar (plain-language labels), reason codes (soft warnings), evidence chips (click → opens the related chart in a side sheet).
5. **Twins**: this campaign's **Genome Glyph** big, next to the 3 twin glyphs with similarity %, outcome badge, key metrics and a lesson line. Overlaying the glyphs on hover shows where they differ.
6. **What-if** (counterfactuals): two columns — "Would become GO if…" and "Would break if…" — as cards with a from→to change, the resulting verdict chip, ΔGP change, and [Apply].
7. **Frontier**: the **Discount Frontier** (14.5).

### 13.4 Scenario Lab — `/lab`  [P1]
- Up to 3 scenario columns A/B/C (clone from the current recommendation). Each column has compact controls: depth slider, offer type, audience breadth (All → Exclude Sure Things → Persuadables only), cities, duration, bundle toggle, cap, channels.
- Top: **Profit vs Revenue plane**: x = ΔRevenue, y = ΔGP, the frontier line of all depths for scenario A's family, scenario dots A/B/C (bubble size = stock-out prob, ring colour = verdict). Quadrant labels ("Profitable growth", "Buying revenue").
- Middle: **comparison table** — rows = metrics (buyers, ΔRev, ΔGP, ROI, leakage, stock-out prob, min cover, install util, fatigue after, readiness, verdict); the best cell per row gets a subtle gold highlight + crown icon.
- "Promote scenario B to campaign" → creates a draft.
- Insight line: "Scenario B earns 92% of A's revenue with 1.6× the profit and no stock-out risk."

### 13.5 Mismatch Map — `/map`  [P0]
```
┌ MAP (8–9 cols, full height) ─────────────────────────────┐┌ PANEL (3–4 cols) ─────────┐
│ India (official boundaries), dark basemap, states subtle  ││ Category [TVs ▾]           │
│ ● city bubbles: size = demand index, fill = mismatch      ││ Window  [Diwali ▾]         │
│   diverging colour, pulse ring on surging cities          ││ Layers: ☑ Demand ☑ Cover   │
│ ⤳ animated transfer arcs (ember dots travelling)          ││ ☑ Transfers ☐ Campaigns    │
│ ◌ event intensity halo (Kolkata during Durga Puja)        ││ ☐ Event intensity          │
│ legend: stock-rich ◀──── balanced ────▶ demand-hot/short  ││ INSIGHT callout            │
│                                                            ││ Top mismatches list (5)    │
└────────────────────────────────────────────────────────────┘└────────────────────────────┘
┌ MISMATCH MATRIX: cities (rows) × categories (cols) heatmap; cell = mismatch score, icon ⚠/📦/✓ ┐
└ click cell → Forge filtered · hover → demand idx, search growth, cover days, opportunity   ┘
```
- Click a city → right **drawer**: its stores with cover gauges per category, SKUs at risk (top 5), local events, install utilisation, active/planned campaigns, "Forge for this city".
- Transfer arcs: ECharts `lines` with `effect` (small ember symbol, period 4 s); click an arc → transfer card with [Add to campaign].
- Timeline scrubber under the map (P1): slide through weeks from now to Diwali to see projected cover change (no promo vs with approved campaigns).

### 13.6 Store Readiness — `/stores`  [P1] (Store Ops home)
- A table of 36 stores: city, format, promoted SKUs' min cover (bar), stock-out alerts count, installation utilisation peak (heat bar), inbound POs, transfers in/out, campaigns touching the store, readiness status (Ready / Watch / At risk).
- Store detail page: a **45-day installation calendar heatmap** (baseline vs promo load), a stock burn-down for its top SKUs, inbound POs timeline, staffing note generator ("Expected peak footfall Sat 7 Nov: +38% → add 2 demo staff").
- Store Ops can raise a flag "Store cannot support" on a campaign → becomes their seal's "changes requested".

### 13.7 Audience Studio — `/audience`  [P1]
- **Persona gallery**: 8 cards (name, emoji-free line icon, size, lifecycle mini-bar, top categories chips, price sensitivity meter, best offer type, preferred channel, fatigue status dot).
- **Uplift Quadrant** (signature 14.4): x = baseline purchase probability, y = uplift; bubbles = personas/micro-segments; quadrant labels; toggle "₹ view" that re-sizes bubbles by the last 90 days' discount spend → shows leakage visually. Insight: "₹38.2 L (41%) of last quarter's discount went to Sure Things."
- **Lifecycle Flow**: a Sankey of transitions over 90 days (New → Active → At-risk → Dormant → Reactivated). Click a link (e.g. Active→At-risk 1,240) → "Create reactivation audience".
- **Fatigue Strip**: rows = personas, columns = last 16 weeks, cell colour = exposures, with the response-rate line overlaid per row; a fatigued row gets a red edge + "Pause 21 d" action.
- **Retention Playbook**: table lifecycle → recommended action (editable in Settings), with the expected Δretention for each from the model.

### 13.8 Festival Pulse — `/festivals`  [P1]
- **Timeline** Oct 2026 – Jan 2027: event bands on top (colour = intensity, label, peak marker 🪔), a "Today" line, countdown chips.
- **Category Heat Ribbon**: categories × weeks, ember ramp = expected uplift learned from past years. Hover: "Last year TVs rose 11 days before peak."
- **Campaign swimlanes (Gantt)**: grouped by category; bars coloured by status; **collision markers** (⚡ icons where audiences overlap > 40%, stock contention or budget peaks); click → collision explanation with a suggested fix ("Shift CMP-017 by 4 days"). Drag to reschedule (P2) → re-simulate → verdict updates.
- "Then vs now" panel: Diwali 2025 same-phase actual vs Diwali 2026 forecast by category.
- Regional intensity mini map of the selected event (Durga Puja → Kolkata glow).

### 13.9 Guardrail Court — `/court`  [P0]
- Header stats: "23 cases · ₹1.8 Cr margin erosion prevented · 17 stock-outs avoided · ₹38 L leakage avoided" (count-up).
- Filters by charge (reason code) with counts; sort by risk avoided.
- **Case file cards** (grid, 2 columns):
```
┌ CASE #PF-0417 ─────────────────────────────── [⛔ BLOCKED stamp, rotated −8°] ┐
│ "20% off Aurex 55″ TVs to all customers in Pune, 1–8 Nov"                       │
│ CHARGES: R-STK-001 Stock-out likely · R-LEAK-001 58% leakage                    │
│ EXHIBIT A: mini burn-down (PUN-01 hits zero on 4 Nov)                            │
│ EXHIBIT B: stat "Next PO arrives 12 Nov — after Diwali"                          │
│ RISK AVOIDED: ₹6.2 L                                                             │
│ TO MAKE ADMISSIBLE: ▸ Transfer 60 units from MUM-03 + cap 90 units → CONDITIONAL │
│ [View full case] [Forge admissible version] [Appeal (Admin)]                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```
- "Forge admissible version" applies the counterfactual and opens it in the Forge.
- Appeal (Admin only): a dialog requiring a justification ≥ 30 chars → a campaign with a red "Override" ribbon; all 3 seals + admin are needed.

### 13.10 Approval Board — `/board`  [P0]
- **Kanban**: Draft · In Review · Approved · Scheduled · Live · Completed (Rejected is collapsed at the end). Column headers show counts + total ΔGP.
- **Campaign card**: verdict chip, title, sentence excerpt, ΔGP, readiness mini-ring, dates, and **3 seals** (M / Mx / O) — empty dashed circle = pending, ember filled + check = approved, amber = changes requested, red = rejected. Cards awaiting *my* seal get an ember glow border + "Your seal" tag. Filter "Only mine".
- Drag between columns only where the transition is allowed (otherwise the card snaps back with a toast explaining why).
- **Campaign drawer** (wide Sheet, 720px):
  - Header: sentence, verdict, readiness, status stepper.
  - **Lens switch** (Marketing | Merchandising | Store Ops) — defaults to my role — shows that lens's panel (Section 10).
  - **Pre-flight checklist** (auto ticks animate in sequence on open, 80 ms apart).
  - **Seal panel**: my seal button → dialog (Approve / Request changes / Reject + reason). On approve: the **seal stamp animation** (scale 1.3 → 1, rotate −8°, 280 ms, one subtle "thud" shadow). When the 3rd seal lands → confetti-free celebration: the card border glows gold for 1.5 s + toast "All teams signed off — CMP-2026-016 approved".
  - Comments thread (@mention role) and **Audit timeline** (vertical, icons per action, diff chips for spec changes).
  - Actions: Schedule, Launch, **Time Warp ⏩** (on Live), Export brief (P2).

### 13.11 Campaign Memory — `/memory`  [P1]
- Grid/table toggle of past + completed campaigns: Genome Glyph thumbnail, name, event, category, offer, outcome badge (Beat / Met / Missed forecast), ΔGP actual, treated vs control conv.
- Filters: category, event, offer type, outcome; "Find twins of…" search.
- Detail: **Predicted vs Actual** daily chart (predicted band + actual line), treated vs control bars, stock-out events marked, the lesson list ("Bundles beat % off for Elite Loyalists by 2.1× ROI").
- **Time Warp result view** (after a run): an animated reveal — days fill in left to right over ~2 s (skip-able) — then error metrics and "Engine recalibrated: TV bundle uplift × 0.92".
- **Calibration panel**: forecast error per completed campaign (bars) + trend line; "Predicted ΔGP within ±15% for 7 of 10 campaigns."
- Model evidence: **Qini curve** from the uplift model vs a random baseline.

### 13.12 Settings — `/settings`  [P2]
Tabs: Guardrails (per-category floors/max discounts table, stock-out tolerance slider, fatigue cap, leakage limit, capacity limits, budget per objective), Objectives (weight sliders with **live re-rank preview** of the top 10), Channels (costs, reach), Lifecycle thresholds, Demo (clock, reset demo, regenerate data with seed — admin only). Saving triggers re-evaluation + a toast with "7 verdicts changed" + link.

### 13.13 Data Studio — `/data`  [P2]
Dataset cards with "SYNTHETIC" badges (rows, date range, freshness), a data lineage diagram (sources → features → models → engine → UI), model cards (forecast WAPE + backtest chart, elasticity table with CIs, uplift Qini/AUUC, persona silhouette), and privacy panel (IDs hashed, consent coverage, DND excluded, k ≥ 50).

---

## 14. SIGNATURE COMPONENTS — DETAILED SPECS

### 14.1 `PromoSentence`
Props: `tokens, spec, onChange(specPatch), loading`. Text 20px Space Grotesk, slots as inline chips with an ember dashed underline, hover → `ember-soft` bg, focus-visible ring. Keyboard: Tab through slots, Enter opens the editor, Esc closes. While simulating, the changed slot shows a tiny spinner. Wraps naturally; on narrow screens it becomes a vertical key-value list.

### 14.2 `BurnDownChart`
x = days (today → window end + 14), y = units on hand. Per store: p50 line, P10–P90 band (15% opacity), dashed safety-stock line, inbound PO markers (▲ with qty label), shaded campaign window, **stock-out point** (red pulsing dot + label "Stock-out 4 Nov"), a "no-promo" ghost line (dashed, faint) for comparison. The toggle "All stores" shows small multiples (3 columns). Animates line draw on first render (500 ms).

### 14.3 `ReadinessRing`
SVG ring 120px (small 28px variant for lists). 7 arcs with 2° gaps, arc length ∝ weight, fill ∝ value (track in `surface-3`). Centre: score (Space Grotesk 32) + verdict label. Colour by verdict. Arcs fill sequentially on mount (60 ms stagger).

### 14.4 `UpliftQuadrant`
Scatter with quadrant background tints (Persuadables: ember-soft; Sure Things: gold 8%; Lost Causes: neutral; Sleeping Dogs: block 8%), labelled in corners in micro caps. Bubbles labelled by persona. The "₹ view" toggle morphs bubble sizes (animated 400 ms).

### 14.5 `DiscountFrontier`
x = depth (0–30%), two y-axes: ΔGP (ember line) and ΔRevenue (cyan line); stock-out probability as a background band (turns red past the gate); the **sweet spot** marker at the max ΔGP point with label; the current depth as a vertical ember line (draggable → updates the sentence). Also plots non-price offers as distinct markers at x = 0 ("Early access", "Free installation").

### 14.6 `MarginWaterfall`
Vertical waterfall; positive bars `go`, negative bars `block` at 80% opacity, totals `ember`; value labels in ₹ compact; hover explains each step.

### 14.7 `GenomeGlyph`
SVG 16-petal radial glyph: petal length = dimension value, petal colour grouped by family (product = ember, offer = gold, audience = violet, context = cyan). Size variants 32/64/160. On hover of a twin, draws it as an outline over the current glyph.

### 14.8 `MismatchMap`
ECharts geo with the `india_states.geojson` (registered as 'india'); `effectScatter` for surging cities (ripple period 4 s), `scatter` for others, `lines` with effect for transfers, and optional `heatmap`/halo for events. Roam enabled (zoom 1–6), reset button, keyboard-focusable city list fallback for accessibility.

### 14.9 `SignoffSeals` & `VerdictStamp`
Seals: 3 × 28px circles with role initials; states as in 13.10. Stamp: a bordered, uppercase, slightly rotated label with a rough-edge SVG mask for the "rubber stamp" feel; used on verdict panels and Court cards.

### 14.10 `LiveTicker` / `PulseFeed`
Shared SSE hook `usePulse()` (EventSource with backoff reconnect; keeps the last 50 events in Zustand). The feed item enters with a slide+fade from the top (200 ms); critical events get a 1-time ember flash.

### 14.11 `KpiTile`
Label (micro caps) + ⓘ, value (count-up), delta pill, 60×24 sparkline, optional status dot; clickable (hover border ember).

---

## 15. MOTION & DYNAMIC ELEMENTS (keep it "normal", not flashy)

| Element | Motion | Duration |
|---|---|---|
| Page change | fade + 8px rise | 200 ms |
| Lists/cards | stagger in (max 12 items) | 25 ms/item |
| KPI numbers | count-up on load/value change | 600 ms ease-out |
| Metric changed after simulate | background flash green/red → transparent | 800 ms |
| Verdict change | stamp scales 1.2 → 1 with rotate | 280 ms |
| Readiness ring | arcs fill sequentially | 60 ms stagger |
| Charts | ECharts entry animation | 500 ms |
| Map | surging-city ripple, transfer arcs travelling | 4 s loops |
| Radar sweep | rotation | 8 s loop |
| Live dot | opacity pulse | 2 s loop |
| Ticker | marquee | 45 s loop, pause on hover |
| Seal stamp | scale 1.3 → 1 + shadow | 280 ms |
| Time Warp reveal | days fill left→right | ~2 s, skippable |
| Skeleton | shimmer | 1.2 s |

**Not allowed**: particles, 3D, parallax, confetti, heavy glassmorphism, bouncing springs on data, auto-playing sounds. With `prefers-reduced-motion`: disable loops, count-ups and sweeps; keep instant state changes.

Accessibility: WCAG AA contrast for text; focus rings (2px ember + 2px offset); every chart has an accessible table fallback ("View data" toggle); verdicts use icon + text; all interactive elements are keyboard reachable; `aria-live="polite"` for simulate results and pulse updates.

---

## 16. FRONTEND STATE, DATA & CODE CONVENTIONS

- `store/context.ts` (Zustand): `{windowPreset, windowStart, windowEnd, region, city, category, objective}` + URL sync via a `useSyncContextToUrl` hook.
- `store/role.ts`: `{user, role}` persisted in `localStorage` (wrapped in try/catch).
- `api/client.ts`: fetch wrapper with base `/api`, JSON errors → typed `ApiError`, and a request id header.
- `api/hooks/*`: `useDashboard(ctx)`, `useRecommendations(ctx, filters)`, `useRecommendation(id)`, `useSimulate()` (mutation, debounced, cancels the previous request with AbortController), `useCounterfactuals(id)`, `useMap(ctx)`, `useBlocked(ctx)`, `useCampaigns()`, `useSignoff()` (optimistic update of seals), `usePulse()`, `useAsk()`.
- Query keys always include the context; `staleTime` 60 s for analytics, 0 for campaigns.
- Components are dumb and receive typed props; pages compose hooks + components.
- Types come from `schema.d.ts` generated via `npm run gen:api` (`openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts`).
- Lint: ESLint + Prettier; no `any` in `components/`.

---

## 17. BUILD PHASES (give Claude Code one phase at a time)

| Phase | Build | Acceptance criteria |
|---|---|---|
| **0 Scaffold** | Repo structure (Section 5), Makefile, `.env.example`, FastAPI hello `/api/health`, Vite+React+TS+Tailwind+shadcn app with tokens.css, fonts, dark/light toggle, `/api` proxy, CLAUDE.md | `make dev` runs both; the frontend shows the Prometheus shell with the flame logo and fetches `/api/health` |
| **1 Synthetic world** | `data_gen/*` (Section 6) incl. events.csv, world simulator, 10 stories, `validate.py` report | `make data` < 5 min; row counts within ±20% of Section 6; `validate.py` passes all 10 story assertions; identical output hash for SEED=42 twice |
| **2 Models** | `features`, `segmentation`, `forecast`, `elasticity`, `uplift`, `affinity`, `cannibalization`, `fatigue` + `train_all.py` + `metrics.json` | Forecast WAPE reported; elasticity within ±30% of truth for ≥ 9/12 categories (test); uplift AUUC > random; ≥ 60% of true persuadables land in the Persuadable quadrant; 8 named personas each ≥ 50 customers |
| **3 Engine** | inventory, opportunities, candidates, simulator, guardrails, readiness, ranking, explain, counterfactual, genome, insights, transfers | Unit tests for the formulas; **story tests**: S1 HYD → GO/COND and Pune broad 20% → BLOCK with R-STK-001; S3 → R-FAT-001; S4 → R-LEAK-001; S6 national AC → R-LOC-001; S1 transfer MUM-03→PUN-01 suggested; `/simulate` p95 < 150 ms |
| **4 API & workflow** | All routers (Section 9), SQLite models, state machine, seals, audit, notifications, SSE pulse, seed demo campaigns, `/admin/reset-demo` | OpenAPI complete; pytest API tests for every endpoint; illegal transitions → 409; SSE emits every 6–12 s |
| **5 Frontend foundation** | Design system (Section 11), shell (12), context bar, role switcher, ⌘K palette (nav + fallback ask), API client + generated types, TanStack Query hooks, format lib, ECharts theme, all primitives & data components, skeleton/empty/error states | Storybook-like `/dev/components` route showing every component in both themes; Lighthouse accessibility ≥ 90 on the shell |
| **6 P0 pages** | Mission Control, Promotion Forge (all 7 tabs, sentence editing with live simulate), Mismatch Map + Matrix, Guardrail Court, Approval Board (seals, lenses, pre-flight, audit, comments) | Full demo story S1 is clickable end-to-end (Section 19 steps 1–8); no mock data; every chart shows an insight |
| **7 P1 pages** | Scenario Lab, Audience Studio, Festival Pulse, Store Readiness, Campaign Memory + Time Warp + calibration, live ticker/feed | Time Warp completes and updates calibration; collisions show on the timeline; Scenario "promote to campaign" works |
| **8 P2 polish** | LLM narrative + NL ask (with fallback), Opportunity Radar, Settings with live re-rank, Data Studio, guided demo tour, brief PDF, drag-to-reschedule | Works with `LLM_ENABLED=false` identically (template text); the number-safety check test passes |
| **9 Hardening** | Playwright E2E (3 flows below), perf pass, responsive pass, reduced-motion pass, README with screenshots | All tests green; demo rehearsed twice after `make demo-reset` |

**E2E flows**: (1) Home → Forge the HYD TV opportunity → change depth 10→15 → see metrics flash + verdict change → back to 10 → send for sign-off. (2) Switch roles Marketing → Merchandising → Store Ops, stamp seals → approved → launch → Time Warp → Memory shows result. (3) Court → Pune case → "Forge admissible version" → CONDITIONAL.

---

## 18. TESTING & QUALITY

- **Backend**: pytest for data invariants (no negative stock, prices ≥ cost × 0.8, dates in range), formula unit tests (waterfall sums to ΔGP within ₹1), guardrail tests per reason code, story tests (Phase 3), API contract tests, determinism test.
- **Leakage guard test**: grep/AST test that no module under `app/engine` except `timewarp.py` imports `data_gen`, and none reads `data/_truth`.
- **Frontend**: Vitest for `format.ts` (lakh/crore), verdict helpers, sentence token rendering; Testing Library for PromoSentence editing and SignoffSeals states; Playwright E2E.
- **Visual QA checklist**: both themes, 1280/1440/1920 widths, keyboard-only walkthrough, reduced motion, empty states (filter to a city with no opportunities), API down state.

---

## 19. DEMO SCRIPT (6 minutes) — `docs/DEMO_SCRIPT.md`

1. **Problem (20 s)**: "Prometheus runs Diwali promos blind: marketing, merchandising and stores each have their own spreadsheet. The result is stock-outs in Pune, dead laptops in Delhi, and discounts handed to people who'd buy anyway."
2. **Mission Control (40 s)**: as Ananya (Marketing). Countdown "Diwali in 38 days". The KPI tiles; the pulse ticker shows "Search spike 55″ TVs Hyderabad +42%". Point to "₹1.8 Cr risk already blocked".
3. **Map (40 s)**: the TV layer. Hyderabad = hot demand + rich stock; Pune = hot demand + 8 days cover. The transfer arc MUM-03 → PUN-01 animates. Kolkata glows (Durga Puja).
4. **Forge (90 s)**: open the #1 recommendation. Read the **Promo Sentence** aloud. Show the Readiness Ring 82 GO, the waterfall (leakage & shift subtracted: "this is *incremental* profit"). Change depth **10 → 15%**: revenue ↑, profit ↓, stock-out risk ↑, the verdict drops to CONDITIONAL. Open the **Frontier**: "profit peaks at 10%". Back to 10%. Show **Why** and **Twins** ("Diwali 2025 HYD bundle delivered 2.7× ROI").
5. **Guardrail Court (40 s)**: the Pune 20% case, with the burn-down exhibit hitting zero on 4 Nov. "To make admissible: transfer 60 units + cap" → Forge admissible version → CONDITIONAL. Also show the Elite-loyalists leakage case → early access instead.
6. **Audience Studio (30 s)**: Uplift Quadrant ₹ view: "41% of last quarter's discounts went to Sure Things."
7. **Approval Board (50 s)**: send for sign-off. Switch to Rohan (Merchandising lens: margin) → seal. Switch to Farhan (Store Ops lens: install calendar at HYD-02) → seal. Ananya seals → approved, gold glow.
8. **Time Warp (30 s)**: launch → ⏩ Time Warp → predicted vs actual fills in → "Engine recalibrated". Close with Memory's calibration panel.
9. **Close (20 s)**: the one-line pitch (Section 1.4) + the problem-statement mapping (Section 20).

Backup: `make demo-reset` before every run; a guided tour button runs the same path.

---

## 20. PROBLEM STATEMENT → FEATURE MAPPING (for the pitch slide)

| Problem statement asks for | PromoForge answer |
|---|---|
| Align customer preference | Personas, intent signals, uplift quadrants, persona-best offer type |
| Inventory availability | Stock burn-down, P(stock-out), caps, transfers, R-STK gates |
| Local demand patterns / regional variation | Mismatch Map & Matrix, city search index, regional event intensity, R-LOC gate |
| Margin objectives | Incremental GP waterfall, margin floors, leakage, Discount Frontier, objective presets |
| Avoid over-promoting low-stock items | Guardrail Court (R-STK-001) + admissible counterfactuals |
| Missed high-demand opportunities | Opportunity Feed/Radar (DEMAND_SURGE, FESTIVAL_WINDOW, CROSS_SELL_GAP) |
| Discounts that don't build loyalty | Uplift-based targeting, retention value, fatigue meter, non-price offers |
| Shared view for marketing, merchandising, store ops | **Three-Lens Sign-off**, shared readiness score, pre-flight checklist, audit, live pulse |
| Beyond broad historical segmentation | Recent intent, lifecycle transitions, micro-segments |
| Clear explanations & operational risks | Why / Why-not / drivers / reason codes / twins / what-if |
| Planning views, summaries, impact indicators, approval workflow | Forge, Scenario Lab, Festival Pulse, KPI tiles, Approval Board |
| Synthetic data for seasonal promos, stock constraints, responses | Causal digital twin with 10 planted stories + holdouts |
| Intelligent decision-making without prescribing implementation | Human-in-the-loop: AI proposes, teams edit/approve, Time Warp closes the loop |

---

## 21. RUN INSTRUCTIONS (README excerpt)

```bash
cp .env.example .env
make setup        # pip install -e backend[dev]; npm ci in frontend
make seed         # generate data (SEED=42) → train models → precompute caches
make dev          # API http://localhost:8000/docs · UI http://localhost:5173
make test         # pytest + vitest
make e2e          # playwright
make demo-reset   # restore seeded campaigns/state before a demo
```

---

## 22. NON-GOALS / DON'TS FOR CLAUDE CODE

- No real retailer names, real brands, real customer data or scraped data.
- No authentication system (role switcher only); no multi-tenant.
- No second chart library, no CSS-in-JS runtime, no Redux.
- No hard-coded "demo answers" in the engine or frontend; stories must emerge from data.
- No LLM dependency for core functionality; LLM text never introduces new numbers.
- No infinite animations except those listed in Section 15.
- No individual customer rows in the UI (aggregates only; min group size 50).
- Don't over-engineer infra (no Kafka, no Kubernetes, no microservices).
