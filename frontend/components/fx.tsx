"use client";
// Glossary tooltips and tweened figures.
import { AnimatePresence, animate, motion, useMotionValue, useReducedMotion } from "motion/react";
import { useEffect, useId, useState } from "react";
import { inr, num } from "@/lib/api";

export const GLOSSARY: Record<string, string> = {
  confidence: "A score out of 100 built from five checks: profit, stock, customer response, store capacity and message fatigue. 70 or more is safe to run.",
  profit: "Profit the promotion adds after discounts, messaging costs and sales lost to running out, compared with doing nothing.",
  units: "Units sold because of the promotion, on top of what would sell anyway.",
  stockout: "The chance this city runs out during the promotion, from stock on hand, deliveries on the way and expected demand.",
  wasted: "Discount given to people who would have bought at full price anyway. Targeting only persuadable customers keeps this low.",
  uplift: "How many more people buy with an offer than similar people who didn't get one, measured on holdout groups from past campaigns.",
  cover: "How many days current stock lasts at the festival rate of sale.",
  roi: "Profit returned for every ₹1 spent on discount.",
};

export function Tip({ k, text }: { k?: string; text?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const body = text ?? (k ? GLOSSARY[k] : "");
  return (
    <span className="tip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      {/* a span, not a button: tips sit inside clickable rows, and buttons can't nest */}
      <span role="button" tabIndex={0} aria-label="What does this mean?" aria-describedby={open ? id : undefined} className="tip-q"
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); } else if (e.key === "Escape") setOpen(false); }}>i</span>
      <AnimatePresence>
        {open && <motion.span id={id} role="tooltip" className="tip-pop" initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}>{body}</motion.span>}
      </AnimatePresence>
    </span>
  );
}

/** Animates from the previous value to the new one, so a change reads as a change. */
export function Tween({ value, fmt = "num" }: { value: number; fmt?: "num" | "inr" | "pct0" }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const [shown, setShown] = useState(value);
  useEffect(() => {
    if (reduce) { mv.set(value); return; }
    const c = animate(mv, value, { duration: 0.5, ease: [0.2, 0.7, 0.2, 1], onUpdate: setShown });
    const done = setTimeout(() => setShown(value), 600);
    return () => { c.stop(); clearTimeout(done); };
  }, [value, reduce, mv]);
  const v = reduce ? value : shown;
  return <>{fmt === "inr" ? inr(v) : fmt === "pct0" ? `${Math.round(v)}%` : num(v)}</>;
}
