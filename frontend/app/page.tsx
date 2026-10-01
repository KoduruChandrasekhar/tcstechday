"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/components/AppState";
import { Tip } from "@/components/fx";
import { NetworkMap } from "@/components/three/lazy";
import { DataTable, Drawer, ErrorBox, Icon, Meter, PageHeader, Panel, Skeleton, Status, TypeIn, Verdict, type Col } from "@/components/ui";
import { GOAL_LABEL, SHORT_LABEL, api, catName, cityLights, day, inr, num, seasonStatus, shortLevel, type AiResult, type MapData, type Rec, ApiError } from "@/lib/api";

const SIGNAL_TONE: Record<string, string> = { "Too much stock": "violet", "Running out": "red", "Rising interest": "green", Festival: "amber", "Lapsing customers": "amber" };
const LEVEL_TONE = ["grey", "amber", "red"];

export default function Overview() {
  const { meta, metaError, recs, recsError, reloadRecs, win, city: cityFilter, cat, objective, campaigns, setPeek } = useApp();
  const [map, setMap] = useState<MapData | null>(null), [mapErr, setMapErr] = useState("");
  const [city, setCity] = useState(""), [reset, setReset] = useState(0);
  const [brief, setBrief] = useState<AiResult | null>(null), [briefOpen, setBriefOpen] = useState(false), [busy, setBusy] = useState(false), [briefErr, setBriefErr] = useState("");

  const loadMap = () => { api<MapData>("/api/mismatch?window=" + win).then((m) => { setMap(m); setMapErr(""); }).catch((e: ApiError) => setMapErr(e.message)); };
  useEffect(loadMap, [win]);

  const lights = useMemo(() => (map ? cityLights(map) : []), [map]);
  const maxShort = Math.max(0, ...lights.map((l) => l.short));
  const cities = useMemo(() => [...lights].sort((a, b) => b.short - a.short || b.demand - a.demand), [lights]);

  const writeBrief = async () => {
    setBriefOpen(true); setBusy(true); setBriefErr("");
    const p = new URLSearchParams({ objective, window: win }); if (cityFilter) p.set("city", cityFilter); if (cat) p.set("category", cat);
    try { setBrief(await api<AiResult>("/api/ai/overview?" + p)); } catch (e) { setBriefErr((e as ApiError).message); }
    setBusy(false);
  };

  const w = meta?.windows[win], k = recs?.kpis, counts = k?.counts;
  const passed = counts ? (counts.GO || 0) + (counts["CONDITIONAL GO"] || 0) + (counts.HOLD || 0) : 0;
  const waiting = (campaigns || []).filter((c) => c.status === "Pending sign-off" || c.status === "Approved");

  const cols: Col<Rec & { rank: number }>[] = [
    { key: "rank", label: "#", render: (r) => <span className={`rank ${r.rank === 1 ? "top" : ""}`}>{r.rank}</span>, w: 44 },
    { key: "promo", label: "Promotion", render: (r) => <><b>{r.offer} on {r.product}</b><span className="sub">{catName(r.category)}</span></> },
    { key: "who", label: "Customers", hide: "md", render: (r) => <><span className="nw">{r.segment}</span><span className="sub">{r.city_name}</span></> },
    { key: "v", label: "Decision", hide: "sm", render: (r) => <Verdict v={r.verdict} /> },
    { key: "gp", label: "Extra profit", num: true, render: (r) => <b style={{ color: r.net_gp < 0 ? "var(--sindoor)" : undefined }}>{r.fmt?.net_gp ?? inr(r.net_gp)}</b> },
    { key: "conf", label: "Confidence", num: true, hide: "sm", render: (r) => <span className="conf">{Math.round(r.readiness)}<Meter v={r.readiness} /></span> },
  ];

  return (
    <>
      <PageHeader
        title={w?.name || "Overview"}
        sub={meta && w ? `${day(w.start, false)} to ${day(w.end)}, ${seasonStatus(meta.today, w)}. Figures use sales, stock and customer data up to ${day(meta.today)}.` : "Loading the season"}
        actions={<>
          <button className="btn" onClick={writeBrief} disabled={!recs}><Icon n="doc" s={15} />Season briefing</button>
          <Link className="btn primary" href="/promotions">Review promotions</Link>
        </>} />

      {(metaError || recsError) && <ErrorBox msg={metaError || recsError} retry={metaError ? () => location.reload() : reloadRecs} />}

      <div className="ledger" aria-label="This season's promotion funnel">
        <div><span>Ideas tested</span><b>{k ? num(k.candidates) : "–"}</b><small>Every product, city, customer group and discount</small></div>
        <div><span>Pass the policy rules</span><b>{counts ? num(passed) : "–"}</b><small>{counts ? <Link className="link" href="/promotions/blocked">{num(counts.BLOCK || 0)} blocked</Link> : "Checking"}</small></div>
        <div><span>Recommended</span><b>{recs ? recs.top.length : "–"}</b><small>Ranked for {GOAL_LABEL[objective]}</small></div>
        <div className="hl"><span>Extra profit<Tip k="profit" /></span><b>{k?.net_gp_top ?? "–"}</b><small>If every recommended promotion runs</small></div>
      </div>

      <div className="grid eq">
        <Panel className="model s-8" title="Store network" sub="Tower height is festival demand, width is the number of stores. Click a city for details."
          actions={<button className="icon-btn" onClick={() => setReset((r) => r + 1)} aria-label="Reset the 3D view" title="Reset view"><Icon n="rotate" s={15} /></button>} flush>
          <div className="stage" style={{ ["--h" as string]: "470px" }}>
            {mapErr ? <div className="stage-fallback">{mapErr}</div> : lights.length ? <NetworkMap lights={lights} selected={city} onSelect={(n) => setCity((s) => (s === n ? "" : n))} reset={reset} /> : <div className="stage-fallback">Loading the network</div>}
            <div className="stage-legend"><span><i style={{ background: "var(--accent)" }} />{SHORT_LABEL[0]}</span><span><i style={{ background: "var(--marigold)" }} />{SHORT_LABEL[1]}</span><span><i style={{ background: "var(--sindoor)" }} />{SHORT_LABEL[2]}</span></div>
          </div>
        </Panel>

        <Panel className="s-4 fill" title="Cities" sub="Most products running short first" flush>
          {!map && !mapErr ? <div className="panel-b"><Skeleton lines={6} /></div> : (
            <ul className="list">
              {cities.map((c) => {
                const lvl = shortLevel(c.short, maxShort);
                return (
                  <li key={c.name} className={`click ${city === c.name ? "on" : ""}`} onClick={() => setCity((s) => (s === c.name ? "" : c.name))}
                    tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") setCity((s) => (s === c.name ? "" : c.name)); }} aria-pressed={city === c.name} role="button">
                    <span className="grow"><b>{c.name}</b><span>{c.stores} stores, {num(c.demand)} units a day</span></span>
                    <span className={`badge ${LEVEL_TONE[lvl]}`}><i />{c.short ? `${c.short} short` : "Stock holds"}</span>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="panel-foot"><span className="muted">{city ? `${city} selected` : `${lights.length} cities`}</span><Link className="link" href="/inventory">Open inventory</Link></div>
        </Panel>
      </div>

      <div className="grid">
        <Panel className="s-8" title="Recommended promotions" sub={recs ? `Top ${Math.min(8, recs.top.length)} of ${recs.top.length}, ranked for ${GOAL_LABEL[objective]}` : undefined}
          actions={<Link className="btn sm" href="/promotions">View all</Link>} flush>
          {!recs && !recsError ? <div className="panel-b"><Skeleton lines={6} /></div> : (
            <DataTable label="Recommended promotions" rows={(recs?.top || []).slice(0, 8).map((r, i) => ({ ...r, rank: i + 1 }))} cols={cols} rowKey={(r) => r.id} onRow={setPeek}
              empty={<>No promotions pass the rules for this filter. <Link className="link" href="/promotions/blocked">See what was blocked</Link></>} />
          )}
        </Panel>

        <div className="stack s-4">
          <Panel title="Needs action" actions={<Link className="link" href="/approvals">Approvals</Link>} flush>
            {!campaigns ? <div className="panel-b"><Skeleton lines={2} /></div> : waiting.length ? (
              <ul className="list">
                {waiting.slice(0, 4).map((c) => (
                  <li key={c.id}><Link href={`/approvals?c=${c.id}`} className="row" style={{ display: "flex", gap: 12, alignItems: "center", width: "100%" }}>
                    <span className="grow"><b>{c.id}: {c.rec.offer} on {c.rec.product}</b><span>{c.rec.segment} in {c.rec.city_name}</span></span><Status s={c.status} />
                  </Link></li>
                ))}
              </ul>
            ) : <p className="panel-b muted">Nothing is waiting. Promotions sent for approval appear here.</p>}
          </Panel>
          <Panel title="Signals" sub="From recent sales, stock and online searches" flush>
            {!recs ? <div className="panel-b"><Skeleton lines={4} /></div> : (
              <ul className="list">
                {recs.opportunities.slice(0, 5).map((o, i) => (
                  <li key={i} style={{ alignItems: "flex-start" }}><span className="grow"><span className={`badge ${SIGNAL_TONE[o.type] || "grey"}`} style={{ marginBottom: 4 }}><i />{o.type}</span><span style={{ color: "var(--ink-2)" }}>{o.text}</span></span></li>
                ))}
                {!recs.opportunities.length && <li className="muted">No new signals this week.</li>}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <Drawer open={briefOpen} onClose={() => setBriefOpen(false)} title="Season briefing" sub={`${w?.name || ""}, ranked for ${GOAL_LABEL[objective]}. Written from the planning engine's own figures.`}
        footer={<>
          {brief && <button className="btn" onClick={() => navigator.clipboard?.writeText([brief.headline, brief.briefing, ...((brief.actions as string[]) || [])].join("\n\n"))}><Icon n="copy" s={15} />Copy</button>}
          <button className="btn primary" onClick={writeBrief} disabled={busy}>{busy ? "Writing" : "Write again"}</button>
        </>}>
        {briefErr && <ErrorBox msg={briefErr} retry={writeBrief} />}
        {busy && !brief && <Skeleton lines={6} />}
        {brief && (
          <div style={{ display: "grid", gap: 14, opacity: busy ? 0.5 : 1 }}>
            <p style={{ font: "650 1.15rem/1.4 var(--font-head)" }}><TypeIn text={String(brief.headline || "")} /></p>
            <p><TypeIn text={String(brief.briefing || "")} /></p>
            <div><h3>Next actions</h3><ul className="bul">{((brief.actions as string[]) || []).map((a, i) => <li key={i}>{a}</li>)}</ul></div>
            <p className={`note ${brief.source === "ai" ? "ok" : ""}`}>{brief.note}</p>
          </div>
        )}
      </Drawer>
    </>
  );
}
