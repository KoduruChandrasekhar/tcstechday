"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppState";
import Filters from "@/components/Filters";
import { Empty, ErrorBox, Icon, PageHeader, Panel, Skeleton, TypeIn } from "@/components/ui";
import { api, catName, downloadCSV, specOf, type AiResult, type Rec, ApiError } from "@/lib/api";

const RULES: Record<string, (v: number) => string> = {
  min_gp_margin: (v) => `Keep at least ${(v * 100).toFixed(0)}% profit margin after the discount`,
  max_stockout_prob: (v) => `Keep the chance of selling out below ${(v * 100).toFixed(0)}%`,
  max_capacity_load: () => "Only promote installed products where stores have installation slots",
  max_leakage_share: (v) => `Waste no more than ${(v * 100).toFixed(0)}% of the discount on people who'd buy anyway`,
  max_fatigue: (v) => `Don't message a customer group more than ${v} times in 60 days`,
  min_segment_size: (v) => `Only target groups of at least ${v} customers, to protect privacy`,
};

function Case({ r, open, toggle }: { r: Rec; open: boolean; toggle: () => void }) {
  const { setCur, win } = useApp();
  const router = useRouter();
  const [ai, setAi] = useState<AiResult | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const explain = async () => { setBusy(true); setErr(""); try { setAi(await api<AiResult>("/api/ai/fix", specOf(r, win))); } catch (e) { setErr((e as ApiError).message); } setBusy(false); };
  return (
    <li style={{ display: "block", padding: 0 }}>
      <button className="case-h" onClick={toggle} aria-expanded={open}>
        <span className="grow"><b>{r.offer} on {r.product}</b><span>{catName(r.category)} for {r.segment} in {r.city_name}</span></span>
        <span className="case-why">{r.blocks?.[0]}</span>
        <Icon n={open ? "chevU" : "chevD"} s={16} />
      </button>
      {open && (
        <div className="case-b">
          <div className="why">
            <div><h3 style={{ color: "var(--sindoor)" }}>Rules it breaks</h3><ul className="bul">{(r.blocks || []).map((b, j) => <li key={j}>{b}</li>)}</ul></div>
            <div><h3 style={{ color: "var(--leaf)" }}>What would make it safe</h3><ul className="bul">{(r.what_would_change || []).slice(0, 3).map((f, j) => <li key={j}>{f}</li>)}</ul></div>
          </div>
          <div className="toolbar" style={{ marginTop: 16 }}>
            <button className="btn primary sm" onClick={() => { setCur(specOf(r, win)); router.push("/planner"); }}><Icon n="sliders" s={14} />Fix in planner</button>
            <button className="btn sm" onClick={explain} disabled={busy}><Icon n="doc" s={14} />{busy ? "Writing" : ai ? "Write the rescue plan again" : "Write a rescue plan"}</button>
          </div>
          {err && <ErrorBox msg={err} retry={explain} />}
          {ai && (
            <div className="rescue">
              <p><TypeIn text={String(ai.explain || "")} /></p>
              <ol className="bul">{((ai.plan as string[]) || []).map((p, j) => <li key={j}>{p}</li>)}</ol>
              {ai.verdict_after ? <p className="muted">{String(ai.verdict_after)}</p> : null}
              <p className={`note ${ai.source === "ai" ? "ok" : ""}`}>{ai.note}</p>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function Blocked() {
  const { meta, recs, recsError, reloadRecs, win } = useApp();
  const [open, setOpen] = useState<string>("");
  const list = recs?.blocked || [];
  const exportCSV = () => downloadCSV(`blocked-${win}.csv`, ["Offer", "Product", "Customer group", "City", "Rules broken", "Suggested fix"],
    list.map((r) => [r.offer, r.product, r.segment, r.city_name, (r.blocks || []).join("; "), (r.what_would_change || []).slice(0, 2).join("; ")]));

  return (
    <>
      <PageHeader title="Promotions" sub="Ideas the policy rules stopped. Each shows the rule it breaks and the smallest change that would make it safe."
        actions={<button className="btn" onClick={exportCSV} disabled={!list.length}><Icon n="download" s={15} />Export CSV</button>}
        tabs={[{ href: "/promotions", label: "Recommended", count: recs?.top.length }, { href: "/promotions/blocked", label: "Blocked", count: recs?.blocked.length }]} />
      <div className="toolbar"><Filters /></div>
      {recsError && <ErrorBox msg={recsError} retry={reloadRecs} />}

      <div className="grid">
        <Panel className="s-8" title={recs ? `${list.length} blocked promotion${list.length === 1 ? "" : "s"}` : "Blocked promotions"} sub="Open one to see the rule it breaks and the fix" flush>
          {!recs && !recsError ? <div className="panel-b"><Skeleton lines={8} /></div>
            : !list.length ? <Empty title="Nothing blocked">Every idea for this filter passed the policy rules.</Empty>
            : <ul className="list">{list.map((r) => <Case key={r.id} r={r} open={open === r.id} toggle={() => setOpen((o) => (o === r.id ? "" : r.id))} />)}</ul>}
        </Panel>
        <Panel className="s-4 sticky" title="Policy rules" sub="Every promotion is checked against these before it can be sent for approval">
          {meta ? <ol className="rules">{Object.entries(meta.guardrails).map(([k, v]) => <li key={k}>{RULES[k] ? RULES[k](v) : `${k}: ${v}`}</li>)}</ol> : <Skeleton />}
        </Panel>
      </div>
    </>
  );
}
