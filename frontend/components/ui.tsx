"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { VERDICT, fin, vk } from "@/lib/api";

const P: Record<string, string> = {
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  check: "M20 6 9 17l-5-5", x: "M18 6 6 18M6 6l12 12", minus: "M5 12h14", plus: "M12 5v14M5 12h14",
  box: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96 12 12.01l8.73-5.05M12 22.08V12",
  alert: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z",
  chart: "M3 3v18h18M18 17V9M13 17V5M8 17v-3", search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35",
  home: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
  tag: "M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01",
  sliders: "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6",
  bell: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  refresh: "M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  chevD: "M6 9l6 6 6-6", chevR: "M9 18l6-6-6-6", chevL: "M15 18l-6-6 6-6", chevU: "M18 15l-6-6-6 6",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
  external: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3",
  send: "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z",
  bookmark: "M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z",
  rotate: "M1 4v6h6M3.51 15a9 9 0 1 0 2.13-9.36L1 10",
  doc: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8",
  msg: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  truck: "M1 3h15v13H1zM16 8h4l3 3v5h-7zM5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  copy: "M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
};
export function Icon({ n, s = 18, w = 2 }: { n: string; s?: number; w?: number }) {
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={P[n] || ""} />
    </svg>
  );
}

/** The product mark: an anvil-cut tag. */
export const Mark = ({ s = 26 }: { s?: number }) => (
  <svg width={s} height={s} viewBox="0 0 32 32" aria-hidden>
    <path d="M4 9.5 15 4h13v13L17.5 28 4 14.5z" fill="var(--marigold)" />
    <path d="M4 14.5 17.5 28 28 17V12L17.5 22.5 4 9.5z" fill="#000" fillOpacity=".18" />
    <circle cx="22.5" cy="9.5" r="2.4" fill="var(--brand)" />
  </svg>
);

export const Verdict = ({ v }: { v: string }) => { const V = VERDICT[vk(v)]; return <span className={`badge ${V.tone}`}><i />{V.label}</span>; };

const STATUS: Record<string, [string, string]> = {
  "Pending sign-off": ["Waiting", "amber"], Approved: ["Approved", "violet"], Completed: ["Completed", "green"], Rejected: ["Rejected", "red"],
};
export const Status = ({ s }: { s: string }) => { const [l, t] = STATUS[s] || [s, "grey"]; return <span className={`badge ${t}`}><i />{l}</span>; };

export function PageHeader({ title, sub, actions, tabs }: { title: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode; tabs?: { href: string; label: string; count?: number }[] }) {
  const path = usePathname();
  return (
    <header className={`ph ${tabs ? "has-tabs" : ""}`}>
      <div className="ph-row">
        <div className="ph-text"><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
        {actions && <div className="ph-actions">{actions}</div>}
      </div>
      {tabs && (
        <nav className="tabs" aria-label="Sections">
          {tabs.map((t) => <Link key={t.href} href={t.href} aria-current={path === t.href ? "page" : undefined}>{t.label}{t.count !== undefined && <span className="count">{t.count}</span>}</Link>)}
        </nav>
      )}
    </header>
  );
}

export function Panel({ title, sub, actions, children, className = "", flush, id }: { title?: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string; flush?: boolean; id?: string }) {
  return (
    <section className={`panel ${className}`} id={id}>
      {(title || actions) && (
        <div className="panel-h">
          <div>{title && <h2>{title}</h2>}{sub && <p>{sub}</p>}</div>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      <div className={flush ? "panel-flush" : "panel-b"}>{children}</div>
    </section>
  );
}

export function Seg<T extends string>({ value, set, opts, label }: { value: T; set: (v: T) => void; opts: [T, React.ReactNode][]; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {opts.map(([v, l]) => <button key={v} className={value === v ? "on" : ""} aria-pressed={value === v} onClick={() => set(v)}>{l}</button>)}
    </div>
  );
}

export interface Col<T> { key: string; label: React.ReactNode; render: (r: T, i: number) => React.ReactNode; sort?: (r: T) => number | string; num?: boolean; hide?: "md" | "sm"; w?: number | string }

/** Sortable, paged table. Rows open with click or Enter. */
export function DataTable<T>({ rows, cols, rowKey, onRow, initial, pageSize = 0, empty = "Nothing to show.", isOn, label }: {
  rows: T[]; cols: Col<T>[]; rowKey: (r: T) => string; onRow?: (r: T) => void; initial?: [string, "asc" | "desc"];
  pageSize?: number; empty?: React.ReactNode; isOn?: (r: T) => boolean; label: string;
}) {
  const [sort, setSort] = useState<[string, "asc" | "desc"] | null>(initial || null);
  const [page, setPage] = useState(0);
  const sorted = useMemo(() => {
    const c = sort && cols.find((x) => x.key === sort[0]);
    if (!c?.sort) return rows;
    const m = sort![1] === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => { const x = c.sort!(a), y = c.sort!(b); return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * m; });
  }, [rows, cols, sort]);
  const pages = pageSize ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1, p = Math.min(page, pages - 1);
  const shown = pageSize ? sorted.slice(p * pageSize, (p + 1) * pageSize) : sorted;
  const flip = (c: Col<T>) => { setPage(0); setSort((s) => (s?.[0] === c.key ? [c.key, s[1] === "asc" ? "desc" : "asc"] : [c.key, c.num ? "desc" : "asc"])); };

  return (
    <div className="dt">
      <div className="dt-scroll">
        <table aria-label={label}>
          <thead><tr>{cols.map((c) => (
            <th key={c.key} className={`${c.num ? "r" : ""} ${c.hide ? "hide-" + c.hide : ""}`} style={{ width: c.w }} aria-sort={sort?.[0] === c.key ? (sort[1] === "asc" ? "ascending" : "descending") : undefined}>
              {c.sort ? <button onClick={() => flip(c)}>{c.label}<Icon n={sort?.[0] === c.key ? (sort[1] === "asc" ? "chevU" : "chevD") : "chevD"} s={12} /></button> : c.label}
            </th>))}</tr></thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={rowKey(r)} className={`${onRow ? "click" : ""} ${isOn?.(r) ? "on" : ""}`} tabIndex={onRow ? 0 : undefined}
                onClick={onRow ? () => onRow(r) : undefined} onKeyDown={onRow ? (e) => { if (e.key === "Enter") onRow(r); } : undefined}>
                {cols.map((c) => <td key={c.key} className={`${c.num ? "r num" : ""} ${c.hide ? "hide-" + c.hide : ""}`}>{c.render(r, p * pageSize + i)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="dt-empty">{empty}</div>}
      </div>
      {pageSize > 0 && sorted.length > pageSize && (
        <div className="dt-foot">
          <span>{p * pageSize + 1} to {Math.min(sorted.length, (p + 1) * pageSize)} of {sorted.length}</span>
          <span className="dt-pages">
            <button className="icon-btn" disabled={p === 0} onClick={() => setPage(p - 1)} aria-label="Previous page"><Icon n="chevL" s={16} /></button>
            <button className="icon-btn" disabled={p >= pages - 1} onClick={() => setPage(p + 1)} aria-label="Next page"><Icon n="chevR" s={16} /></button>
          </span>
        </div>
      )}
    </div>
  );
}

export function Meter({ v, tone }: { v: number; tone?: string }) {
  const c = tone || (v >= 70 ? "var(--leaf)" : v >= 40 ? "var(--amber)" : "var(--sindoor)");
  return <span className="meter" style={{ ["--c" as string]: c }}><i style={{ width: `${Math.max(3, Math.min(100, fin(v)))}%` }} /></span>;
}

export function HBar({ label, right, pct, color, hl }: { label: React.ReactNode; right: React.ReactNode; pct: number; color?: string; hl?: boolean }) {
  return (
    <div className={`hbar ${hl ? "hl" : ""}`}>
      <div className="hbar-l"><span>{label}</span><span className="num">{right}</span></div>
      <div className="hbar-t"><i style={{ width: `${Math.max(1.5, Math.min(100, fin(pct)))}%`, background: color }} /></div>
    </div>
  );
}

export const ErrorBox = ({ msg, retry }: { msg: string; retry?: () => void }) => (
  <div className="error" role="alert"><Icon n="alert" s={16} /><span>{msg}</span>{retry && <button className="btn sm" onClick={retry}>Try again</button>}</div>
);

export const Skeleton = ({ lines = 3, h }: { lines?: number; h?: number }) => (
  <div className="skel-wrap" aria-busy="true" aria-label="Loading">{h ? <div className="skel" style={{ height: h }} /> : Array.from({ length: lines }, (_, i) => <div key={i} className="skel" style={{ width: `${92 - i * 13}%` }} />)}</div>
);

export const Empty = ({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) => (
  <div className="empty"><b>{title}</b>{children && <p>{children}</p>}{action}</div>
);

/** Types text in progressively. Only used to reveal text the user just asked for. */
export function TypeIn({ text }: { text: string }) {
  const [st, setSt] = useState({ t: "", n: 0 });
  const still = typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    if (still) return;
    const id = setInterval(() => setSt((s) => {
      const n = s.t === text ? s.n + 4 : 4;
      if (n >= text.length) clearInterval(id);
      return { t: text, n };
    }), 12);
    return () => clearInterval(id);
  }, [text, still]);
  const n = still ? text.length : st.t === text ? st.n : 0;
  return <span className={n < text.length ? "caret" : ""}>{text.slice(0, n)}</span>;
}

/** Slide-over panel from the right edge. Esc or the backdrop closes it; focus returns to where it was. */
export function Drawer({ open, onClose, title, sub, children, footer, wide }: { open: boolean; onClose: () => void; title: React.ReactNode; sub?: React.ReactNode; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  const box = useRef<HTMLDivElement>(null), back = useRef<Element | null>(null);
  useEffect(() => {
    if (!open) return;
    back.current = document.activeElement;
    const t = setTimeout(() => box.current?.querySelector<HTMLElement>("button, a, input, select, textarea")?.focus(), 60);
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    document.body.classList.add("locked");
    return () => { clearTimeout(t); window.removeEventListener("keydown", key); document.body.classList.remove("locked"); (back.current as HTMLElement | null)?.focus?.(); };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="drawer-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} onClick={onClose}>
          <motion.aside ref={box} className={`drawer ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "Details"} onClick={(e) => e.stopPropagation()}
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 420, damping: 42 }}>
            <header className="drawer-h">
              <div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
              <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon n="x" s={18} /></button>
            </header>
            <div className="drawer-b">{children}</div>
            {footer && <footer className="drawer-f">{footer}</footer>}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
