"use client";
// Small dynamic building blocks: tooltips, tweened numbers, confidence ring, funnel, confetti.
import { AnimatePresence, animate, motion, useMotionValue, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { inr, num } from "@/lib/api";

export const GLOSSARY: Record<string, string> = {
  confidence: "A 0–100 score combining five checks: profit, stock, customer response, store capacity and message fatigue. 70+ is safe to run.",
  profit: "Extra profit the promotion adds after discounts, messaging costs and any lost sales from running out, compared with doing nothing.",
  units: "Units sold because of the promotion, on top of what would sell anyway.",
  stockout: "The chance the city runs out of this product during the promotion, based on current stock, deliveries on the way and expected demand.",
  wasted: "Discount given to customers who would have bought at full price anyway. Our uplift model targets people an offer actually persuades to cut this.",
  safe: "Ideas that pass every safety rule: enough margin, stock that lasts, a large enough customer group, and customers not over-messaged.",
  checked: "Every combination of customer group × product × city × discount the engine simulated for this season.",
  picked: "The best safe promotions for your chosen goal, ranked.",
  uplift: "How many more people buy when they get an offer, compared with similar people who didn't (a real holdout group from past campaigns).",
};

export function Tip({ k, text }: { k?: string; text?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const body = text ?? (k ? GLOSSARY[k] : "");
  return (
    <span className="tip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      {/* a span, not a button: tips sit inside clickable cards, and buttons can't nest */}
      <span role="button" tabIndex={0} aria-label="What does this mean?" className="tip-q" aria-describedby={id} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); } else if (e.key === "Escape") setOpen(false); }}>?</span>
      <AnimatePresence>
        {open && <motion.span id={id} role="tooltip" className="tip-pop" initial={{ opacity: 0, y: 4, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 4 }} transition={{ duration: 0.14 }}>{body}</motion.span>}
      </AnimatePresence>
    </span>
  );
}

/** Tweens from the previous value to the new one whenever `value` changes. */
export function Tween({ value, fmt = "num", suffix = "" }: { value: number; fmt?: "num" | "inr" | "pct0"; suffix?: string }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const [shown, setShown] = useState(value);
  useEffect(() => {
    if (reduce) { mv.set(value); return; }
    const c = animate(mv, value, { duration: 0.6, ease: [0.2, 0.7, 0.2, 1], onUpdate: setShown });
    const done = setTimeout(() => setShown(value), 700);
    return () => { c.stop(); clearTimeout(done); };
  }, [value, reduce, mv]);
  const v = reduce ? value : shown;
  const f = fmt === "inr" ? inr(v) : fmt === "pct0" ? `${Math.round(v)}%` : num(v);
  return <>{f}{suffix}</>;
}

export function Ring({ value, size = 84, color = "var(--accent)" }: { value: number; size?: number; color?: string }) {
  const r = (size - 10) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value));
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--soft)" strokeWidth={8} fill="none" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={8} fill="none" strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - v / 100) }} transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }} />
      </svg>
      <div className="ring-in"><b><Tween value={v} /></b><small>/100</small></div>
    </div>
  );
}

/** Horizontal funnel: each stage's bar width is proportional to sqrt(count) so small stages stay visible. */
export function Funnel({ stages }: { stages: { v: number; label: string; tip: string; tone?: string }[] }) {
  const max = Math.sqrt(Math.max(1, ...stages.map((s) => s.v)));
  return (
    <div className="funnel">
      {stages.map((s, i) => (
        <div key={s.label} className="fn-row">
          <div className="fn-bar-wrap">
            <motion.div className="fn-bar" style={{ background: s.tone }} initial={{ width: 0 }} animate={{ width: `${Math.max(6, (Math.sqrt(s.v) / max) * 100)}%` }}
              transition={{ delay: i * 0.18, duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }}>
              <b><Tween value={s.v} /></b>
            </motion.div>
          </div>
          <div className="fn-label">{s.label} <Tip k={s.tip} /></div>
          {i < stages.length - 1 && <div className="fn-drop">{stages[i + 1].v && s.v ? `${Math.round((stages[i + 1].v / s.v) * 100)}% pass to next step` : ""}</div>}
        </div>
      ))}
    </div>
  );
}

/** A short, lightweight celebration burst (no library). */
export function Confetti({ fire }: { fire: number }) {
  const reduce = useReducedMotion();
  const [bits, setBits] = useState<{ id: number; x: number; r: number; c: string; d: number; dx: number; t: number }[]>([]);
  const n = useRef(0);
  useEffect(() => {
    if (!fire || reduce) return;
    const cols = ["#4f46e5", "#7c3aed", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4"];
    const t = setTimeout(() => setBits(Array.from({ length: 70 }, () => ({ id: n.current++, x: Math.random() * 100, r: Math.random() * 540 - 270, c: cols[Math.floor(Math.random() * cols.length)], d: Math.random() * 0.4, dx: (Math.random() - 0.5) * 160, t: 2 + Math.random() }))), 0);
    const clear = setTimeout(() => setBits([]), 2600);
    return () => { clearTimeout(t); clearTimeout(clear); };
  }, [fire, reduce]);
  return (
    <div className="confetti" aria-hidden>
      {bits.map((b) => (
        <motion.i key={b.id} style={{ left: `${b.x}%`, background: b.c }} initial={{ y: -20, opacity: 1, rotate: 0 }}
          animate={{ y: "105vh", opacity: [1, 1, 0], rotate: b.r, x: b.dx }} transition={{ duration: b.t, delay: b.d, ease: "easeIn" }} />
      ))}
    </div>
  );
}
