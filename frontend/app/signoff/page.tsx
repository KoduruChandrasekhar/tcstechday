"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useApp } from "@/components/AppState";
import { Confetti } from "@/components/fx";
import { ErrorBox, Icon, PageHead, Pager } from "@/components/ui";
import { api, inr, num, type Rec, ApiError } from "@/lib/api";

interface Outcome { pred_incr_units: number; actual_incr_units: number; pred_net_gp: number; actual_net_gp: number; stocked_out: boolean; error_pct: number; lesson: string }
interface Campaign { id: string; rec: Rec; status: string; seals: Record<string, string | null>; outcome?: Outcome }

const TEAMS: [string, string, string, string, (r: Rec) => string[]][] = [
  ["marketing", "Marketing", "chat", "Customers & messaging", (r) => [`Reaches ${num(r.reach)} customers by ${r.channel}`, `${num(r.incr_units)} extra units sold`, `${(r.leak_share * 100).toFixed(0)}% of the discount wasted`]],
  ["merchandising", "Merchandising", "rupee", "Profit & margin", (r) => [`Extra profit ${r.fmt.net_gp}`, `Margin after discount ${(r.gp_margin * 100).toFixed(1)}%`, `Total discount given ${r.fmt.discount_spend}`]],
  ["store_ops", "Store Ops", "store", "Stock & staff", (r) => [`${num(r.available)} in stock vs ${num(r.organic_units + r.promo_units)} needed`, `${(r.p_stockout * 100).toFixed(0)}% chance of selling out${r.stockout_day ? ` (day ${r.stockout_day})` : ""}`, `Installation teams ${(r.cap_load * 100).toFixed(0)}% busy`]],
];
const Vs = ({ label, a, b, f, bad }: { label: string; a: number; b: number; f: (x: number) => string; bad?: boolean }) => {
  const m = Math.max(Math.abs(a), Math.abs(b), 1);
  return <div className="card"><div className="small muted" style={{ marginBottom: 8 }}>{label}</div>
    <div className="r"><span>Expected</span><div className="tr"><i style={{ width: `${(Math.abs(a) / m) * 100}%`, background: "var(--muted)" }} /></div><b>{f(a)}</b></div>
    <div className="r"><span>Actual</span><div className="tr"><i style={{ width: `${(Math.abs(b) / m) * 100}%`, background: bad ? "var(--bad)" : "var(--accent)" }} /></div><b>{f(b)}</b></div></div>;
};

export default function SignOff() {
  const { toast } = useApp();
  const [party, setParty] = useState(0);
  const [cs, setCs] = useState<Campaign[] | null>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false), [sim, setSim] = useState<{ id: string; day: number } | null>(null);
  const load = useCallback(() => { api<Campaign[]>("/api/campaigns").then((x) => { setCs(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); }, []);
  useEffect(load, [load]);

  const seal = async (id: string, lens: string, decision: string) => {
    if (busy) return; setBusy(true);
    try { const c = await api<Campaign>(`/api/campaigns/${id}/seal`, { lens, decision }); if (c.status === "Approved") { setParty((p) => p + 1); toast("All three teams approved 🎉"); } } catch (e) { toast((e as ApiError).message); }
    setBusy(false); load();
  };
  const warp = async (id: string) => {
    if (busy) return; setBusy(true); setSim({ id, day: 0 });
    const req = api(`/api/campaigns/${id}/timewarp`, {});
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) for (let d = 1; d <= 8; d++) { await new Promise((r) => setTimeout(r, 230)); setSim({ id, day: d }); }
    try { await req; } catch (e) { toast((e as ApiError).message); }
    setSim(null); setBusy(false); load();
  };

  return (
    <main>
      <PageHead step={6} title="Team sign-off, then see what happens" lead="Marketing, Merchandising and Store Ops each check what matters to them. When all three approve, we fast-forward through the season and compare what we expected with what really happened."
        tips={[["Each team reviews", "only the numbers they care about."], ["All three approve", "one “no” stops it."], ["Fast-forward", "see the real result."]]} />
      {err && <ErrorBox msg={err} retry={load} />}
      {cs && !cs.length && <div className="card empty"><b>Nothing waiting for sign-off</b>Build a promotion in step 4 and send it here.<div style={{ marginTop: 14 }}><Link className="btn" href="/build">Build a promotion <Icon n="arrow" s={16} /></Link></div></div>}
      {!cs && !err && <div className="card"><div className="skel" /></div>}
      {cs?.slice().reverse().map((c) => {
        const r = c.rec, o = c.outcome, stage = c.status === "Completed" ? 4 : c.status === "Approved" ? 2 : c.status === "Rejected" ? 0 : 1;
        return (
          <div key={c.id} className="card" style={{ marginBottom: 18 }}>
            <div className="row between"><div className="row"><b style={{ fontSize: "1.05rem" }}>Promotion {c.id}</b>
              <span className={`pill ${c.status === "Rejected" ? "p-BLOCK" : c.status === "Pending sign-off" ? "p-CONDITIONAL" : "p-GO"}`}>{c.status === "Pending sign-off" ? "Waiting for sign-off" : c.status}</span></div>
              <span className="small muted">Confidence {Math.round(r.readiness)}/100</span></div>
            <p style={{ margin: "10px 0 0" }}>{r.sentence}</p>
            <div className="flow">{["Sent", "Teams approve", "Fast-forward", "Learn"].map((t, i) => <span key={t} className={i < stage ? "d" : i === stage && c.status !== "Rejected" ? "c" : ""}>{i + 1}. {t}</span>)}</div>
            <div className="teams">{TEAMS.map(([k, n, ic, d, f], i) => (
              <div key={k} className={`team rise ${c.seals[k] === "approve" ? "ok" : c.seals[k] === "reject" ? "no" : ""}`} style={{ animationDelay: `${i * 60}ms` }}>
                <div className="row"><span className="ic" style={{ width: 34, height: 34, borderRadius: 10, border: "1px solid var(--border)", display: "grid", placeItems: "center", color: "var(--accent)", background: "var(--surface)" }}><Icon n={ic} s={17} /></span><div><b>{n}</b><div className="small muted">{d}</div></div></div>
                <ul>{f(r).map((x) => <li key={x}>{x}</li>)}</ul>
                <div className="row">{c.seals[k] ? <b style={{ color: c.seals[k] === "approve" ? "var(--good)" : "var(--bad)" }}>{c.seals[k] === "approve" ? "✓ Approved" : "✕ Rejected"}</b>
                  : c.status === "Rejected" ? <span className="small muted">Not needed</span>
                  : <><button className="btn good sm" disabled={busy} onClick={() => seal(c.id, k, "approve")}><Icon n="check" s={15} /> Approve</button><button className="btn bad sm" disabled={busy} onClick={() => seal(c.id, k, "reject")}>Reject</button></>}</div>
              </div>))}</div>
            {c.status === "Approved" && (sim?.id === c.id
              ? <div className="sim"><b>Fast-forwarding through the season…</b><div className="small muted">Day {Math.max(1, sim.day)} of 8</div><div className="simdays">{Array.from({ length: 8 }, (_, i) => <i key={i} className={i < sim.day ? "on" : ""} />)}</div><div className="small muted">Customers receive the offer, stores sell, stock moves. Then we compare with the forecast.</div></div>
              : <div className="sendbar celebrate"><div><b>🎉 All three teams approved</b><div className="small muted">Fast-forward through the season in our simulated store network to see the real result.</div></div><button className="btn" disabled={busy} onClick={() => warp(c.id)}><Icon n="ff" s={16} /> Fast-forward</button></div>)}
            {o && <div style={{ marginTop: 18, borderTop: "1px solid var(--border)", paddingTop: 18 }}><h2>What actually happened</h2>
              <div className="vs"><Vs label="Extra units sold" a={o.pred_incr_units} b={o.actual_incr_units} f={num} /><Vs label="Extra profit" a={o.pred_net_gp} b={o.actual_net_gp} f={inr} bad={o.actual_net_gp < 0} />
                <div className="card"><div className="small muted" style={{ marginBottom: 8 }}>Did we sell out?</div><div style={{ fontSize: "1.5rem", fontWeight: 700, color: o.stocked_out ? "var(--bad)" : "var(--good)" }}>{o.stocked_out ? "Yes" : "No"}</div><div className="small muted">Sales were {Math.abs(o.error_pct)}% {o.error_pct < 0 ? "below" : "above"} forecast</div></div></div>
              <div className="learn"><Icon n="bulb" /><div><b>What we learned:</b> {o.lesson}</div></div>
              <Link className="btn ghost sm" href="/results" style={{ marginTop: 12 }}>See past results <Icon n="arrow" s={15} /></Link></div>}
          </div>);
      })}
      <Confetti fire={party} />
      <Pager step={6} />
    </main>
  );
}
