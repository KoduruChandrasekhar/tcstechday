"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useApp } from "./AppState";
import CommandPalette from "./CommandPalette";
import { STEPS } from "./steps";
import { Icon } from "./ui";
import { winEmoji } from "@/lib/api";

export default function Shell({ children }: { children: React.ReactNode }) {
  const { meta, win, setWin, theme, toggleTheme, tips, toggleTips } = useApp();
  const path = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const tabs = useRef<HTMLDivElement>(null);
  const idx = STEPS.findIndex((s) => s.href === path);
  const step = STEPS[idx];

  // keep the active tab visible when the tab strip scrolls (narrow screens)
  useEffect(() => { tabs.current?.querySelector(".tab.on")?.scrollIntoView({ block: "nearest", inline: "center" }); }, [path]);

  const w = meta?.windows[win];
  let countdown = "";
  if (meta && w) {
    const d = Math.round((+new Date(w.start) - +new Date(meta.today)) / 864e5), e = Math.round((+new Date(w.end) - +new Date(meta.today)) / 864e5);
    countdown = d > 0 ? `${d} day${d > 1 ? "s" : ""} to go` : e >= 0 ? "Live now" : "Ended";
  }

  return (
    <>
      <header className="nav">
        <div className="nav-row">
          <Link href="/" className="nav-brand">
            <span className="mk"><Icon n="logo" s={17} /></span>
            <span className="nav-brand-t"><b>PromoForge</b><small>Prometheus Retail</small></span>
          </Link>

          <nav className="tabs" ref={tabs} aria-label="Steps">
            {STEPS.map((s, i) => {
              const on = i === idx;
              return (
                <Link key={s.href} href={s.href} className={`tab ${on ? "on" : ""} ${i < idx ? "done" : ""}`} aria-current={on ? "page" : undefined} title={`Step ${i + 1}: ${s.hint}`}>
                  {on && <motion.span layoutId="tab-active" className="tab-pill" transition={{ type: "spring", stiffness: 500, damping: 38 }} />}
                  <span className="tab-n">{i < idx ? <Icon n="check" s={11} /> : i + 1}</span>
                  <span className="tab-t">{s.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="nav-tools">
            <button className="nav-search" onClick={() => setPaletteOpen(true)} aria-label="Search">
              <Icon n="search" s={15} /><span>Search</span><kbd>⌘K</kbd>
            </button>
            <button className={`icon-btn ${tips ? "on" : ""}`} onClick={toggleTips} aria-pressed={tips} title={tips ? "Hide help tips" : "Show help tips"}><Icon n="help" s={16} /></button>
            <button className="icon-btn" onClick={toggleTheme} aria-label="Switch light or dark mode" title={theme === "dark" ? "Light mode" : "Dark mode"}><Icon n={theme === "dark" ? "sun" : "moon"} s={16} /></button>
          </div>
        </div>

        <div className="subbar">
          <div className="crumbs">
            <span className="muted">Journey</span><span className="sep">/</span><b>{step ? step.label : "PromoForge"}</b>
            {step && <span className="muted small hide-sm">· {step.hint}</span>}
          </div>
          <div className="sub-right">
            {w && <span className="count fest">{winEmoji(win)} {w.name} · {countdown}</span>}
            <label className="season"><Icon n="cal" s={14} />
              <select value={win} onChange={(e) => setWin(e.target.value)} aria-label="Season">
                {meta ? Object.entries(meta.windows).map(([k, v]) => <option key={k} value={k}>{v.name}</option>) : <option>Loading…</option>}
              </select>
            </label>
          </div>
          <div className="progress"><motion.i animate={{ width: `${((idx + 1) / STEPS.length) * 100}%` }} transition={{ type: "spring", stiffness: 120, damping: 22 }} /></div>
        </div>
      </header>
      {children}
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />
    </>
  );
}
