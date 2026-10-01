// Thin client for the FastAPI engine (proxied through next.config.ts rewrites).

export type Verdict = "GO" | "CONDITIONAL GO" | "HOLD" | "BLOCK";

export interface Meta {
  today: string;
  segments: Record<string, number>;
  products: { sku: string; name: string; cat: string; price: number }[];
  cities: { code: string; name: string }[];
  offers: string[];
  channels: string[];
  windows: Record<string, { name: string; start: string; end: string }>;
  guardrails: Record<string, number>;
}

export interface Spec {
  segment: string; sku: string; city: string; offer_idx: number; channel: string; cap: number | null; window: string;
}

export interface Rec extends Spec {
  id: string; product: string; category: string; city_name: string; offer: string; sentence: string;
  verdict: Verdict; readiness: number; scores: Record<string, number>;
  reach: number; incr_units: number; promo_units: number; organic_units: number; available: number; stock: number;
  p_stockout: number; stockout_day: number | null; burn: number[]; inbound: { day: number; qty: number }[];
  gp_margin: number; incr_gp: number; net_gp: number; leakage: number; leak_share: number; roi: number;
  cap_load: number; cover_days: number; fest: number; discount_spend: number;
  drivers: string[]; risks: string[]; blocks: string[]; what_would_change: string[];
  fmt: { net_gp: string; leakage: string; discount_spend: string; incr_revenue: string };
  // only on /simulate
  frontier?: { offer: string; net_gp: number; incr_units: number; verdict: Verdict }[];
  history?: { weeks: string[]; units: number[] };
  twins?: { name: string; pred_roi: number; actual_roi: number }[];
  insights?: Record<string, string>;
}

export interface Recs {
  insight: string; insights: Record<string, string>;
  kpis: { candidates: number; net_gp_top: string; counts: Record<Verdict, number> };
  top: Rec[]; blocked: Rec[]; block_reasons: Record<string, number>; gp_by_cat: Record<string, number>;
  opportunities: { type: string; text: string }[];
}

export interface AiResult { source: "ai" | "template"; note?: string; [k: string]: unknown }

export class ApiError extends Error {}

export async function api<T>(url: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(url, body === undefined ? { cache: "no-store" } : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running on port 8765?");
  }
  let j: unknown;
  try { j = await r.json(); } catch { throw new ApiError(`Server error (${r.status})`); }
  if (!r.ok) {
    const d = (j as { detail?: unknown })?.detail;
    throw new ApiError(typeof d === "string" ? d : (d as { msg?: string })?.msg || `Request failed (${r.status})`);
  }
  return j as T;
}

export const specOf = (r: Spec, window: string): Spec => ({
  segment: r.segment, sku: r.sku, city: r.city, offer_idx: r.offer_idx, channel: r.channel, cap: r.cap ?? null, window,
});

export const fin = (x: unknown) => (Number.isFinite(Number(x)) ? Number(x) : 0);

export function inr(v: unknown): string {
  let x = fin(v);
  const s = x < 0 ? "-" : "";
  x = Math.abs(x);
  if (x >= 1e7) return `${s}₹${(x / 1e7).toFixed(2)} Cr`;
  if (x >= 1e5) return `${s}₹${(x / 1e5).toFixed(1)} L`;
  return `${s}₹${Math.round(x).toLocaleString("en-IN")}`;
}
export const num = (v: unknown) => Math.round(fin(v)).toLocaleString("en-IN");
export const pct = (v: unknown, d = 0) => `${(fin(v) * 100).toFixed(d)}%`;

export const VERDICT: Record<string, { label: string; text: string; color: string; tone: string }> = {
  GO: { label: "Go", text: "Makes money, and stock will last the season.", color: "var(--leaf)", tone: "green" },
  CONDITIONAL: { label: "Go with changes", text: "Worth running once the suggested change is made.", color: "var(--amber)", tone: "amber" },
  HOLD: { label: "Hold", text: "Borderline. Try a different discount or city.", color: "var(--muted)", tone: "grey" },
  BLOCK: { label: "Blocked", text: "Breaks a policy rule. The fix is listed below.", color: "var(--sindoor)", tone: "red" },
};
export const vk = (v?: string) => {
  const k = String(v || "HOLD").split(" ")[0];
  return VERDICT[k] ? k : "HOLD";
};

const CAT_NAME: Record<string, string> = {
  TV: "Television", AC: "Air conditioner", REF: "Refrigerator", WM: "Washing machine", AUD: "Audio", LAP: "Laptop",
  KIT: "Kitchen appliance", TAB: "Tablet", PHN: "Phone", ACC: "Accessory", GAM: "Gaming & camera", WEA: "Wearable",
};
export const catName = (cat?: string) => CAT_NAME[String(cat || "").toUpperCase()] || String(cat || "Product");


export interface MapData {
  insight: string;
  rows: { city: string; city_name: string; product: string; status: string; cover_days: number; demand_per_day: number; stock: number }[];
  transfers: { product: string; from: string; to: string; qty: number; from_ll: [number, number]; to_ll: [number, number] }[];
  cities: { city: string; lat: number; lon: number; stores: number; short: number; excess: number }[];
}
export interface CityLight { name: string; lat: number; lon: number; stores: number; short: number; excess: number; demand: number; stock: number; cover: number }

/** Roll SKU rows up to one lamp per city: demand per day, stock, days of cover, and how many products run short. */
export function cityLights(d: MapData): CityLight[] {
  return d.cities.map((c) => {
    const rows = d.rows.filter((r) => r.city_name === c.city);
    const demand = rows.reduce((a, r) => a + fin(r.demand_per_day), 0), stock = rows.reduce((a, r) => a + fin(r.stock), 0);
    return { name: c.city, lat: c.lat, lon: c.lon, stores: c.stores, short: c.short, excess: c.excess, demand, stock, cover: demand ? stock / demand : 0 };
  });
}

export interface Outcome { pred_incr_units: number; actual_incr_units: number; pred_net_gp: number; actual_net_gp: number; stocked_out: boolean; error_pct: number; lesson: string }
export interface Campaign { id: string; rec: Rec; status: string; seals: Record<string, string | null>; log?: string[]; outcome?: Outcome }

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "2026-11-01" -> "1 Nov 2026". Parsed by hand so the server and browser agree whatever the time zone. */
export function day(iso?: string, year = true): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return iso || "";
  return `${+m[3]} ${MONTHS[+m[2] - 1]}${year ? " " + m[1] : ""}`;
}
export const daysBetween = (a: string, b: string) => Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 864e5);

/** Status wording for a season relative to the data date. */
export function seasonStatus(today: string, w: { start: string; end: string }): string {
  const d = daysBetween(today, w.start), e = daysBetween(today, w.end);
  return d > 1 ? `starts in ${d} days` : d === 1 ? "starts tomorrow" : e >= 0 ? "running now" : "ended";
}

/** Download rows as a CSV file. */
export function downloadCSV(name: string, head: string[], rows: (string | number | null | undefined)[][]) {
  const q = (v: unknown) => { const t = String(v ?? ""); return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
  const blob = new Blob(["\ufeff" + [head, ...rows].map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Shortage level for a city, in three plain steps: 0 stock holds, 1 some products short, 2 many short. */
export const shortLevel = (short: number, maxShort: number) => (short <= 0 ? 0 : short < Math.max(2, maxShort * 0.5) ? 1 : 2);
export const SHORT_LABEL = ["Stock holds", "Some products short", "Many products short"];

export const GOALS: [string, string][] = [["profit", "Most profit"], ["growth", "More sales"], ["clear", "Clear old stock"], ["retain", "Win back customers"]];
export const GOAL_LABEL: Record<string, string> = { profit: "most profit", growth: "more sales", clear: "clearing old stock", retain: "winning back customers" };
