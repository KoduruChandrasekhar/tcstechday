"use client";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/components/AppState";
import { Tip } from "@/components/fx";
import { NetworkMap } from "@/components/three/lazy";
import { DataTable, ErrorBox, Icon, PageHeader, Panel, Seg, Skeleton, type Col } from "@/components/ui";
import { SHORT_LABEL, api, cityLights, downloadCSV, fin, num, shortLevel, type CityLight, type MapData, ApiError } from "@/lib/api";

type SkuRow = MapData["rows"][number];
type Move = MapData["transfers"][number];
const lasts = (r: { stock: number; cover_days: number }) => (fin(r.stock) <= 0 ? "Out of stock" : r.cover_days < 1 ? "Under a day" : `${Math.round(r.cover_days)} days`);
const LEVEL_TONE = ["grey", "amber", "red"];

export default function Inventory() {
  const { win, meta } = useApp();
  const [d, setD] = useState<MapData | null>(null), [err, setErr] = useState("");
  const [pick, setPick] = useState(""), [arcs, setArcs] = useState(true), [reset, setReset] = useState(0), [view, setView] = useState<"short" | "extra" | "moves">("short");
  const load = () => { api<MapData>("/api/mismatch?window=" + win).then((x) => { setD(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(load, [win]);

  const lights = useMemo(() => (d ? cityLights(d) : []), [d]);
  const maxShort = Math.max(0, ...lights.map((l) => l.short));
  const worst = useMemo(() => [...lights].sort((a, b) => b.short - a.short)[0]?.name || "", [lights]);
  const sel = pick || worst;
  const c = lights.find((l) => l.name === sel);
  const rows = d?.rows.filter((r) => r.city_name === sel) || [];
  const short = rows.filter((r) => r.status === "SHORT").sort((a, b) => a.cover_days - b.cover_days);
  const extra = rows.filter((r) => r.status === "EXCESS").sort((a, b) => b.cover_days - a.cover_days);
  const moves = d?.transfers.filter((t) => t.to === sel || t.from === sel) || [];

  const cityCols: Col<CityLight>[] = [
    { key: "name", label: "City", sort: (r) => r.name, render: (r) => <b>{r.name}</b> },
    { key: "stores", label: "Stores", num: true, sort: (r) => r.stores, render: (r) => r.stores },
    { key: "demand", label: "Units a day", num: true, sort: (r) => r.demand, hide: "sm", render: (r) => num(r.demand) },
    { key: "stock", label: "In stock", num: true, sort: (r) => r.stock, hide: "md", render: (r) => num(r.stock) },
    { key: "cover", label: <>Days of cover<Tip k="cover" /></>, num: true, sort: (r) => r.cover, hide: "sm", render: (r) => Math.round(r.cover) },
    { key: "short", label: "Running short", num: true, sort: (r) => r.short, render: (r) => { const l = shortLevel(r.short, maxShort); return <span className={`badge ${LEVEL_TONE[l]}`}><i />{r.short}</span>; } },
    { key: "excess", label: "Surplus", num: true, sort: (r) => r.excess, hide: "md", render: (r) => r.excess },
  ];
  const moveCols: Col<Move>[] = [
    { key: "p", label: "Product", sort: (t) => t.product, render: (t) => <b>{t.product}</b> },
    { key: "f", label: "From", sort: (t) => t.from, render: (t) => t.from },
    { key: "t", label: "To", sort: (t) => t.to, render: (t) => t.to },
    { key: "q", label: "Units", num: true, sort: (t) => t.qty, render: (t) => <b>{num(t.qty)}</b> },
  ];
  const lowCols: Col<SkuRow>[] = [
    { key: "p", label: "Product", sort: (r) => r.product, render: (r) => <><b>{r.product}</b><span className="sub">{r.city_name}</span></> },
    { key: "d", label: "Sells a day", num: true, sort: (r) => r.demand_per_day, hide: "sm", render: (r) => r.demand_per_day },
    { key: "s", label: "In stock", num: true, sort: (r) => r.stock, render: (r) => num(r.stock) },
    { key: "c", label: "Lasts", num: true, sort: (r) => r.cover_days, render: (r) => <span className="badge red"><i />{lasts(r)}</span> },
  ];

  const exportMoves = () => d && downloadCSV(`stock-transfers-${win}.csv`, ["Product", "From", "To", "Units"], d.transfers.map((t) => [t.product, t.from, t.to, Math.round(t.qty)]));
  const exportCities = () => downloadCSV(`stock-by-city-${win}.csv`, ["City", "Stores", "Units a day", "In stock", "Days of cover", "Products running short", "Products in surplus"],
    lights.map((l) => [l.name, l.stores, Math.round(l.demand), Math.round(l.stock), Math.round(l.cover), l.short, l.excess]));

  return (
    <>
      <PageHeader title="Inventory" sub={`Stock against festival demand for ${meta?.windows[win]?.name || "the season"}, across the hero products in every city.`}
        actions={<>
          <button className="btn" onClick={exportCities} disabled={!lights.length}><Icon n="download" s={15} />Cities CSV</button>
          <button className="btn" onClick={exportMoves} disabled={!d?.transfers.length}><Icon n="truck" s={15} />Transfers CSV</button>
        </>} />
      {err && <ErrorBox msg={err} retry={load} />}
      {d?.insight && <p className="answer">{d.insight}</p>}

      <div className="grid eq">
        <Panel className="model s-8" title="Store network" sub="Dashed lines are suggested stock moves; they drift toward the city that needs the stock."
          actions={<>
            <label className="small" style={{ display: "inline-flex", gap: 7, alignItems: "center" }}><input type="checkbox" checked={arcs} onChange={(e) => setArcs(e.target.checked)} />Stock moves</label>
            <button className="icon-btn" onClick={() => setReset((r) => r + 1)} aria-label="Reset the 3D view" title="Reset view"><Icon n="rotate" s={15} /></button>
          </>} flush>
          <div className="stage" style={{ ["--h" as string]: "540px" }}>
            {lights.length ? <NetworkMap lights={lights} selected={sel} onSelect={setPick} reset={reset} arcs={arcs ? d!.transfers.map((t) => ({ from: t.from_ll, to: t.to_ll })) : []} />
              : <div className="stage-fallback">{err ? "Map unavailable" : "Loading the network"}</div>}
            <div className="stage-legend"><span><i style={{ background: "var(--accent)" }} />{SHORT_LABEL[0]}</span><span><i style={{ background: "var(--marigold)" }} />{SHORT_LABEL[1]}</span><span><i style={{ background: "var(--sindoor)" }} />{SHORT_LABEL[2]}</span></div>
          </div>
        </Panel>

        <Panel className="s-4 fill" title={c?.name || "City"} sub={c ? `${c.stores} stores, ${num(c.demand)} units a day of festival demand` : undefined} flush>
          {!c ? <div className="panel-b"><Skeleton lines={6} /></div> : <>
            <div className="mini-figs">
              <div><span>Running short</span><b style={{ color: c.short ? "var(--sindoor)" : undefined }}>{c.short}</b></div>
              <div><span>Surplus</span><b>{c.excess}</b></div>
              <div><span>Days of cover</span><b>{Math.round(c.cover)}</b></div>
            </div>
            <div style={{ padding: "12px 18px 0" }}><Seg label="Show" value={view} set={setView} opts={[["short", `Short ${short.length}`], ["extra", `Surplus ${extra.length}`], ["moves", `Moves ${moves.length}`]]} /></div>
            <ul className="list" aria-live="polite">
              {view === "short" && (short.length ? short.map((r, i) => <li key={i}><span className="grow"><b>{r.product}</b><span>Sells {r.demand_per_day} a day, {num(r.stock)} in stock</span></span><span className="badge red"><i />{lasts(r)}</span></li>) : <li className="muted">Nothing is about to run out here.</li>)}
              {view === "extra" && (extra.length ? extra.map((r, i) => <li key={i}><span className="grow"><b>{r.product}</b><span>{num(r.stock)} in stock</span></span><span className="badge violet"><i />{Math.round(r.cover_days)} days</span></li>) : <li className="muted">No surplus here.</li>)}
              {view === "moves" && (moves.length ? moves.map((t, i) => <li key={i}><span className="grow"><b>{t.product}</b><span>{t.from} to {t.to}</span></span><span className="badge amber"><i />{num(t.qty)} units</span></li>) : <li className="muted">No moves suggested for this city.</li>)}
            </ul>
          </>}
        </Panel>
      </div>

      <div className="grid">
        <Panel className="s-12" title="Cities" sub="Click a row to show the city on the map" flush>
          {!d ? <div className="panel-b"><Skeleton lines={6} /></div> : <DataTable label="Stock by city" rows={lights} cols={cityCols} rowKey={(r) => r.name} onRow={(r) => { setPick(r.name); window.scrollTo({ top: 0, behavior: "smooth" }); }} isOn={(r) => r.name === sel} initial={["short", "desc"]} />}
        </Panel>
      </div>

      <div className="grid">
        <Panel className="s-6" title="Suggested transfers" sub="Move these before promoting. No new purchase orders needed." flush>
          {!d ? <div className="panel-b"><Skeleton /></div> : <DataTable label="Suggested stock transfers" rows={d.transfers} cols={moveCols} rowKey={(t) => `${t.product}-${t.from}-${t.to}`} initial={["q", "desc"]} pageSize={8} empty="No moves needed this season." />}
        </Panel>
        <Panel className="s-6" title="Closest to running out" sub="How long stock lasts at the festival rate of sale" flush>
          {!d ? <div className="panel-b"><Skeleton /></div> : <DataTable label="Products closest to running out" rows={d.rows.filter((r) => r.status === "SHORT")} cols={lowCols} rowKey={(r) => `${r.product}-${r.city_name}`} initial={["c", "asc"]} pageSize={8} empty="Nothing is running short." />}
        </Panel>
      </div>
    </>
  );
}
