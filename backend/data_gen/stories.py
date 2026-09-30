"""The ten planted business stories (PLAN §6.7).

Stories are planted only through *world parameters* - trait tweaks, intent
multipliers, allocation / supply decisions, attach propensities, calendar
entries and campaign plans. Observed tables are never edited afterwards.
Each story's mechanism and the evidence it should leave are written to
``_truth/story_truth.parquet``.
"""
from __future__ import annotations

from datetime import date

STORIES = [
    dict(story_id="S1", title="Diwali TV - Hyderabad vs Pune",
         mechanism="55in TV journey-start rate x1.45 in HYD & PUN from 2026-09-10 with TV_55 sub-choice x2.2; West supplier allocation "
                   "shortage from 2026-08-20 pushes PUN 55U7/55Q8 POs to 2026-11-12; HYD over-allocated to ~53 days cover; MUM-03 over-allocated on 55U7",
         evidence="TV_55 views last 21d vs prior 28d >= +25% in HYD & PUN; HYD 55U7/55Q8 cover 46-60 d; PUN-01/02 cover 6-10 d; open PO ETA 2026-11-12; MUM-03 excess >= 40 units above 30-day cover",
         params=dict(intent_mult=1.45, sub_mult=2.2, start="2026-09-10", pune_block_from="2026-08-20", pune_eta="2026-11-12",
                     hyd_cover=53, pune_cover=8, mum03_extra=70)),
    dict(story_id="S2", title="Aging laptops - Delhi NCR",
         mechanism="Bulk buy of 360 Kairo Air 14 (2025) received 2026-05-18 into DEL-01/02/03; model EOL 2026-08-01 with 2026 successor launched 2026-08-05; "
                   "merchandising held price (4% markdown instead of standard clearance); residual trimmed to ~210 via return-to-DC on 2026-09-12",
         evidence="DEL stores hold 180-240 units of LAP-KAI-14A25 with average age >= 120 days; weekly sales fall after the successor launch",
         params=dict(bulk_units=360, bulk_day="2026-05-18", target_units=210, trim_day="2026-09-12")),
    dict(story_id="S3", title="Deal-hunter fatigue",
         mechanism="Naive team sends 'Flash Deals' to observable deal hunters (metro, promo share >= 40%) ~monthly, then 9 blasts between 2026-08-02 and 2026-09-26; "
                   "true uplift decays as exp(-fatigue_k x exposures_60d); unsubscribe hazard rises with exposures",
         evidence="Flash-deal treated 7-day response of the last blasts <= 45% of the early ones; median exposures_60d of the segment >= 7; unsub rate rises",
         params=dict(blasts_last_60d=9)),
    dict(story_id="S4", title="Elite loyalists = Sure Things",
         mechanism="Elite tier assigned mostly uplift_type=sure_thing; elite customers' phone replacement is always 'due' and phone launches add x2.2 intent for elite",
         evidence="Circle phone-launch campaigns: control 30-day conversion >= 20% and treated minus control <= 4 pp; early-access variant shows non-price response",
         params=dict(elite_launch_mult=2.2, elite_rate_mult=1.6)),
    dict(story_id="S5", title="Cannibalisation 50U5 -> 55U7",
         mechanism="Nested-logit SKU choice with substitute_group nests (lambda=0.45); TV-AUR-50U5 receives 7 deal-of-the-week markdowns and 5 targeted campaigns",
         evidence="55U7 weekly units drop when 50U5 is discounted; true kappa for TV_AUR_50_55 in _truth/cannibalisation_truth",
         params=dict(nest_lambda=0.45)),
    dict(story_id="S6", title="AC regional split",
         mechanism="Winter cool-down event (AC x0.15, north intensity 1.0, Chennai 0.05) plus Chennai AC city multiplier 1.7; Chennai stores over-allocated with AC on 2026-09-05",
         evidence="Oct-Nov AC units per store in Chennai >= 2x North; national AC campaigns in Oct-Nov earn most incremental sales in Chennai; Chennai AC cover >= 45 d",
         params=dict(chennai_cover=60)),
    dict(story_id="S7", title="Kolkata Durga Puja",
         mechanism="Durga Puja event with TV/REF uplift 2.2 at Kolkata intensity 1.0 (others <= 0.12); Kolkata stock topped up to >= 30 days cover before Puja 2026",
         evidence="Kolkata TV+REF units in Puja windows >= 1.7x its baseline, other cities not; Kolkata TV/REF cover >= 30 d on 2026-09-30",
         params=dict(kolkata_cover=35)),
    dict(story_id="S8", title="At-risk washing-machine browsers",
         mechanism="On 2026-09-16 customers who are at_risk by the observable lifecycle rule and have washing-machine affinity get a WM replacement-due intent spike (x9 for 14 days)",
         evidence="~1,300 (1,000-1,700) customers that are at_risk on 2026-09-30 viewed WM pages in the last 14 days; appliance win-back campaigns show T>C repeat_180d",
         params=dict(select_day="2026-09-16", n_target=1900, boost=9.0)),
    dict(story_id="S9", title="Installation capacity crunch BLR-02",
         mechanism="Forward installation bookings = booking-curve baseline + a bulk residential-society AC/TV install drive booked at BLR-02 for 2026-11-02..08",
         evidence="BLR-02 forward install utilisation 2-8 Nov between 88% and 96%",
         params=dict(store="BLR-02", start="2026-11-02", end="2026-11-08", target_util=0.92)),
    dict(story_id="S10", title="Cross-sell gap - laptop bags in Hyderabad",
         mechanism="Laptop -> bag in-order attach propensity 0.22 everywhere x city noise, but x0.41 in Hyderabad (merchandising placement)",
         evidence="Hyderabad laptop orders with a bag ~9% vs peer average ~22% (gap >= 8 pp)",
         params=dict(base_attach=0.22, hyd_mult=0.41)),
]

S1_START = date(2026, 9, 10)
S1_CITIES = ("HYD", "PUN")
S1_SKUS = ("TV-AUR-55U7", "TV-AUR-55Q8")
PUNE_BLOCK_FROM = date(2026, 8, 20)
PUNE_ETA = date(2026, 11, 12)
S2_SKU = "LAP-KAI-14A25"
S2_BULK_DAY = date(2026, 5, 18)
S2_TRIM_DAY = date(2026, 9, 12)
S2_STORES = {"DEL-01": 140, "DEL-02": 120, "DEL-03": 100}
S5_DEAL_WEEKS = [date(2025, 3, 10), date(2025, 6, 2), date(2025, 8, 11), date(2025, 11, 24), date(2026, 2, 16),
                 date(2026, 4, 6), date(2026, 7, 13)]
S6_DAY = date(2026, 9, 5)
S7_DAY = date(2026, 9, 20)
S8_DAY = date(2026, 9, 16)
FINAL_ALLOC_DAY = date(2026, 9, 30)
MUM03_DAY = date(2026, 9, 15)
HYD_BAG_ATTACH_MULT = 0.41
