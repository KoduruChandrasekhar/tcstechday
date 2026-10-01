"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useApp } from "@/components/AppState";
import { Empty, ErrorBox, HBar, Icon, PageHeader, Panel, Seg, Skeleton, Status } from "@/components/ui";
import { api, inr, num, type Campaign, type Rec, ApiError } from "@/lib/api";

const TEAMS: [string, string, string, (r: Rec) => string[]][] = [
  ["marketing", "Marketing", "Customers and messages", (r) => [`Reaches ${num(r.reach)} customers by ${r.channel}`, `${num(r.incr_units)} extra units sold`, `${(r.leak_share * 100).toFixed(0)}% of the discount wasted`]],
  ["merchandising", "Merchandising", "Profit and margin", (r) => [`${r.fmt.net_gp} extra profit`, `${(r.gp_margin * 100).toFixed(1)}% margin after the discount`, `${r.fmt.discount_spend} given in discounts`]],
  ["store_ops", "Store Ops", "Stock and staff", (r) => [`${num(r.available)} in stock, ${num(r.organic_units + r.promo_units)} needed`, `${(r.p_stockout * 100).toFixed(0)}% chance of selling out${r.stockout_day ? `, on day ${r.stockout_day}` : ""}`, `Installation teams ${(r.cap_load * 100).toFixed(0)}% booked`]],
];
const STAGES = ["Sent", "Team reviews", "Approved", "Season result"];
type Filter = "all" | "Pending sign-off" | "Approved" | "Completed" | "Rejected";
const FILTERS: [Filter, string][] = [["all", "All"], ["Pending sign-off", "Waiting"], ["Approved", "Approved"], ["Completed", "Completed"], ["Rejected", "Rejected"]];
const TEAM_NAME: Record<string, string> = { marketing: "Marketing", merchandising: "Merchandising", store_ops: "Store Ops" };

function actionText(a: string) {
  if (a === "created") return "Sent for approval";
  if (a === "timewarp") return "Season simulated";
  const [lens, d] = a.split(" ");
  return TEAM_NAME[lens] ? `${TEAM_NAME[lens]} ${d === "approve" ? "approved" : "rejected"}` : a;
}
const when = (iso: string) => { const t = new Date(iso); return isNaN(+t) ? iso : t.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); };

function Detail({ c, onChange }: { c: Campaign; onChange: () => void }) {
  const { toast } = useApp();
  const [busy, setBusy] = useState(false), [sim, setSim] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [log, setLog] = useState<{ action: string; detail: string; created_at: string }[] | null>(null);
  const r = c.rec, o = c.outcome;
  const loadLog = useCallback(() => { api<typeof log>(`/api/campaigns/${c.id}/audit`).then(setLog).catch(() => setLog([])); }, [c.id]);
  useEffect(loadLog, [loadLog, c.status, c.seals]);

  const seal = async (lens: string, decision: string) => {
    if (busy) return; setBusy(true);
    try {
      const n = await api<Campaign>(`/api/campaigns/${c.id}/seal`, { lens, decision, note: notes[lens] || "" });
      toast(n.status === "Approved" ? `${c.id} approved by all three teams` : n.status === "Rejected" ? `${c.id} rejected. It won't run.` : `${TEAM_NAME[lens]} ${decision === "approve" ? "approved" : "rejected"}`);
    } catch (e) { toast((e as ApiError).message); }
    setBusy(false); onChange();
  };
  const simulate = async () => {
    if (busy) return; setBusy(true); setSim(0);
    const req = api(`/api/campaigns/${c.id}/timewarp`, {});
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) for (let d = 1; d <= 8; d++) { await new Promise((res) => setTimeout(res, 200)); setSim(d); }
    try { await req; toast("Season result recorded"); } catch (e) { toast((e as ApiError).message); }
    setSim(null); setBusy(false); onChange();
  };

  const approvals = Object.values(c.seals).filter((v) => v === "approve").length;
  const stage = c.status === "Completed" ? 4 : c.status === "Approved" ? 3 : c.status === "Rejected" ? -1 : 1;
  return (
    <div className="stack">
      <Panel title={<>{c.id}: {r.offer} on {r.product}</>} sub={`${r.segment} in ${r.city_name}, by ${r.channel}`} actions={<Status s={c.status} />}>
        <ol className="progress" aria-label="Progress">
          {STAGES.map((t, i) => <li key={t} className={stage < 0 ? (i === 0 ? "done" : i === 1 ? "now" : "") : i < stage ? "done" : i === stage ? "now" : ""}>{i === 1 ? `${t} (${approvals} of 3)` : t}</li>)}
        </ol>
        <p className="sentence">{r.sentence}.</p>
        <div className="mini-figs" style={{ border: "1px solid var(--line)", borderRadius: "var(--r-sm)", marginTop: 14 }}>
          <div><span>Extra profit</span><b>{r.fmt.net_gp}</b></div>
          <div><span>Extra units</span><b>{num(r.incr_units)}</b></div>
          <div><span>Sell-out risk</span><b>{Math.round(r.p_stockout * 100)}%</b></div>
        </div>
      </Panel>

      <Panel title="Team reviews" sub="Each team checks the part it is responsible for. One rejection stops the promotion.">
        <div className="reviews">
          {TEAMS.map(([k, n, d, f]) => {
            const s = c.seals[k];
            return (
              <section key={k} className={`review ${s === "approve" ? "ok" : s === "reject" ? "no" : ""}`} aria-label={`${n} review`}>
                <div><h3>{n}</h3><p className="small muted">{d}</p></div>
                <ul>{f(r).map((x) => <li key={x}>{x}</li>)}</ul>
                {s ? <span className="decided" style={{ color: s === "approve" ? "var(--leaf)" : "var(--sindoor)" }}><Icon n={s === "approve" ? "check" : "x"} s={15} />{s === "approve" ? "Approved" : "Rejected"}</span>
                  : c.status === "Rejected" ? <span className="small muted">Not needed</span>
                  : <>
                    <textarea placeholder="Note (optional)" aria-label={`${n} note`} value={notes[k] || ""} onChange={(e) => setNotes((x) => ({ ...x, [k]: e.target.value }))} />
                    <div className="review-act">
                      <button className="btn ok sm" disabled={busy} onClick={() => seal(k, "approve")}><Icon n="check" s={14} />Approve</button>
                      <button className="btn danger sm" disabled={busy} onClick={() => seal(k, "reject")}>Reject</button>
                    </div>
                  </>}
              </section>
            );
          })}
        </div>
      </Panel>

      {c.status === "Approved" && (
        <div className="simulate">
          {sim !== null ? <div style={{ width: "100%" }}><b>Running the season, day {Math.max(1, sim)} of 8</b><div className="days">{Array.from({ length: 8 }, (_, i) => <i key={i} className={i < sim ? "lit" : ""} />)}</div></div>
            : <>
              <div><b>Approved by all three teams</b><p className="small" style={{ color: "var(--ink-2)" }}>Run the season in the simulated store network to compare the forecast with what happens.</p></div>
              <button className="btn primary" disabled={busy} onClick={simulate}><Icon n="clock" s={15} />Simulate the season</button>
            </>}
        </div>
      )}

      {o && (
        <Panel title="Season result" sub={`Sales came in ${Math.abs(o.error_pct)}% ${o.error_pct < 0 ? "below" : "above"} the forecast.`}>
          <div className="compare">
            <div><span>Extra units, forecast</span><b>{num(o.pred_incr_units)}</b><HBar label="Actual" right={num(o.actual_incr_units)} pct={(o.actual_incr_units / Math.max(o.pred_incr_units, o.actual_incr_units, 1)) * 100} /></div>
            <div><span>Extra profit, forecast</span><b>{inr(o.pred_net_gp)}</b><HBar label="Actual" right={inr(o.actual_net_gp)} pct={(Math.abs(o.actual_net_gp) / Math.max(Math.abs(o.pred_net_gp), Math.abs(o.actual_net_gp), 1)) * 100} color={o.actual_net_gp < 0 ? "var(--sindoor)" : undefined} /></div>
            <div><span>Sold out</span><b style={{ color: o.stocked_out ? "var(--sindoor)" : "var(--leaf)" }}>{o.stocked_out ? "Yes" : "No"}</b></div>
          </div>
          <p className="answer" style={{ marginTop: 16 }}><b>What the engine learned:</b> {o.lesson}</p>
        </Panel>
      )}

      <Panel title="Activity">
        {!log ? <Skeleton lines={3} /> : !log.length ? <p className="muted">No activity recorded.</p> : (
          <ol className="timeline">{log.map((e, i) => <li key={i}><span><b>{actionText(e.action)}</b>{e.detail ? <span className="muted">: {e.detail}</span> : null}</span><time dateTime={e.created_at}>{when(e.created_at)}</time></li>)}</ol>
        )}
      </Panel>
    </div>
  );
}

function Inbox() {
  const { campaigns, campaignsError, reloadCampaigns } = useApp();
  const params = useSearchParams(), router = useRouter(), path = usePathname();
  const [filter, setFilter] = useState<Filter>("all");
  useEffect(() => { reloadCampaigns(); }, [reloadCampaigns]);

  const all = [...(campaigns || [])].reverse();
  const shown = all.filter((c) => filter === "all" || c.status === filter);
  const id = params.get("c") || shown[0]?.id;
  const c = all.find((x) => x.id === id);
  const choose = (cid: string) => router.replace(`${path}?c=${cid}`, { scroll: false });
  const count = (f: Filter) => (f === "all" ? all.length : all.filter((x) => x.status === f).length);

  return (
    <>
      <PageHeader title="Approvals" sub="Promotions sent from the planner. Marketing, Merchandising and Store Ops each sign off before a promotion runs."
        actions={<>
          <button className="btn" onClick={reloadCampaigns}><Icon n="refresh" s={15} />Refresh</button>
          <Link className="btn primary" href="/planner"><Icon n="plus" s={15} />New promotion</Link>
        </>} />
      {campaignsError && <ErrorBox msg={campaignsError} retry={reloadCampaigns} />}
      {!campaigns && !campaignsError ? <Skeleton lines={8} /> : !all.length ? (
        <Panel><Empty title="Nothing has been sent for approval" action={<Link className="btn primary" href="/planner">Open the planner</Link>}>Set up a promotion in the planner and send it here for the three teams to review.</Empty></Panel>
      ) : (
        <div className="inbox">
          <Panel flush>
            <div style={{ padding: 12, borderBottom: "1px solid var(--line)" }}><Seg label="Status" value={filter} set={setFilter} opts={FILTERS.map(([f, l]) => [f, <>{l} <span className="count">{count(f)}</span></>])} /></div>
            <ul className="list">
              {shown.map((x) => (
                <li key={x.id} className={`click ${x.id === c?.id ? "on" : ""}`} role="button" tabIndex={0} aria-current={x.id === c?.id ? "true" : undefined}
                  onClick={() => choose(x.id)} onKeyDown={(e) => { if (e.key === "Enter") choose(x.id); }} style={{ alignItems: "flex-start" }}>
                  <span className="grow"><b>{x.id}: {x.rec.offer} on {x.rec.product}</b><span>{x.rec.segment} in {x.rec.city_name}, {x.rec.fmt.net_gp}</span></span>
                  <Status s={x.status} />
                </li>
              ))}
              {!shown.length && <li className="muted">No promotions with this status.</li>}
            </ul>
          </Panel>
          {c ? <Detail key={c.id} c={c} onChange={reloadCampaigns} /> : <Panel><Empty title="Select a promotion">Pick one from the list to review it.</Empty></Panel>}
        </div>
      )}
    </>
  );
}

export default function Approvals() {
  return <Suspense fallback={<Skeleton lines={8} />}><Inbox /></Suspense>;
}
