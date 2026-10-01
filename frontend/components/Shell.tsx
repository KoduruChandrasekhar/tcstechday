"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApp } from "./AppState";
import CommandPalette from "./CommandPalette";
import PromoDrawer from "./PromoDrawer";
import { NAV, navFor } from "./nav";
import { Icon, Mark } from "./ui";
import { api, day, seasonStatus } from "@/lib/api";

/** A button that opens a small anchored menu; closes on outside click or Esc. */
function Pop({ label, button, children, className = "" }: { label: string; button: React.ReactNode; children: (close: () => void) => React.ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", off); document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", off); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div className={`pop ${className}`} ref={ref}>
      <button className="top-btn" aria-label={label} aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((o) => !o)}>{button}</button>
      {open && <div className="pop-menu" role="menu">{children(() => setOpen(false))}</div>}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { meta, metaError, win, setWin, theme, toggleTheme, campaigns, reloadCampaigns, toast } = useApp();
  const path = usePathname(), router = useRouter();
  const [palette, setPalette] = useState(false);
  const here = navFor(path);
  const nav = useRef<HTMLElement>(null);

  useEffect(() => { document.title = here && here.href !== "/" ? `${here.label} | PromoForge` : "PromoForge | Prometheus Retail"; }, [here]);
  // keep the current section visible in the nav strip on narrow screens, without scrolling the page
  useEffect(() => {
    const n = nav.current, a = n?.querySelector<HTMLElement>("[aria-current]");
    if (n && a && (a.offsetLeft < n.scrollLeft || a.offsetLeft + a.offsetWidth > n.scrollLeft + n.clientWidth)) n.scrollLeft = a.offsetLeft - 16;
  }, [path]);

  const waiting = (campaigns || []).filter((c) => c.status === "Pending sign-off");
  const ready = (campaigns || []).filter((c) => c.status === "Approved");
  const w = meta?.windows[win];

  const reset = async () => {
    if (!confirm("Delete every promotion sent for approval and its history? The planning data itself is not affected.")) return;
    try { await api("/api/admin/reset-demo", {}); reloadCampaigns(); toast("Approval history cleared"); } catch { toast("Couldn't clear the approval history"); }
  };

  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <header className="top">
        <div className="top-in">
          <Link href="/" className="brand" aria-label="PromoForge overview"><Mark /><span><b>PromoForge</b><small>Prometheus Retail</small></span></Link>
          <nav className="nav" ref={nav} aria-label="Main">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={here?.href === n.href ? "page" : undefined}>
                {n.label}{n.href === "/approvals" && waiting.length > 0 && <span className="dot-count" aria-label={`${waiting.length} waiting`}>{waiting.length}</span>}
              </Link>
            ))}
          </nav>
          <div className="top-tools">
            <label className="season" title="Planning season">
              <Icon n="clock" s={15} />
              <select value={win} onChange={(e) => setWin(e.target.value)} aria-label="Planning season">
                {meta ? Object.entries(meta.windows).map(([k, v]) => <option key={k} value={k}>{v.name}</option>) : <option>Loading seasons</option>}
              </select>
              {meta && w && <span className="season-when">{seasonStatus(meta.today, w)}</span>}
            </label>
            <button className="top-btn search" onClick={() => setPalette(true)} aria-label="Search (Ctrl or Cmd + K)"><Icon n="search" s={16} /><span>Search</span><kbd>⌘K</kbd></button>
            <Pop label={`Notifications, ${waiting.length + ready.length} need action`} button={<><Icon n="bell" s={17} />{waiting.length + ready.length > 0 && <span className="bell-dot" />}</>}>
              {(close) => <>
                <div className="pop-head">Needs action</div>
                {!waiting.length && !ready.length && <p className="pop-empty">Nothing is waiting on you.</p>}
                {waiting.map((c) => <button key={c.id} role="menuitem" onClick={() => { close(); router.push(`/approvals?c=${c.id}`); }}><b>{c.id} waiting for sign-off</b><span>{c.rec.offer} on {c.rec.product}, {c.rec.city_name}</span></button>)}
                {ready.map((c) => <button key={c.id} role="menuitem" onClick={() => { close(); router.push(`/approvals?c=${c.id}`); }}><b>{c.id} approved, ready to run</b><span>{c.rec.offer} on {c.rec.product}, {c.rec.city_name}</span></button>)}
              </>}
            </Pop>
            <button className="top-btn theme" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} title={theme === "dark" ? "Light mode" : "Dark mode"}><Icon n={theme === "dark" ? "sun" : "moon"} s={17} /></button>
            <Pop label="Workspace menu" className="acct" button={<span className="avatar">PR</span>}>
              {(close) => <>
                <div className="pop-head">Prometheus Retail<small>Planning workspace</small></div>
                <button role="menuitem" onClick={() => { close(); setPalette(true); }}><b>Search and shortcuts</b><span>Press ⌘K anywhere</span></button>
                <button role="menuitem" onClick={() => { close(); toggleTheme(); }}><b>{theme === "dark" ? "Light mode" : "Dark mode"}</b></button>
                <button role="menuitem" onClick={() => { close(); reset(); }}><b>Clear approval history</b><span>Removes promotions sent for sign-off</span></button>
              </>}
            </Pop>
          </div>
        </div>
      </header>

      <div id="main" className="app">{children}</div>

      <footer className="foot">
        <div className="foot-in">
          <span className={`conn ${metaError ? "down" : meta ? "up" : ""}`}><i />{metaError ? "Planning engine offline" : meta ? "Planning engine connected" : "Connecting"}</span>
          {meta && <span>Data up to {day(meta.today)}</span>}
          {meta && <span>{meta.cities.length} cities, {meta.products.length} products, {Object.keys(meta.segments).length} customer groups</span>}
          <span className="foot-r">PromoForge for Prometheus Retail</span>
        </div>
      </footer>

      <CommandPalette open={palette} setOpen={setPalette} />
      <PromoDrawer />
    </>
  );
}
