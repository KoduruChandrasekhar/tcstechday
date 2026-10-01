"use client";
import { useEffect, useMemo, useState } from "react";
import { Scatter } from "react-chartjs-2";
import { useApp } from "@/components/AppState";
import { cssVar } from "@/components/charts-setup";
import { Tip } from "@/components/fx";
import { DataTable, ErrorBox, HBar, Icon, PageHeader, Panel, Seg, Skeleton, type Col } from "@/components/ui";
import { api, day, downloadCSV, ApiError } from "@/lib/api";

interface Row { id: string; name: string; objective: string; start: string; pred_roi: number; actual_roi: number; stockouts?: number; leakage_pct?: number; gp?: string }
interface Mem { insight: string; rows: Row[]; calibration?: { bias: number; sd: number; mae: number; n: number } }
const TOL = 0.5;
const nice = (s: string) => (s ? s[0].toUpperCase() + s.slice(1).replace(/_/g, " ") : "All");
const close = (c: Row) => Math.abs(c.actual_roi - c.pred_roi) <= TOL;

export default function Performance() {
  const { theme } = useApp();
  const [d, setD] = useState<Mem | null>(null), [err, setErr] = useState(""), [f, setF] = useState("all");
  const load = () => { api<Mem>("/api/memory").then((x) => { setD(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(load, []);

  const all = useMemo(() => (d?.rows || []).filter((c) => Number.isFinite(+c.pred_roi) && Number.isFinite(+c.actual_roi)), [d]);
  const kinds = [...new Set(all.map((c) => c.objective).filter(Boolean))].sort();
  const m = all.filter((c) => f === "all" || c.objective === f);
  const xs = m.flatMap((c) => [+c.pred_roi, +c.actual_roi]).sort((a, b) => a - b);
  const pc = (q: number) => xs[Math.min(xs.length - 1, Math.max(0, Math.round(q * (xs.length - 1))))] ?? 0;
  const lo = Math.floor(pc(0.03) - 0.5), hi = Math.ceil(pc(0.97) + 0.5);
  const near = m.filter(close), far = m.filter((c) => !close(c));
  const outside = m.filter((c) => [c.pred_roi, c.actual_roi].some((v) => v < lo || v > hi)).length;
  const cal = d?.calibration;
  const byKind = kinds.map((k) => { const g = all.filter((c) => c.objective === k); return [k, g.length ? g.filter(close).length / g.length : 0, g.length] as const; }).sort((a, b) => b[1] - a[1]);

  const cols: Col<Row>[] = [
    { key: "n", label: "Promotion", sort: (c) => c.name, render: (c) => <><b>{c.name}</b><span className="sub">{c.id}</span></> },
    { key: "o", label: "Type", sort: (c) => c.objective, hide: "sm", render: (c) => nice(c.objective) },
    { key: "s", label: "Started", sort: (c) => c.start, hide: "md", render: (c) => day(c.start) },
    { key: "p", label: <>Forecast return<Tip k="roi" /></>, num: true, sort: (c) => c.pred_roi, render: (c) => `${c.pred_roi}×` },
    { key: "a", label: "Actual return", num: true, sort: (c) => c.actual_roi, render: (c) => <b style={{ color: close(c) ? undefined : "var(--amber)" }}>{c.actual_roi}×</b> },
    { key: "d", label: "Difference", num: true, sort: (c) => c.actual_roi - c.pred_roi, hide: "sm", render: (c) => { const v = +(c.actual_roi - c.pred_roi).toFixed(2); return <span className={`delta ${Math.abs(v) <= TOL ? "eq" : v > 0 ? "up" : "dn"}`}>{v > 0 ? "+" : ""}{v}×</span>; } },
    { key: "so", label: "Store-days out of stock", num: true, sort: (c) => c.stockouts ?? 0, hide: "md", render: (c) => c.stockouts ?? "" },
    { key: "w", label: "Wasted discount", num: true, sort: (c) => c.leakage_pct ?? 0, hide: "md", render: (c) => (c.leakage_pct !== undefined ? `${c.leakage_pct}%` : "") },
  ];
  const exportCSV = () => downloadCSV("forecast-accuracy.csv", ["ID", "Promotion", "Type", "Started", "Forecast return", "Actual return", "Store-days out of stock", "Wasted discount %", "Gross profit"],
    m.map((c) => [c.id, c.name, nice(c.objective), c.start, c.pred_roi, c.actual_roi, c.stockouts ?? "", c.leakage_pct ?? "", c.gp ?? ""]));

  return (
    <>
      <PageHeader title="Performance" sub="Every past promotion, with the return we forecast and the return it made. The planner uses these results to keep its forecasts honest."
        actions={<button className="btn" onClick={exportCSV} disabled={!m.length}><Icon n="download" s={15} />Export CSV</button>} />
      {err && <ErrorBox msg={err} retry={load} />}

      <div className="ledger" aria-label="Forecast accuracy summary">
        <div><span>Past promotions</span><b>{cal?.n ?? (d ? all.length : "–")}</b><small>With a forecast and a measured result</small></div>
        <div><span>Close to forecast</span><b>{all.length ? `${Math.round((all.filter(close).length / all.length) * 100)}%` : "–"}</b><small>Within {TOL}× of the forecast return</small></div>
        <div><span>Average miss</span><b>{cal ? `${cal.mae}×` : "–"}</b><small>Forecast against actual return</small></div>
        <div><span>Bias</span><b>{cal ? `${cal.bias > 0 ? "+" : ""}${cal.bias}×` : "–"}</b><small>{cal ? (Math.abs(cal.bias) < 0.05 ? "Forecasts run neither high nor low" : cal.bias > 0 ? "Results tend to beat forecasts" : "Forecasts tend to run high") : "Checking"}</small></div>
      </div>

      <div className="toolbar">
        <Seg label="Promotion type" value={f} set={setF} opts={[["all", <>All <span className="count">{all.length}</span></>], ...kinds.map((k) => [k, <>{nice(k)} <span className="count">{all.filter((c) => c.objective === k).length}</span></>] as [string, React.ReactNode])]} />
      </div>

      <div className="grid">
        <Panel className="s-8" title="Forecast against result" sub={`Each dot is one promotion. Dots in the shaded band landed within ${TOL}× of the forecast.`}>
          <div className="chart" style={{ height: 400 }}>
            {!d && !err ? <Skeleton h={380} /> : m.length ? <Scatter key={theme + f} data={{ datasets: [
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              { type: "line" as any, label: "_hi", data: [{ x: lo, y: lo + TOL }, { x: hi, y: hi + TOL }], borderWidth: 0, pointRadius: 0, fill: false } as any,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              { type: "line" as any, label: `Within ${TOL}× of forecast`, data: [{ x: lo, y: lo - TOL }, { x: hi, y: hi - TOL }], borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: cssVar("--accent-soft") } as any,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              { type: "line" as any, label: "Perfect forecast", data: [{ x: lo, y: lo }, { x: hi, y: hi }], borderColor: cssVar("--muted"), borderDash: [6, 5], pointRadius: 0, borderWidth: 1.2 } as any,
              { label: "Close to forecast", data: near.map((c) => ({ x: +c.pred_roi, y: +c.actual_roi, n: c.name })), backgroundColor: cssVar("--accent"), pointRadius: 4.5, pointHoverRadius: 7 },
              { label: "Off forecast", data: far.map((c) => ({ x: +c.pred_roi, y: +c.actual_roi, n: c.name })), backgroundColor: cssVar("--marigold"), pointRadius: 4.5, pointHoverRadius: 7 },
            ] }} options={{ plugins: { filler: { drawTime: "beforeDatasetsDraw" }, legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, filter: (i) => !i.text.startsWith("_") } },
              tooltip: { filter: (i) => !!(i.raw as { n?: string })?.n, callbacks: { title: (c) => (c[0]?.raw as { n?: string })?.n || "", label: (c) => `Forecast ${(c.raw as { x: number }).x}×, actual ${(c.raw as { y: number }).y}×` } } },
              scales: { x: { min: lo, max: hi, title: { display: true, text: "Forecast return per ₹1 of discount" } }, y: { min: lo, max: hi, title: { display: true, text: "Actual return" } } } }} />
              : <div className="chart-empty">No completed promotions yet.</div>}
          </div>
          {m.length > 0 && <p className="small muted" style={{ marginTop: 10 }}>{near.length} of {m.length} landed close to the forecast.{outside ? ` ${outside} unusual result${outside > 1 ? "s sit" : " sits"} beyond the chart edges.` : ""}</p>}
        </Panel>
        <Panel className="s-4" title="Accuracy by type" sub={`Share within ${TOL}× of the forecast`}>
          {!d ? <Skeleton lines={5} /> : byKind.map(([k, v, n]) => <HBar key={k} hl={k === f} label={<>{nice(k)} <span className="muted small">{n}</span></>} right={`${Math.round(v * 100)}%`} pct={v * 100} color={v >= 0.5 ? "var(--accent)" : "var(--marigold)"} />)}
          {d?.insight && <p className="answer" style={{ marginTop: 18 }}>{d.insight}</p>}
        </Panel>
      </div>

      <div className="grid">
        <Panel className="s-12" title={f === "all" ? "All past promotions" : `${nice(f)} promotions`} flush>
          {!d ? <div className="panel-b"><Skeleton lines={8} /></div> : <DataTable label="Past promotions" rows={m} cols={cols} rowKey={(c) => c.id} initial={["s", "desc"]} pageSize={12} empty="No completed promotions yet." />}
        </Panel>
      </div>
    </>
  );
}
