"""Store x SKU inventory: FIFO receipt cohorts, weekly (s, S) replenishment, POs.

The replenishment policy is deliberately *naive*: it forecasts from an EWMA of
observed sales (lost demand is invisible to it), only partially anticipates
festivals, and supply lead times are stochastic with occasional delays. That is
what creates realistic stock-outs, excess and aging stock.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np


class Inventory:
    def __init__(self, rng: np.random.Generator, n_stores: int, n_sku: int, ranged: np.ndarray, sku: dict,
                 store_region: np.ndarray, region_dc: list[str], store_ids: list[str], sku_ids: list[str],
                 day_dates: list, history_start_idx: int):
        self.rng = rng
        self.S, self.P = n_stores, n_sku
        self.ranged = ranged.copy()
        self.sku = sku
        self.store_region = store_region
        self.region_dc = region_dc
        self.store_ids, self.sku_ids = store_ids, sku_ids
        self.dates = day_dates
        self.h0 = history_start_idx
        self.on_hand = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.on_order = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.ewma = np.zeros((n_stores, n_sku))
        self.sales_today = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.lost_today = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.receipts_today = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.cohorts = [deque() for _ in range(n_stores * n_sku)]
        self.pos: list[dict] = []
        self.po_due: dict[int, list[int]] = {}
        self.blocked_until: dict[tuple[int, int], tuple[int, int]] = {}  # (s,p) -> (from_day, forced_eta_day)
        self.no_reorder: set[tuple[int, int]] = set()
        # weekly ledger
        self.w_sales = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.w_receipts = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.w_oos = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.w_lost = np.zeros((n_stores, n_sku), dtype=np.int64)
        self.weekly_rows: list[tuple] = []
        self.daily_on_hand: list[np.ndarray] = []
        self.daily_sales: list[np.ndarray] = []
        self.transfers: list[dict] = []

    # ------------------------------------------------------------ primitives
    def _k(self, s, p):
        return s * self.P + p

    def add_stock(self, s, p, qty, day):
        if qty <= 0:
            return
        self.on_hand[s, p] += qty
        self.cohorts[self._k(s, p)].append([day, qty])

    def remove_stock(self, s, p, qty, newest_first=False):
        """Remove qty units (FIFO by default). Returns units removed."""
        q = min(qty, int(self.on_hand[s, p]))
        if q <= 0:
            return 0
        self.on_hand[s, p] -= q
        dq = self.cohorts[self._k(s, p)]
        left = q
        while left > 0 and dq:
            c = dq[-1] if newest_first else dq[0]
            take = min(left, c[1])
            c[1] -= take
            left -= take
            if c[1] == 0:
                dq.pop() if newest_first else dq.popleft()
        return q

    def sell(self, s, p, qty):
        q = self.remove_stock(s, p, qty)
        self.sales_today[s, p] += q
        return q

    def avg_age(self, s, p, day):
        dq = self.cohorts[self._k(s, p)]
        tot = sum(c[1] for c in dq)
        if tot == 0:
            return None, 0
        age = sum((day - c[0]) * c[1] for c in dq) / tot
        aged90 = sum(c[1] for c in dq if day - c[0] > 90)
        return age, aged90

    def last_receipt(self, s, p):
        dq = self.cohorts[self._k(s, p)]
        return dq[-1][0] if dq else None

    # ------------------------------------------------------------ purchase orders
    def create_po(self, s, p, qty, day, po_type="replenishment", eta_override=None, lead_days=None):
        if qty <= 0:
            return None
        imported = bool(self.sku["is_imported"][p])
        if lead_days is None:
            mean = 21.0 if imported else 10.0
            lead_days = int(max(2, round(self.rng.lognormal(math.log(mean) - 0.045, 0.3))))
        planned = day + lead_days
        delay = 0
        if po_type == "replenishment" and self.rng.random() < 0.05:
            delay = int(self.rng.integers(7, 15))
        eta = planned + delay
        blk = self.blocked_until.get((s, p))
        if blk is not None and day >= blk[0]:
            eta = max(eta, blk[1])
            planned = max(planned, blk[1])
        if eta_override is not None:
            eta = planned = eta_override
        idx = len(self.pos)
        self.pos.append(dict(s=s, p=p, qty=int(qty), created=day, planned=planned, eta=eta, delay=eta - planned,
                             type=po_type, received=None))
        self.po_due.setdefault(eta, []).append(idx)
        self.on_order[s, p] += qty
        return idx

    def receive_due(self, day):
        for idx in self.po_due.pop(day, []):
            po = self.pos[idx]
            self.on_order[po["s"], po["p"]] -= po["qty"]
            self.add_stock(po["s"], po["p"], po["qty"], day)
            self.receipts_today[po["s"], po["p"]] += po["qty"]
            po["received"] = day

    def transfer_out(self, s, p, qty, day, kind="return_to_dc", to_store=None):
        q = self.remove_stock(s, p, qty, newest_first=True)
        if q > 0:
            self.transfers.append(dict(day=day, s=s, p=p, qty=q, kind=kind, to_store=to_store))
        return q

    # ------------------------------------------------------------ replenishment policy
    def review(self, day, stores: np.ndarray, sellable: np.ndarray, plan_uplift: np.ndarray):
        """(s, S) review for the given stores. plan_uplift[S,P] = merchandiser's anticipated demand multiplier."""
        if len(stores) == 0:
            return
        lt = np.where(self.sku["is_imported"], 21.0, 10.0)
        for s in stores:
            rng_mask = self.ranged[s] & sellable
            if not rng_mask.any():
                continue
            d = self.ewma[s] * plan_uplift[s]
            cover = np.where(self.sku["cat_is_acc"], 21.0, 14.0)
            ss = 1.3 * np.sqrt(d * (lt + 7)) + 2.0 * d
            sp = d * (lt + 7) + ss
            Sp = sp + d * cover
            position = self.on_hand[s] + self.on_order[s]
            minimum = np.where(self.sku["is_big"], 1, 2)
            need = rng_mask & ((position <= sp) | (position < minimum))
            for p in np.nonzero(need)[0]:
                if (s, p) in self.no_reorder:
                    continue
                target = max(Sp[p], minimum[p])
                qty = int(math.ceil(target - position[p]))
                pack = int(self.sku["case_pack"][p])
                qty = int(math.ceil(qty / pack) * pack)
                if qty > 0:
                    self.create_po(s, p, qty, day)

    # ------------------------------------------------------------ end of day bookkeeping
    def end_of_day(self, day, active_mask: np.ndarray, record: bool, week_end: bool, week_label):
        self.ewma = 0.94 * self.ewma + 0.06 * self.sales_today
        if record:
            self.w_sales += self.sales_today
            self.w_receipts += self.receipts_today
            self.w_lost += self.lost_today
            self.w_oos += ((self.on_hand == 0) & self.ranged & active_mask).astype(np.int64)
            self.daily_on_hand.append(self.on_hand.astype(np.int32).copy())
            self.daily_sales.append(self.sales_today.astype(np.int16).copy())
            if week_end:
                keep = self.ranged & (active_mask | (self.on_hand > 0) | (self.w_sales > 0) | (self.w_receipts > 0))
                ss, pp = np.nonzero(keep)
                self.weekly_rows.append((week_label, ss, pp, self.on_hand[ss, pp].copy(), self.w_sales[ss, pp].copy(),
                                         self.w_receipts[ss, pp].copy(), self.w_oos[ss, pp].copy(),
                                         self.on_order[ss, pp].copy(), self.w_lost[ss, pp].copy()))
                self.w_sales[:] = 0
                self.w_receipts[:] = 0
                self.w_oos[:] = 0
                self.w_lost[:] = 0
        self.sales_today[:] = 0
        self.receipts_today[:] = 0
        self.lost_today[:] = 0
