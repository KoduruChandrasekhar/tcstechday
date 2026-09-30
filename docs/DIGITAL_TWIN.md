# How the Prometheus digital twin works
`backend/data_gen/world.py` simulates 90 warm-up + 730 history days, vectorised over 25k customers x 12 categories.

1. **Latent traits** (Gaussian copula): price sensitivity, promo responsiveness, tier preference, purchase rate, churn hazard, online propensity, category affinity (Dirichlet by age), fatigue_k, festival affinity; uplift_type derived from traits (28/22/45/5%).
2. **Intent**: journey-start hazard = rate x affinity x city/store multipliers x season x festival (x festival affinity) x replacement-due x complement boost x story multipliers x active state.
3. **Journeys -> web**: journeys last 3-21 days and emit web activity (web leads purchases).
4. **Conversion**: base conversion x (1 - open markdown)^(-elasticity x sensitivity) x payday x day-of-week; sleeping-dog suppression.
5. **Channel, store, SKU**: nested logit within substitute groups (cannibalisation), stock check (substitute 55% / online 20% / lost 25%).
6. **Order**: attach services/accessories (city-specific), discounts (markdown, deal, clearance, campaign), installation & ship-from-store capacity, returns, reviews.
7. **Inventory**: FIFO cohorts, weekly naive (s,S) replenishment from EWMA of sales, stochastic lead times and delays.
8. **Campaigns**: naive team targets on observable rules; 10% holdout; uplift = U0 x responsiveness x g(depth) x (1+sensitivity) x relevance x exp(-fatigue_k x exposures_60d) x type multiplier; unsubscribes rise with pressure; retention effects for win-back.
9. **Lifecycle**: churn hazard, spontaneous / purchase / campaign reactivation.
10. **Stories S1-S10** planted via parameters only (see `stories.py`, `_truth/story_truth`).
