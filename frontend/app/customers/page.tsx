"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppState";
import { Tip } from "@/components/fx";
import { SegmentBlocks } from "@/components/three/lazy";
import { DataTable, ErrorBox, HBar, Icon, Meter, PageHeader, Panel, Skeleton, type Col } from "@/components/ui";
import { api, catName, downloadCSV, fin, num, specOf, ApiError } from "@/lib/api";

interface Seg { segment: string; size: number; persuadable: number; fatigue?: number; treated: number; control: number; lift: number; top_categories: string[] }
interface Aud {
  segments: Seg[];
  model: { model?: string; features?: string[]; train_rows: number; treated: number; control: number; obs_uplift_top30_pts: number; obs_uplift_rest_pts: number; obs_uplift_all_pts: number };
  dnc: number; chart_insight: string;
}
const per100 = (v: number) => (v * 100).toFixed(1);

export default function Customers() {
  const { recs, cur, setCur, win, toast, meta } = useApp();
  const router = useRouter();
  const [d, setD] = useState<Aud | null>(null), [err, setErr] = useState(""), [pick, setPick] = useState(""), [reset, setReset] = useState(0);
  const load = () => { api<Aud>("/api/audiences").then((x) => { setD(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(load, []);

  const segs = [...(d?.segments || [])].sort((a, b) => b.lift - a.lift);
  const best = segs[0]?.segment || "";
  const sel = segs.find((s) => s.segment === (pick || best));
  const plan = (g: string) => {
    const r = recs?.top.find((x) => x.segment === g);
    if (r) setCur(specOf(r, win)); else if (cur) setCur({ ...cur, segment: g });
    toast(r ? `Opened the best promotion for ${g}` : `Customer group set to ${g}`);
    router.push("/planner");
  };
  const mc = d?.model;
  const proof: [string, number, string][] = mc ? [["Customers we choose (top 30%)", mc.obs_uplift_top30_pts, "var(--accent)"], ["Everyone else", mc.obs_uplift_rest_pts, "var(--line-2)"], ["Offer sent to everyone", mc.obs_uplift_all_pts, "var(--muted)"]] : [];
  const pm = Math.max(0.01, ...proof.map((p) => p[1]));

  const cols: Col<Seg>[] = [
    { key: "g", label: "Customer group", sort: (s) => s.segment, render: (s) => <><b>{s.segment}</b><span className="sub">Likes {(s.top_categories || []).slice(0, 2).map((x) => catName(x.split(" ")[0])).join(", ")}</span></> },
    { key: "n", label: "Customers", num: true, sort: (s) => s.size, render: (s) => num(s.size) },
    { key: "t", label: "Buy with offer", num: true, sort: (s) => s.treated, hide: "md", render: (s) => `${per100(s.treated)}%` },
    { key: "c", label: "Buy without", num: true, sort: (s) => s.control, hide: "md", render: (s) => `${per100(s.control)}%` },
    { key: "l", label: <>Extra per 100<Tip k="uplift" /></>, num: true, sort: (s) => s.lift, render: (s) => <b style={{ color: s.lift > 0 ? "var(--accent-ink)" : "var(--muted)" }}>{s.lift > 0 ? `+${per100(s.lift)}` : "None"}</b> },
    { key: "p", label: "Persuadable", num: true, sort: (s) => s.persuadable, hide: "sm", render: (s) => <span className="conf">{Math.round(s.persuadable * 100)}%<Meter v={s.persuadable * 100} tone="var(--accent)" /></span> },
    { key: "f", label: "Offers in 60 days", num: true, sort: (s) => fin(s.fatigue), hide: "md", render: (s) => fin(s.fatigue).toFixed(1) },
  ];
  const exportCSV = () => downloadCSV("customer-groups.csv", ["Customer group", "Customers", "Buy with offer %", "Buy without %", "Extra buyers per 100", "Persuadable %", "Offers in last 60 days"],
    segs.map((s) => [s.segment, s.size, per100(s.treated), per100(s.control), per100(s.lift), Math.round(s.persuadable * 100), fin(s.fatigue).toFixed(1)]));

  return (
    <>
      <PageHeader title="Customers" sub="Who an offer actually persuades. Each group is compared with similar customers who got no offer, so a discount only goes where it changes behaviour."
        actions={<>
          <button className="btn" onClick={exportCSV} disabled={!segs.length}><Icon n="download" s={15} />Export CSV</button>
          {sel && <button className="btn primary" onClick={() => plan(sel.segment)}><Icon n="sliders" s={15} />Plan for {sel.segment}</button>}
        </>} />
      {err && <ErrorBox msg={err} retry={load} />}
      {d?.chart_insight && <p className="answer">{d.chart_insight}</p>}

      <div className="grid">
        <Panel className="model s-8" title="Customer groups" sub="Width is group size. Grey is buying anyway; the coloured top is extra buyers the offer brings."
          actions={<button className="icon-btn" onClick={() => setReset((r) => r + 1)} aria-label="Reset the 3D view" title="Reset view"><Icon n="rotate" s={15} /></button>} flush>
          <div className="stage" style={{ ["--h" as string]: "460px" }}>
            {segs.length ? <SegmentBlocks segs={segs} selected={sel?.segment || ""} onSelect={setPick} reset={reset} /> : <div className="stage-fallback">{err ? "Customer data unavailable" : "Loading customer groups"}</div>}
            <div className="stage-legend"><span><i style={{ background: "var(--line-2)" }} />Buy without an offer</span><span><i style={{ background: "var(--accent)" }} />Extra buyers with an offer</span><span><i style={{ background: "var(--marigold)" }} />Selected</span></div>
          </div>
        </Panel>

        <Panel className="s-4" title={sel?.segment || "Customer group"} sub={sel ? `${num(sel.size)} customers${sel.segment === best ? ", the strongest response" : ""}` : undefined}>
          {!sel ? <Skeleton lines={6} /> : <>
            <div className="pair">
              <HBar label="Buy with an offer" right={`${per100(sel.treated)}%`} pct={(sel.treated / Math.max(...segs.map((s) => s.treated))) * 100} color="var(--accent)" />
              <HBar label="Buy without" right={`${per100(sel.control)}%`} pct={(sel.control / Math.max(...segs.map((s) => s.treated))) * 100} color="var(--line-2)" />
            </div>
            <div className="kv" style={{ marginTop: 16 }}><span>Extra buyers per 100<Tip k="uplift" /></span><b>{sel.lift > 0 ? `+${per100(sel.lift)}` : "None"}</b></div>
            <div className="kv"><span>Persuadable share</span><b>{Math.round(sel.persuadable * 100)}%</b></div>
            <div className="kv"><span>Offers received, last 60 days</span><b>{fin(sel.fatigue).toFixed(1)}</b></div>
            <h3 style={{ marginTop: 16 }}>Most likely to buy</h3>
            <ul className="bul">{(sel.top_categories || []).map((x) => { const [c, m] = x.split(" "); return <li key={x}>{catName(c)} <span className="muted">{m?.replace("×", "")}× the average</span></li>; })}</ul>
            <button className="btn primary" style={{ marginTop: 18, width: "100%" }} onClick={() => plan(sel.segment)}>Plan a promotion for this group</button>
          </>}
        </Panel>
      </div>

      <div className="grid">
        <Panel className="s-8" title="All groups" sub="Click a row to select the group" flush>
          {!d ? <div className="panel-b"><Skeleton lines={6} /></div> : <DataTable label="Customer groups" rows={segs} cols={cols} rowKey={(s) => s.segment} onRow={(s) => setPick(s.segment)} isOn={(s) => s.segment === sel?.segment} />}
          {d && <div className="panel-foot"><span className="muted">{num(d.dnc)} customers are never contacted: opted out, on Do Not Disturb, or no consent.</span></div>}
        </Panel>
        <Panel className="s-4" title="Does the targeting work?" sub="Checked on customers held back from past offers">
          {!mc?.train_rows ? <Skeleton lines={4} /> : <>
            <p className="small muted" style={{ marginBottom: 14 }}>Learned from {num(mc.train_rows)} past offers: {num(mc.treated)} customers received one and {num(mc.control)} similar customers were held back. Extra buyers per 100:</p>
            {proof.map(([l, v, c]) => <HBar key={l} label={l} right={`+${v}`} pct={(v / pm) * 100} color={c} />)}
            <p className="answer" style={{ marginTop: 16 }}>Offering only to the customers we choose brings {(mc.obs_uplift_top30_pts / Math.max(mc.obs_uplift_all_pts, 0.01)).toFixed(1)} times as many extra buyers per 100 as offering to everyone.</p>
            {meta && <p className="note" style={{ marginTop: 10 }}>{mc.model || "Uplift model"}, using {(mc.features || []).length} customer signals.</p>}
          </>}
        </Panel>
      </div>
    </>
  );
}
