"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "./AppState";
import { STEPS } from "./steps";
import { Icon } from "./ui";

export default function Header() {
  const { meta, win, setWin, theme, toggleTheme, tips, toggleTips } = useApp();
  const path = usePathname();
  const idx = STEPS.findIndex((s) => s.href === path);
  const w = meta?.windows[win];
  let countdown = "";
  if (meta && w) {
    const d = Math.round((+new Date(w.start) - +new Date(meta.today)) / 864e5), e = Math.round((+new Date(w.end) - +new Date(meta.today)) / 864e5);
    countdown = d > 0 ? `${d} day${d > 1 ? "s" : ""} to ${w.name}` : e >= 0 ? `${w.name} is live now` : `${w.name} ended`;
  }
  return (
    <header className="hdr">
      <div className="hdr-row">
        <Link href="/" className="brand">
          <span className="mk"><Icon n="logo" /></span>
          <div><b>Prometheus PromoForge</b><span>Plan festival promotions that make money and don&apos;t run out of stock</span></div>
        </Link>
        <div className="hdr-right">
          {countdown && <span className="count"><Icon n="cal" s={14} />{countdown}</span>}
          <span>Season</span>
          <select className="pick" value={win} onChange={(e) => setWin(e.target.value)} aria-label="Season">
            {meta ? Object.entries(meta.windows).map(([k, v]) => <option key={k} value={k}>{v.name}</option>) : <option>Loading…</option>}
          </select>
          <button className={`tbtn ${tips ? "on" : ""}`} onClick={toggleTips}>Help tips {tips ? "on" : "off"}</button>
          <button className="tbtn" onClick={toggleTheme} aria-label="Switch light or dark mode">
            <Icon n={theme === "dark" ? "sun" : "moon"} s={16} />{theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </div>
      <nav className="stepper" aria-label="Steps">
        {STEPS.map((s, i) => (
          <Link key={s.href} href={s.href} className={`st ${i === idx ? "on" : i < idx ? "done" : ""}`} aria-current={i === idx ? "page" : undefined}>
            <span className="n">{i + 1}</span>{s.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
