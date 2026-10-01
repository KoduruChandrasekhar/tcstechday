"use client";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "./AppState";
import { NAV } from "./nav";
import { Icon } from "./ui";

interface Item { id: string; group: string; label: string; hint?: string; icon: string; run: () => void }

export default function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const { meta, recs, win, setWin, setPeek, toggleTheme, setObjective } = useApp();
  const router = useRouter();
  const [q, setQ] = useState(""), [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open); }
      else if (e.key === "Escape" && open) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 30); }, [open]);

  const items = useMemo<Item[]>(() => {
    const go = (href: string) => () => router.push(href);
    const list: Item[] = NAV.map((s) => ({ id: s.href, group: "Go to", label: s.label, hint: s.hint, icon: s.icon, run: go(s.href) }));
    list.push({ id: "blocked", group: "Go to", label: "Blocked promotions", hint: "What the policy rules stopped, and the fix", icon: "shield", run: go("/promotions/blocked") });
    (recs?.top || []).slice(0, 15).forEach((r, i) => list.push({
      id: r.id, group: "Recommended promotions", label: `${r.offer} on ${r.product}`, hint: `Rank ${i + 1}, ${r.segment} in ${r.city_name}, ${r.fmt.net_gp} extra profit`, icon: "tag",
      run: () => setPeek(r),
    }));
    Object.entries(meta?.windows || {}).forEach(([k, v]) => list.push({ id: "w" + k, group: "Season", label: `Switch to ${v.name}`, hint: k === win ? "Current" : undefined, icon: "clock", run: () => setWin(k) }));
    [["profit", "Most profit"], ["growth", "More sales"], ["clear", "Clear old stock"], ["retain", "Win back customers"]].forEach(([k, l]) =>
      list.push({ id: "g" + k, group: "Rank promotions by", label: l, icon: "chart", run: () => { setObjective(k); router.push("/promotions"); } }));
    list.push({ id: "theme", group: "Settings", label: "Switch light or dark mode", icon: "moon", run: toggleTheme });
    return list;
  }, [meta, recs, win, router, setPeek, setWin, setObjective, toggleTheme]);

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? items.filter((i) => `${i.label} ${i.hint || ""} ${i.group}`.toLowerCase().includes(t)) : items;
  }, [items, q]);
  const pick = (i?: Item) => { if (!i) return; setOpen(false); setQ(""); setSel(0); i.run(); };

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="cmdk-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)}>
          <motion.div className="cmdk" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: -12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }} transition={{ duration: 0.16 }}>
            <div className="cmdk-in"><Icon n="search" s={17} />
              <input ref={input} value={q} placeholder="Search pages, promotions and seasons" onChange={(e) => { setQ(e.target.value); setSel(0); }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(shown.length - 1, s + 1)); }
                  else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
                  else if (e.key === "Enter") pick(shown[sel]);
                }} />
              <kbd>esc</kbd></div>
            <div className="cmdk-list">
              {!shown.length && <div className="cmdk-empty">No results for “{q}”</div>}
              {shown.map((it, i) => {
                const head = i === 0 || shown[i - 1].group !== it.group ? it.group : null;
                return (
                  <div key={it.id}>
                    {head && <div className="cmdk-group">{head}</div>}
                    <button className={`cmdk-item ${i === sel ? "on" : ""}`} onMouseEnter={() => setSel(i)} onClick={() => pick(it)}>
                      <span className="cmdk-ic"><Icon n={it.icon} s={15} /></span>
                      <span className="grow"><span className="cmdk-l">{it.label}</span>{it.hint && <span className="cmdk-h">{it.hint}</span>}</span>
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="cmdk-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>⌘K</kbd> close</span></div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
