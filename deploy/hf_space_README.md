---
title: PromoForge API
emoji: 📈
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: AI promotion & inventory alignment planner (FastAPI engine)
---

# PromoForge backend

FastAPI decision engine for PromoForge: causal uplift targeting, inventory and margin guardrails, and a grounded
Gemini writing layer, running on a synthetic Indian electronics retailer.

- API: `/api/meta`, `/api/recommendations?objective=profit&window=diwali`, ...
- The original single-page UI is served at `/`; the main Next.js frontend is deployed separately and proxies `/api/*` here.

Optional secret: `GEMINI_API_KEY` (without it the app shows built-in template text instead of AI-written text).
