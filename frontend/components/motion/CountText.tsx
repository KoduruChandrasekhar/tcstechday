"use client";
import { useLayoutEffect, useRef } from "react";
import { gsap, reduced, skippable } from "./gsap";

const NUM = /-?[\d,]*\.?\d+/;

/**
 * Counts the figure inside a formatted string up from zero, keeping its prefix, suffix and decimals:
 * "1,944", "₹11.6 L", "15". Text without a number is shown as it is.
 */
export default function CountText({ text, delay = 0, duration = 0.9 }: { text: string; delay?: number; duration?: number }) {
  const el = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const node = el.current, m = NUM.exec(text);
    if (!node || !m || reduced() || duration <= 0) return;
    const raw = m[0], target = parseFloat(raw.replace(/,/g, "")), dec = (raw.split(".")[1] || "").length;
    const pre = text.slice(0, m.index), post = text.slice(m.index + raw.length);
    const show = (v: number) => { node.textContent = v >= target ? text : pre + v.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + post; };
    const o = { v: 0 };
    show(0);
    const t = skippable(gsap.to(o, { v: target, duration, delay, ease: "power2.out", onUpdate: () => show(o.v) }));
    return () => { t.kill(); node.textContent = text; };
  }, [text, delay, duration]);
  // keyed on the text so React never tries to update a node GSAP has rewritten
  return <span ref={el} key={text} className="num">{text}</span>;
}
