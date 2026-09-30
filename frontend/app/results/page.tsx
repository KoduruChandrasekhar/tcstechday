"use client";
import { useEffect, useMemo, useState } from "react";
import { Scatter } from "react-chartjs-2";
import { useApp } from "@/components/AppState";
import { cssVar } from "@/components/charts-setup";
import { Answer, ErrorBox, PageHead, Pager } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

interface Mem { insight: string; rows: { id: string; name: string; objective: string; start: string; pred_roi: number; actual_roi: number }[] }
const TOL = 0.5;

export default function Results() {
  const { theme } = useApp();
  const [d, setD] = useState<Mem | null>(null), [err, setErr] = useState(""), [f, setF] = useState("");
  const load = () => { api<Mem>("/api/memory").then((x) => { setD(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(() => { load(); }, []);

  const all = useMemo(() => (d?.rows || []).filter((c) => Number.isFinite(+c.pred_roi) && Number.isFinite(+c.actual_roi)), [d]);
  const objs = [...new Set(all.map((c) => c.objective).filter(Boolean))].sort();
  const m = all.filter((c) => !f || c.objective === f);
  const xs = m.flatMap((c) => [+c.pred_roi, +c.actual_roi]).sort((a, b) => a - b);
  const pc = (q: number) => xs[Math.min(xs.length - 1, Math.max(0, Math.round(q * (xs.length - 1))))] ?? 0;
  const lo = Math.floor(pc(0.03) - 0.5), hi = Math.ceil(pc(0.97) + 0.5);
  const on = m.filter((c) => Math.abs(c.actual_roi - c.pred_roi) <= TOL), off = m.filter((c) => Math.abs(c.actual_roi - c.pred_roi) > TOL);
  const outside = m.filter((c) => [c.pred_roi, c.actual_roi].some((v) => v < lo || v > hi)).length;

  return (
    <main>
      <PageHead step={7} title="How good were our forecasts?" lead="Every past promotion: what we expected it to return, and what it actually returned. This is how we earn trust: with a track record."
        tips={[["Each dot", "is one past promotion."], ["Green band", "forecast within ±0.5×."], ["Filter", "by promotion type."]]} />
      {err && <ErrorBox msg={err} retry={load} />}
      <Answer icon="check">{d?.insight || <span className="skel" style={{ display: "block", width: "60%" }} />}</Answer>
      <div className="grid g2">
        <div className="card"><h2>Expected vs actual return</h2><p className="sub">Dots near the dashed line = accurate forecast.</p>
          <div className="chart" style={{ height: 320 }}>{m.length ? <Scatter key={theme + f} data={{ datasets: [
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            { type: "line" as any, label: "_hi", data: [{ x: lo, y: lo + TOL }, { x: hi, y: hi + TOL }], borderWidth: 0, pointRadius: 0, fill: false } as any,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            { type: "line" as any, label: `Accurate zone (±${TOL}×)`, data: [{ x: lo, y: lo - TOL }, { x: hi, y: hi - TOL }], borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: cssVar("--good") + "22" } as any,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            { type: "line" as any, label: "Perfect forecast", data: [{ x: lo, y: lo }, { x: hi, y: hi }], borderColor: cssVar("--muted"), borderDash: [6, 5], pointRadius: 0, borderWidth: 1.5 } as any,
            { label: "On target", data: on.map((c) => ({ x: +c.pred_roi, y: +c.actual_roi, n: c.name })), backgroundColor: cssVar("--good"), pointRadius: 5, pointHoverRadius: 8 },
            { label: "Off target", data: off.map((c) => ({ x: +c.pred_roi, y: +c.actual_roi, n: c.name })), backgroundColor: cssVar("--warn"), pointRadius: 5, pointHoverRadius: 8 },
          ] }} options={{ plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, filter: (i) => !i.text.startsWith("_") } },
            tooltip: { filter: (i) => !!(i.raw as { n?: string })?.n, callbacks: { title: (c) => (c[0]?.raw as { n?: string })?.n || "", label: (c) => `Expected ${(c.raw as { x: number }).x}× · actual ${(c.raw as { y: number }).y}×` } } },
            scales: { x: { min: lo, max: hi, title: { display: true, text: "Expected return (× per ₹1 of discount)" } }, y: { min: lo, max: hi, title: { display: true, text: "Actual return" } } } }} />
            : <div className="chart-empty">No completed promotions yet.</div>}</div>
          {m.length > 0 && <p className="small muted" style={{ margin: "10px 0 0" }}>{on.length} of {m.length} promotions ({Math.round((on.length / m.length) * 100)}%) landed within ±{TOL}× of the forecast.{outside ? ` ${outside} extreme result${outside > 1 ? "s are" : " is"} off the chart edges.` : ""}</p>}
        </div>
        <div className="card"><h2>Recent promotions</h2><p className="sub">Return per ₹1 of discount spent</p>
          <div className="chips" style={{ marginBottom: 10 }}>{[["", "All"], ...objs.map((o) => [o, o.replace(/_/g, " ")])].map(([v, l]) => (
            <button key={v} className={`chip ${f === v ? "on" : ""}`} onClick={() => setF(v)}>{l[0].toUpperCase() + l.slice(1)} <span style={{ opacity: 0.7 }}>{v ? all.filter((c) => c.objective === v).length : all.length}</span></button>))}</div>
          <div style={{ maxHeight: 360, overflow: "auto" }}><table><thead><tr><th>Promotion</th><th className="r">Expected</th><th className="r">Actual</th></tr></thead><tbody>
            {m.slice(0, 40).map((c) => <tr key={c.id}><td>{c.name}<div className="small muted">{c.start}</div></td><td className="r">{c.pred_roi}×</td><td className="r"><b style={{ color: c.actual_roi >= c.pred_roi ? "var(--good)" : "var(--warn)" }}>{c.actual_roi}×</b></td></tr>)}
          </tbody></table></div>
        </div>
      </div>
      <Pager step={7} />
    </main>
  );
}
