"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useApp } from "@/components/AppState";
import { Tip } from "@/components/fx";
import Filters from "@/components/Filters";
import { DataTable, ErrorBox, HBar, Icon, Meter, PageHeader, Panel, Skeleton, Verdict, type Col } from "@/components/ui";
import { GOAL_LABEL, VERDICT, catName, downloadCSV, fin, inr, num, vk, type Rec } from "@/lib/api";

type Row = Rec & { rank: number };

export default function Promotions() {
  const { recs, recsError, reloadRecs, objective, setPeek, peek, meta, win } = useApp();
  const [q, setQ] = useState("");

  const rows = useMemo<Row[]>(() => {
    const t = q.trim().toLowerCase();
    return (recs?.top || []).map((r, i) => ({ ...r, rank: i + 1 }))
      .filter((r) => !t || [r.product, r.city_name, r.segment, r.offer, r.channel, catName(r.category)].join(" ").toLowerCase().includes(t));
  }, [recs, q]);
  const total = rows.reduce((a, r) => a + fin(r.net_gp), 0);

  const cols: Col<Row>[] = [
    { key: "rank", label: "#", sort: (r) => r.rank, render: (r) => <span className={`rank ${r.rank === 1 ? "top" : ""}`}>{r.rank}</span>, w: 52 },
    { key: "promo", label: "Promotion", sort: (r) => r.product, render: (r) => <><b>{r.offer} on {r.product}</b><span className="sub">{catName(r.category)}</span></> },
    { key: "seg", label: "Customer group", sort: (r) => r.segment, hide: "sm", render: (r) => r.segment },
    { key: "city", label: "City", sort: (r) => r.city_name, render: (r) => r.city_name },
    { key: "ch", label: "Channel", hide: "md", render: (r) => <span className="muted nw">{r.channel}</span> },
    { key: "v", label: "Decision", sort: (r) => r.verdict, hide: "sm", render: (r) => <Verdict v={r.verdict} /> },
    { key: "gp", label: <>Extra profit<Tip k="profit" /></>, num: true, sort: (r) => r.net_gp, render: (r) => <b style={{ color: r.net_gp < 0 ? "var(--sindoor)" : undefined }}>{r.fmt?.net_gp ?? inr(r.net_gp)}</b> },
    { key: "u", label: "Extra units", num: true, sort: (r) => r.incr_units, hide: "md", render: (r) => num(r.incr_units) },
    { key: "so", label: "Sell-out risk", num: true, sort: (r) => r.p_stockout, hide: "md", render: (r) => <span style={{ color: r.p_stockout > 0.2 ? "var(--sindoor)" : undefined }}>{Math.round(r.p_stockout * 100)}%</span> },
    { key: "c", label: "Confidence", num: true, sort: (r) => r.readiness, hide: "sm", render: (r) => <span className="conf">{Math.round(r.readiness)}<Meter v={r.readiness} /></span> },
  ];

  const exportCSV = () => downloadCSV(`promotions-${win}-${objective}.csv`,
    ["Rank", "Offer", "Product", "Product type", "Customer group", "City", "Channel", "Decision", "Extra profit (INR)", "Extra units", "Sell-out risk %", "Confidence"],
    rows.map((r) => [r.rank, r.offer, r.product, catName(r.category), r.segment, r.city_name, r.channel, VERDICT[vk(r.verdict)].label, Math.round(r.net_gp), Math.round(r.incr_units), Math.round(r.p_stockout * 100), Math.round(r.readiness)]));

  const reasons = Object.entries(recs?.block_reasons || {}).sort((a, b) => b[1] - a[1]);
  const byCat = Object.entries(recs?.gp_by_cat || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);

  return (
    <>
      <PageHeader title="Promotions" sub={`Every idea tested for ${meta?.windows[win]?.name || "this season"}, ranked for ${GOAL_LABEL[objective]}. Open a row for the full reasoning.`}
        actions={<>
          <button className="btn" onClick={exportCSV} disabled={!rows.length}><Icon n="download" s={15} />Export CSV</button>
          <Link className="btn primary" href="/planner"><Icon n="plus" s={15} />New promotion</Link>
        </>}
        tabs={[{ href: "/promotions", label: "Recommended", count: recs?.top.length }, { href: "/promotions/blocked", label: "Blocked", count: recs?.blocked.length }]} />

      <div className="toolbar">
        <Filters />
        <label className="search-box grow-input"><Icon n="search" s={15} /><input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by product, city or group" aria-label="Filter promotions" /></label>
      </div>

      {recsError && <ErrorBox msg={recsError} retry={reloadRecs} />}
      <Panel flush>
        {!recs && !recsError ? <div className="panel-b"><Skeleton lines={8} /></div> : (
          <DataTable label="Recommended promotions" rows={rows} cols={cols} rowKey={(r) => r.id} onRow={setPeek} isOn={(r) => peek?.id === r.id}
            empty={q ? `Nothing matches “${q}”.` : <>No promotions pass the policy rules for this filter. <Link className="link" href="/promotions/blocked">See what was blocked</Link></>} />
        )}
        {rows.length > 0 && <div className="panel-foot"><span className="muted">{rows.length} promotion{rows.length > 1 ? "s" : ""}</span><span>Combined extra profit <b className="num">{inr(total)}</b></span></div>}
      </Panel>

      {recs && (
        <div className="grid">
          <Panel className="s-6" title="Why other ideas were blocked" sub={recs.insights?.block}>
            {reasons.length ? reasons.map(([l, v]) => <HBar key={l} label={l} right={`${num(v)} ideas`} pct={(v / Math.max(1, reasons[0][1])) * 100} color="var(--sindoor)" />) : <p className="muted">Nothing was blocked.</p>}
          </Panel>
          <Panel className="s-6" title="Extra profit by product type" sub={recs.insights?.cat}>
            {byCat.length ? byCat.map(([l, v]) => <HBar key={l} label={catName(l)} right={inr(v)} pct={(fin(v) / Math.max(1, byCat[0][1])) * 100} />) : <p className="muted">No profit figures for this filter.</p>}
          </Panel>
        </div>
      )}
    </>
  );
}
