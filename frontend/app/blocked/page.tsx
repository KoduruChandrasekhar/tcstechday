"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppState";
import { ErrorBox, Icon, PageHead, Pager, Pill, Skeleton, TypeIn } from "@/components/ui";
import { catEmoji } from "@/lib/api";
import { api, specOf, type AiResult, type Rec, ApiError } from "@/lib/api";

const RULES: Record<string, (v: number) => string> = {
  min_gp_margin: (v) => `Keep at least ${(v * 100).toFixed(0)}% profit margin after discount`, max_stockout_prob: (v) => `Less than ${(v * 100).toFixed(0)}% chance of selling out`,
  max_capacity_load: () => "Stores must have enough installation slots", max_leakage_share: (v) => `No more than ${(v * 100).toFixed(0)}% of the discount wasted`,
  max_fatigue: (v) => `Don't over-message customers (max ${v} recent promos)`, min_segment_size: (v) => `Only target groups of ${v}+ customers (privacy)`,
};

function Case({ r, i }: { r: Rec; i: number }) {
  const { setCur, win } = useApp();
  const router = useRouter();
  const [ai, setAi] = useState<AiResult | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const explain = async () => { setBusy(true); setErr(""); try { setAi(await api<AiResult>("/api/ai/fix", specOf(r, win))); } catch (e) { setErr((e as ApiError).message); } setBusy(false); };
  return (
    <div className="bcard rise" style={{ animationDelay: `${i * 45}ms` }}>
      <div className="row between"><span className="offer">{r.offer}</span><Pill v="BLOCK" /></div>
      <div className="prod-row"><span className="prod-tile" aria-hidden>{catEmoji(r.category)}</span><div className="prod">{r.product}</div></div>
      <div className="meta"><span><Icon n="users" s={15} />{r.segment}</span><span><Icon n="pin" s={15} />{r.city_name}</span></div>
      {r.blocks?.map((b, j) => <div key={j} className="box bad"><Icon n="x" s={16} /><span>{b}</span></div>)}
      {r.what_would_change?.slice(0, 2).map((f, j) => <div key={j} className="box fix"><Icon n="wrench" s={16} /><span>{f}</span></div>)}
      {ai && <div className="ai-out" style={{ marginTop: 4 }}><p><TypeIn text={String(ai.explain || "")} /></p>
        <div><div className="lbl">Rescue plan</div><ul>{((ai.plan as string[]) || []).map((p, j) => <li key={j}>{p}</li>)}</ul></div>
        <p className="muted small">{String(ai.verdict_after || "")}</p><div className={`ai-note ${ai.source === "ai" ? "ok" : ""}`}>{ai.note}</div></div>}
      {err && <p className="ai-note">{err}</p>}
      <div className="row" style={{ marginTop: "auto" }}>
        <button className="btn ghost sm" onClick={() => { setCur(specOf(r, win)); router.push("/build"); }}>Try the fix <Icon n="arrow" s={15} /></button>
        <button className="btn ghost sm" onClick={explain} disabled={busy}><Icon n="edit" s={15} />{busy ? "Writing…" : "Explain & rescue"}</button>
      </div>
    </div>
  );
}

export default function Blocked() {
  const { meta, recs, recsError, reloadRecs } = useApp();
  return (
    <main>
      <PageHead step={5} title="Promotions we should not run" lead="A good planner also says no. Each of these breaks one of our safety rules. We show the problem and how to fix it."
        tips={[["Our safety rules", "no promotion may break these."], ["Red box", "the problem."], ["Green box", "the fix. Try it in the builder."]]} />
      <div className="card" style={{ marginBottom: 18 }}><h2>Our safety rules</h2><p className="sub">Checked automatically for every promotion</p>
        <div className="rules">{meta ? Object.entries(meta.guardrails).map(([k, v]) => <span key={k} className="rule"><Icon n="shield" s={16} />{RULES[k] ? RULES[k](v) : `${k}: ${v}`}</span>) : <div className="skel" style={{ width: 300 }} />}</div></div>
      {recsError && <ErrorBox msg={recsError} retry={reloadRecs} />}
      <div className="grid g3">
        {!recs && !recsError && <Skeleton />}
        {recs && (recs.blocked.length ? recs.blocked.map((r, i) => <Case key={r.id} r={r} i={i} />) : <div className="card empty" style={{ gridColumn: "1/-1" }}><b>Nothing blocked</b>Every idea for this filter passed the safety rules.</div>)}
      </div>
      <Pager step={5} />
    </main>
  );
}
