"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Campaign, type Meta, type Rec, type Recs, type Spec, specOf, ApiError } from "@/lib/api";

interface State {
  meta: Meta | null; metaError: string;
  win: string; setWin: (w: string) => void;
  objective: string; setObjective: (o: string) => void;
  city: string; setCity: (c: string) => void; cat: string; setCat: (c: string) => void;
  recs: Recs | null; recsError: string; reloadRecs: () => void;
  campaigns: Campaign[] | null; campaignsError: string; reloadCampaigns: () => void;
  cur: Spec | null; setCur: (s: Spec | null) => void;
  peek: Rec | null; setPeek: (r: Rec | null) => void;
  theme: "light" | "dark"; toggleTheme: () => void;
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
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [campaignsError, setCampaignsError] = useState("");
  const [cur, setCur] = useState<Spec | null>(null);
  const [peek, setPeek] = useState<Rec | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [msg, setMsg] = useState("");
  const seq = useRef(0), tt = useRef<ReturnType<typeof setTimeout>>(undefined);

  const toast = useCallback((m: string) => { setMsg(m); clearTimeout(tt.current); tt.current = setTimeout(() => setMsg(""), 2800); }, []);

  const reloadCampaigns = useCallback(() => {
    api<Campaign[]>("/api/campaigns").then((c) => { setCampaigns(c); setCampaignsError(""); }).catch((e: ApiError) => setCampaignsError(e.message));
  }, []);

  useEffect(() => {
    // saved preferences live outside React; read them after mount so server and client HTML match
    Promise.resolve().then(() => setTheme((ls.get("theme3") as "light" | "dark") || "light"));
    api<Meta>("/api/meta").then((m) => { setMeta(m); if (!m.windows.diwali) setWinState(Object.keys(m.windows)[0]); })
      .catch((e: ApiError) => setMetaError(e.message));
    reloadCampaigns();
  }, [reloadCampaigns]);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

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
    meta, metaError, win, setWin, objective, setObjective, city, setCity, cat, setCat, recs, recsError, reloadRecs,
    campaigns, campaignsError, reloadCampaigns, cur, setCur, peek, setPeek,
    theme, toggleTheme: () => setTheme((t) => { const n = t === "dark" ? "light" : "dark"; ls.set("theme3", n); return n; }), toast,
  };
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className={`toast ${msg ? "on" : ""}`} role="status">{msg}</div>
    </Ctx.Provider>
  );
}
