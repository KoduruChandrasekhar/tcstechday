# Uplift model benchmark

Data: 174,969 campaign exposures (157,505 treated, 17,464 holdout control); overall observed uplift 0.75 pts (30-day conversion).
Every score is out-of-fold (5-fold cross-fitting), so no exposure is scored by a model trained on it.

| Model | Qini coefficient | Top-30% uplift (pts) | 90% CI | Rest (pts) |
|---|---|---|---|---|
| T-learner · logistic regression (current) | 2.154 ×10⁻³ | 1.78 | 1.25 – 2.35 | 0.31 |
| T-learner · XGBoost | 0.766 ×10⁻³ | 1.22 | 0.58 – 1.80 | 0.54 |
| S-learner · XGBoost | 1.594 ×10⁻³ | 1.80 | 1.23 – 2.35 | 0.29 |

Best Qini: **T-learner · logistic regression (current)**.

Qini coefficient = area between the model's cumulative-incremental-buyers curve and random targeting, per customer. Top-30% uplift = observed treated-minus-control conversion among the 30% the model ranks most persuadable. Overlapping CIs mean the difference is not conclusive at this sample size.
