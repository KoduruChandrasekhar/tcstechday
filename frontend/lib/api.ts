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

export const VERDICT: Record<string, { label: string; text: string; color: string }> = {
  GO: { label: "Go", text: "Run it. It makes money and stock will last.", color: "var(--good)" },
  CONDITIONAL: { label: "Go, with a change", text: "Run it with the change suggested below.", color: "var(--warn)" },
  HOLD: { label: "Wait", text: "The numbers are borderline. Try a different offer or city.", color: "var(--muted)" },
  BLOCK: { label: "Don't run", text: "It breaks a safety rule. See the fix below.", color: "var(--bad)" },
};
export const vk = (v?: string) => {
  const k = String(v || "HOLD").split(" ")[0];
  return VERDICT[k] ? k : "HOLD";
};
