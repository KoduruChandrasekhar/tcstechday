"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Meta, type Recs, type Spec, specOf, ApiError } from "@/lib/api";

interface State {
  meta: Meta | null; metaError: string;
  win: string; setWin: (w: string) => void;
  objective: string; setObjective: (o: string) => void;
  city: string; setCity: (c: string) => void; cat: string; setCat: (c: string) => void;
  recs: Recs | null; recsError: string; reloadRecs: () => void;
  cur: Spec | null; setCur: (s: Spec | null) => void;
  theme: "light" | "dark"; toggleTheme: () => void;
  tips: boolean; toggleTips: () => void;
  toast: (m: string) => void;
}
const Ctx = createContext<State | null>(null);
export const useApp = () => useContext(Ctx)!;

const ls = { get: (k: string) => { try { return localStorage.getItem("pf." + k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem("pf." + k, v); } catch {} } };

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState("");
  const [win, setWinState] = useState("diwali");
  const [objective, setObjective] = useState("profit");
  const [city, setCity] = useState("");
  const [cat, setCat] = useState("");
  const [recs, setRecs] = useState<Recs | null>(null);
  const [recsError, setRecsError] = useState("");
  const [cur, setCur] = useState<Spec | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [tips, setTips] = useState(true);
  const [msg, setMsg] = useState("");
  const seq = useRef(0), tt = useRef<ReturnType<typeof setTimeout>>(undefined);

  const toast = useCallback((m: string) => { setMsg(m); clearTimeout(tt.current); tt.current = setTimeout(() => setMsg(""), 2600); }, []);

  useEffect(() => {
    // saved preferences live outside React; read them after mount so server and client HTML match
    Promise.resolve().then(() => {
      setTheme((ls.get("theme2") as "light" | "dark") || "light");
      setTips(ls.get("tips") !== "0");
    });
    api<Meta>("/api/meta").then((m) => { setMeta(m); if (!m.windows.diwali) setWinState(Object.keys(m.windows)[0]); })
      .catch((e: ApiError) => setMetaError(e.message));
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => { document.body.classList.toggle("no-tips", !tips); }, [tips]);

  const reloadRecs = useCallback(() => {
    if (!meta) return;
    const q = new URLSearchParams({ objective, window: win });
    if (city) q.set("city", city);
    if (cat) q.set("category", cat);
    const n = ++seq.current;
    api<Recs>("/api/recommendations?" + q).then((d) => {
      if (n !== seq.current) return;
      d.top ||= []; d.blocked ||= []; d.opportunities ||= [];
      setRecs(d); setRecsError("");
      setCur((c) => c ?? (d.top[0] ? specOf(d.top[0], win) : null));
    }).catch((e: ApiError) => n === seq.current && setRecsError(e.message));
  }, [meta, objective, win, city, cat]);
  useEffect(() => { reloadRecs(); }, [reloadRecs]);

  const setWin = (w: string) => { setWinState(w); setCur(null); };
  const value: State = {
    meta, metaError, win, setWin, objective, setObjective, city, setCity, cat, setCat, recs, recsError, reloadRecs, cur, setCur,
    theme, toggleTheme: () => setTheme((t) => { const n = t === "dark" ? "light" : "dark"; ls.set("theme2", n); return n; }),
    tips, toggleTips: () => setTips((t) => { ls.set("tips", t ? "0" : "1"); return !t; }), toast,
  };
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className={`toast ${msg ? "on" : ""}`} role="status">{msg}</div>
    </Ctx.Provider>
  );
}
