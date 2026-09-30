"use client";
import { useEffect, useState } from "react";
import { useApp } from "@/components/AppState";
import { Answer, ErrorBox, Icon, PageHead, Pager } from "@/components/ui";
import { api, fin, num, ApiError } from "@/lib/api";

interface Row { city: string; city_name: string; product: string; status: string; cover_days: number; demand_per_day: number; stock: number }
interface Mismatch {
  insight: string; rows: Row[];
  transfers: { product: string; from: string; to: string; qty: number; from_ll: [number, number]; to_ll: [number, number] }[];
  cities: { city: string; lat: number; lon: number; stores: number; short: number; excess: number }[];
}
const P = (lat: number, lon: number) => [((lon - 68) / 29) * 380 + 30, ((36 - lat) / 29) * 420 + 25];
const lasts = (r: Row) => (fin(r.stock) <= 0 ? "out of stock" : r.cover_days < 1 ? "under a day" : `${r.cover_days} days`);

export default function Stock() {
  const { win } = useApp();
  const [d, setD] = useState<Mismatch | null>(null), [err, setErr] = useState(""), [sel, setSel] = useState("");
  const load = () => { api<Mismatch>("/api/mismatch?window=" + win).then((x) => { setD(x); setErr(""); setSel([...x.cities].sort((a, b) => b.short - a.short)[0]?.city || ""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(() => { load(); }, [win]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = d?.rows.filter((r) => r.city_name === sel) || [];
  const sh = rows.filter((r) => r.status === "SHORT").sort((a, b) => a.cover_days - b.cover_days), ex = rows.filter((r) => r.status === "EXCESS").sort((a, b) => b.cover_days - a.cover_days);
  const c = d?.cities.find((x) => x.city === sel), inb = d?.transfers.filter((t) => t.to === sel).length || 0, out = d?.transfers.filter((t) => t.from === sel).length || 0;

  return (
    <main>
      <PageHead step={2} title="Is our stock where the buyers are?" lead="Promoting a product that's about to sell out wastes money and disappoints customers. Here's where we're short, where we have too much, and how to rebalance."
        tips={[["Red circles", "products about to run out."], ["Blue circles", "more stock than needed."], ["Dashed lines", "suggested stock moves."]]} />
      {err && <ErrorBox msg={err} retry={load} />}
      <Answer icon="truck">{d?.insight || <span className="skel" style={{ display: "block", width: "60%" }} />}</Answer>
      <div className="grid g2">
        <div className="card"><h2>Stock across cities</h2><p className="sub">Click a city to see what&apos;s short and what&apos;s in surplus there</p>
          <svg className="map" viewBox="0 0 440 470" style={{ width: "100%", maxHeight: 520 }} role="img" aria-label="Map of stock by city">
            {d?.transfers.map((t, i) => { const [a, b] = P(...t.from_ll), [x, y] = P(...t.to_ll); return (
              <path key={i} d={`M${a},${b} Q${(a + x) / 2 + 30},${(b + y) / 2 - 40} ${x},${y}`} stroke="var(--accent)" strokeWidth={2} fill="none" strokeDasharray="5 4" opacity={0.85}>
                <animate attributeName="stroke-dashoffset" from="18" to="0" dur="1.2s" repeatCount="indefinite" /></path>); })}
            {d?.cities.map((c) => { const [x, y] = P(c.lat, c.lon), r = 5 + Math.sqrt(c.short) * 3.2; return (
              <g key={c.city} className="city" onClick={() => setSel(c.city)} tabIndex={0} role="button" onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSel(c.city)}>
                <title>{`${c.city}: ${c.short} short, ${c.excess} surplus`}</title>
                {c.short > 0 && <circle cx={x} cy={y} r={r} fill="none" stroke="var(--bad)" strokeWidth={1.5}><animate attributeName="r" from={r} to={r + 9} dur="2s" repeatCount="indefinite" /><animate attributeName="opacity" from=".7" to="0" dur="2s" repeatCount="indefinite" /></circle>}
                <circle cx={x} cy={y} r={r} fill="color-mix(in srgb,var(--bad) 14%,transparent)" stroke="var(--bad)" strokeWidth={1.5} />
                <circle cx={x + 4} cy={y + 4} r={3 + Math.sqrt(c.excess) * 2.6} fill="color-mix(in srgb,var(--info) 14%,transparent)" stroke="var(--info)" />
                <circle cx={x} cy={y} r={sel === c.city ? 5 : 3} fill={sel === c.city ? "var(--accent)" : "var(--ink)"} />
                <text x={x + 12} y={y - 6} fontWeight={600}>{c.city}</text>
                <text x={x + 12} y={y + 7} style={{ fontSize: 10, fill: "var(--muted)" }}>{c.short} short · {c.excess} extra</text>
              </g>); })}
          </svg>
          {c && <div style={{ borderTop: "1px solid var(--border)", marginTop: 14, paddingTop: 14 }}>
            <div className="row between" style={{ marginBottom: 8 }}><b>{sel}</b></div>
            <div className="stat3"><div>Stores<b>{num(c.stores)}</b></div><div>Running short<b style={{ color: "var(--bad)" }}>{sh.length}</b></div><div>Surplus<b style={{ color: "var(--info)" }}>{ex.length}</b></div></div>
            {sh.slice(0, 3).map((r, i) => <div key={i} className="lrow"><div className="grow"><div>{r.product}</div><div className="small muted">sells {r.demand_per_day}/day · {num(r.stock)} in stock</div></div><span className="days">{lasts(r)}</span></div>)}
            {ex.slice(0, 2).map((r, i) => <div key={i} className="lrow"><div className="grow"><div>{r.product}</div><div className="small muted">{num(r.stock)} in stock</div></div><span className="qty" style={{ color: "var(--info)" }}>{Math.round(r.cover_days)} days of stock</span></div>)}
            <p className="small muted" style={{ margin: "8px 0 0" }}>{inb || out ? `${inb} suggested move${inb === 1 ? "" : "s"} into ${sel}, ${out} out.` : "No stock moves suggested for this city."}</p>
          </div>}
          <div className="legend"><span><i style={{ background: "var(--bad)" }} />Running short</span><span><i style={{ background: "var(--info)" }} />Too much stock</span><span><i style={{ background: "var(--accent)" }} />Suggested move</span></div>
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card"><h2>Suggested stock moves</h2><p className="sub">Move these before promoting</p>
            {d ? d.transfers.length ? d.transfers.slice(0, 8).map((t, i) => <div key={i} className="lrow"><span className="qty">{num(t.qty)} units</span><div className="grow"><div>{t.product}</div><div className="route">{t.from} <Icon n="arrow" s={14} /> {t.to}</div></div></div>) : <p className="muted small">No moves needed.</p> : <div className="skel" />}</div>
          <div className="card"><h2>About to run out</h2><p className="sub">Days the current stock will last at today&apos;s sales</p>
            {d ? (d.rows.filter((r) => r.status === "SHORT").sort((a, b) => a.cover_days - b.cover_days).slice(0, 6).map((r, i) => <div key={i} className="lrow"><div className="grow"><div>{r.product}</div><div className="small muted">{r.city_name} · sells {r.demand_per_day}/day · {num(r.stock)} in stock</div></div><span className="days">{lasts(r)}</span></div>)) : <div className="skel" />}</div>
        </div>
      </div>
      <Pager step={2} />
    </main>
  );
}
