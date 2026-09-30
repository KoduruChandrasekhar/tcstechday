"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { STEPS } from "./steps";
import { VERDICT, fin, inr, num, vk } from "@/lib/api";

const P: Record<string, string> = {
  spark: "M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1",
  truck: "M1 3h15v13H1zM16 8h4l3 3v5h-7M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  check: "M20 6 9 17l-5-5", x: "M18 6 6 18M6 6l12 12", minus: "M5 12h14", plus: "M12 5v14M5 12h14",
  arrow: "M5 12h14M13 5l7 7-7 7", back: "M19 12H5M11 19l-7-7 7-7",
  pin: "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0zM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  box: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96 12 12.01l8.73-5.05M12 22.08V12",
  rupee: "M6 3h12M6 8h12M6 13l8.5 8M6 13h3a4.5 4.5 0 0 0 0-10", store: "M3 9l1-5h16l1 5M4 9v11h16V9M9 20v-6h6v6",
  alert: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01",
  up: "M23 6l-9.5 9.5-5-5L1 18M17 6h6v6", cal: "M3 4h18v18H3zM16 2v4M8 2v4M3 10h18",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z", ff: "M13 19l9-7-9-7v14zM2 19l9-7-9-7v14z",
  wrench: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  bulb: "M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z", logo: "M3 17l6-6 4 4 8-8M15 7h6v6",
  edit: "M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z", chart: "M3 3v18h18M18 17V9M13 17V5M8 17v-3",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35", help: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01",
  menu: "M3 6h18M3 12h18M3 18h18", home: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
};
export function Icon({ n, s = 18 }: { n: string; s?: number }) {
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={P[n] || ""} />
    </svg>
  );
}

export const Pill = ({ v }: { v: string }) => <span className={`pill p-${vk(v)}`}>{VERDICT[vk(v)].label}</span>;

export function PageHead({ step, title, lead, tips }: { step: number; title: string; lead: string; tips: [string, string][] }) {
  const s = STEPS[step - 1];
  return (
    <section className="hero">
      <div className="hero-bg" aria-hidden><span /><span /></div>
      <div className="hero-top">
        <span className="hero-ic"><Icon n={s?.icon || "home"} s={22} /></span>
        <div><div className="kicker">Step {step} of 7 · {s?.label}</div><h1>{title}</h1></div>
      </div>
      <p className="lead">{lead}</p>
      <div className="howto">
        {tips.map(([b, t], i) => (
          <div key={i}><span className="num">{i + 1}</span><span><b>{b}</b>{t}</span></div>
        ))}
      </div>
    </section>
  );
}

export const Answer = ({ icon, children }: { icon: string; children: React.ReactNode }) => (
  <div className="answer"><span className="ic"><Icon n={icon} /></span><div><div className="lbl">In one line</div><p>{children}</p></div></div>
);

export function BarRow({ label, right, pct, color, hl }: { label: React.ReactNode; right: React.ReactNode; pct: number; color?: string; hl?: boolean }) {
  return (
    <div className={`bl ${hl ? "hl" : ""}`}>
      <div className="top"><span>{label}</span><span>{right}</span></div>
      <div className="tr"><i style={{ width: `${Math.max(2, Math.min(100, fin(pct)))}%`, background: color || "var(--accent)" }} /></div>
    </div>
  );
}

export const ErrorBox = ({ msg, retry }: { msg: string; retry?: () => void }) => (
  <div className="err"><span>{msg}</span>{retry && <button className="btn ghost sm" onClick={retry}>Try again</button>}</div>
);

export const Skeleton = ({ n = 3 }: { n?: number }) => (
  <>{Array.from({ length: n }, (_, i) => <div key={i} className="card"><div className="skel" /><div className="skel" style={{ width: "60%", marginTop: 10 }} /></div>)}</>
);

/** Counts up from 0 to `to`; always lands on the final value even if animation frames are paused. */
export function CountUp({ to, fmt = "num" }: { to: number; fmt?: "num" | "inr" }) {
  const f = fmt === "inr" ? inr : num;
  const [st, setSt] = useState<{ to: number; v: number }>({ to: NaN, v: 0 });
  const raf = useRef(0);
  const still = !to || (typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    if (still) return;
    const t0 = performance.now(), d = 800;
    const step = (t: number) => { const k = Math.min(1, (t - t0) / d); setSt({ to, v: to * (1 - Math.pow(1 - k, 3)) }); if (k < 1) raf.current = requestAnimationFrame(step); };
    raf.current = requestAnimationFrame(step);
    const done = setTimeout(() => setSt({ to, v: to }), d + 150);
    return () => { cancelAnimationFrame(raf.current); clearTimeout(done); };
  }, [to, still]);
  return <>{f(still ? to : st.to === to ? st.v : 0)}</>;
}

/** Types text in progressively, like a writer. */
export function TypeIn({ text }: { text: string }) {
  const [st, setSt] = useState({ t: "", n: 0 });
  const still = typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    if (still) return;
    const id = setInterval(() => setSt((s) => {
      const n = s.t === text ? s.n + 3 : 3;
      if (n >= text.length) clearInterval(id);
      return { t: text, n };
    }), 14);
    return () => clearInterval(id);
  }, [text, still]);
  const n = still ? text.length : st.t === text ? st.n : 0;
  return <span className={n < text.length ? "caret" : ""}>{text.slice(0, n)}</span>;
}

export function Pager({ step }: { step: number }) {
  const prev = STEPS[step - 2], next = STEPS[step];
  return (
    <div className="pager">
      <div>{prev && <Link className="btn ghost sm" href={prev.href}><Icon n="back" s={16} /> {prev.label}</Link>}</div>
      {next ? (
        <div className="nx"><div><small>Next step</small><b>{next.label}</b></div><Link className="btn" href={next.href}>Continue <Icon n="arrow" s={16} /></Link></div>
      ) : (
        <div className="nx"><div><small>That&apos;s the full loop</small><b>Pick → check → target → build → guard → approve → learn</b></div><Link className="btn" href="/">Start again</Link></div>
      )}
    </div>
  );
}
