"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppState";
import { Answer, BarRow, CountUp, ErrorBox, Icon, PageHead, Pager, Pill, Skeleton, TypeIn } from "@/components/ui";
import { api, fin, inr, num, specOf, type AiResult, type Rec, ApiError } from "@/lib/api";

const GOALS = [["profit", "Most profit"], ["growth", "More sales"], ["clear", "Clear old stock"], ["retain", "Win back customers"]];
const NOTE: Record<string, [string, string]> = { "Too much stock": ["t-info", "box"], "Running out": ["t-bad", "alert"], "Rising interest": ["t-good", "up"], Festival: ["t-warn", "cal"], "Lapsing customers": ["t-warn", "users"] };
const SORTS: [string, string, (a: Rec, b: Rec) => number][] = [
  ["rank", "Best match", () => 0], ["profit", "Profit", (a, b) => b.net_gp - a.net_gp],
  ["conf", "Confidence", (a, b) => b.readiness - a.readiness], ["risk", "Lowest risk", (a, b) => a.p_stockout - b.p_stockout || b.net_gp - a.net_gp],
];

export default function TopPicks() {
  const { meta, metaError, recs, recsError, reloadRecs, objective, setObjective, city, setCity, cat, setCat, win, setCur } = useApp();
  const router = useRouter();
  const [q, setQ] = useState(""), [sort, setSort] = useState("rank"), [all, setAll] = useState(false);
  const [ai, setAi] = useState<AiResult | null>(null), [aiBusy, setAiBusy] = useState(false), [aiErr, setAiErr] = useState("");

  const picks = useMemo(() => {
    if (!recs) return [];
    const qq = q.trim().toLowerCase();
    const list = recs.top.map((r, i) => ({ ...r, _rank: i + 1 }))
      .filter((r) => !qq || [r.product, r.city_name, r.segment, r.offer, r.category].join(" ").toLowerCase().includes(qq));
    return list.sort(SORTS.find((s) => s[0] === sort)![2]);
  }, [recs, q, sort]);
  const shown = all || q ? picks : picks.slice(0, 6);
  const notes = useMemo(() => {
    if (!recs) return [];
    const byType = [...new Map(recs.opportunities.map((o) => [o.type, o])).values()];
    recs.opportunities.forEach((o) => byType.length < 6 && !byType.includes(o) && byType.push(o));
    return byType.slice(0, 6);
  }, [recs]);

  const open = (r: Rec) => { setCur(specOf(r, win)); router.push("/build"); };
  const briefing = async () => {
    setAiBusy(true); setAiErr("");
    const p = new URLSearchParams({ objective, window: win }); if (city) p.set("city", city); if (cat) p.set("category", cat);
    try { setAi(await api<AiResult>("/api/ai/overview?" + p)); } catch (e) { setAiErr((e as ApiError).message); }
    setAiBusy(false);
  };

  if (metaError) return <main><ErrorBox msg={metaError} retry={() => location.reload()} /></main>;
  const k = recs?.kpis, safe = k ? fin(k.counts.GO) + fin(k.counts["CONDITIONAL GO"]) : 0;
  const cats = meta ? [...new Set(meta.products.map((p) => p.cat))].sort() : [];

  return (
    <main>
      <PageHead step={1} title="The best promotions to run" lead="We tried every combination of product, city, customer group and discount, and kept only the promotions that make money without running out of stock."
        tips={[["Pick a goal", "profit, sales, clearing stock or winning customers back."], ["Browse the picks", "best first."], ["Open one", "to see why, and change it."]]} />

      <div className="filters">
        <span className="small muted">Goal</span>
        <div className="chips">{GOALS.map(([v, l]) => <button key={v} className={`chip ${objective === v ? "on" : ""}`} onClick={() => setObjective(v)}>{l}</button>)}</div>
        <select className="pick" value={city} onChange={(e) => setCity(e.target.value)} aria-label="City"><option value="">All cities</option>{meta?.cities.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</select>
        <select className="pick" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category"><option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</select>
      </div>

      {recsError && <ErrorBox msg={recsError} retry={reloadRecs} />}
      <Answer icon="spark">{recs ? recs.insight || "No results for this filter." : <span className="skel" style={{ display: "block", width: "70%" }} />}</Answer>

      {k && (
        <div className="pipe">
          {[[k.candidates, "promotion ideas checked", 100], [safe, "are safe to run", (safe / Math.max(k.candidates, 1)) * 100], [recs!.top.length, "picked for you", Math.max(2, (recs!.top.length / Math.max(k.candidates, 1)) * 100)]].map(([v, l, p], i) => (
            <div key={i} className="rise" style={{ animationDelay: `${i * 60}ms` }}><div className="v"><CountUp to={v as number} /></div><div className="l">{l}</div><div className="meter"><i style={{ width: `${p}%` }} /></div></div>
          ))}
        </div>
      )}

      <div className="card ai">
        <div className="row between"><div><h2>Morning briefing</h2><p className="sub" style={{ margin: 0 }}>A plain-English summary of these results, written by AI from the engine&apos;s numbers.</p></div>
          <button className="btn sm" onClick={briefing} disabled={aiBusy || !recs}><Icon n="spark" s={16} />{aiBusy ? "Writing…" : ai ? "Rewrite" : "Write my briefing"}</button></div>
        {aiErr && <p className="ai-note">{aiErr}</p>}
        {ai && (
          <div className="ai-out">
            <p style={{ fontSize: "1.1rem", fontWeight: 600 }}><TypeIn text={String(ai.headline || "")} /></p>
            <p><TypeIn text={String(ai.briefing || "")} /></p>
            <div><div className="lbl">Do next</div><ul>{((ai.actions as string[]) || []).map((a, i) => <li key={i}>{a}</li>)}</ul></div>
            <div className={`ai-note ${ai.source === "ai" ? "ok" : ""}`}>{ai.source === "ai" ? "✓ " : ""}{ai.note}</div>
          </div>
        )}
      </div>

      <div className="section">
        <div className="row between" style={{ alignItems: "flex-end" }}>
          <div><h2>Our top picks</h2><p className="sub">Click a card to see why it was picked</p></div>
          <button className="link" onClick={() => setAll((a) => !a)}>{q ? `${picks.length} match${picks.length === 1 ? "" : "es"}` : picks.length > 6 ? (all ? "Show fewer" : `Show all ${picks.length}`) : ""}</button>
        </div>
        <div className="tools">
          <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search product, city or customer group…" aria-label="Search promotions" />
          <span className="small muted">Sort by</span>
          <div className="seg2">{SORTS.map(([v, l]) => <button key={v} className={sort === v ? "on" : ""} onClick={() => setSort(v)}>{l}</button>)}</div>
        </div>
        <div className="pcards">
          {!recs && !recsError && <Skeleton />}
          {recs && shown.map((r, i) => (
            <button key={r.id} className="pcard rise" style={{ animationDelay: `${i * 55}ms` }} onClick={() => open(r)}>
              <div className="row between"><span className="rank">#{r._rank}</span><Pill v={r.verdict} /></div>
              <div className="prod">{r.product}</div><span className="offer">{r.offer}</span>
              <div className="meta"><span><Icon n="users" s={15} />{r.segment}</span><span><Icon n="pin" s={15} />{r.city_name}</span></div>
              <div className="foot">
                <div><div className="money-l">Extra profit</div><div className="money" style={{ color: r.net_gp < 0 ? "var(--bad)" : undefined }}><CountUp to={r.net_gp} fmt="inr" /></div></div>
                <div className="conf"><div className="money-l">Confidence {Math.round(r.readiness)}</div><div className="track"><i style={{ width: `${r.readiness}%` }} /></div></div>
              </div>
            </button>
          ))}
          {recs && !shown.length && <div className="card empty" style={{ gridColumn: "1/-1" }}><b>{q ? `No picks match “${q}”` : "No safe promotions for this filter"}</b>{q ? "Try a product, city or group name." : "Try another goal or city, or see what was blocked."}</div>}
        </div>
      </div>

      <div className="section"><h2>Things we noticed</h2><p className="sub">Signals from sales, stock and online searches</p>
        <div className="notes">{notes.length ? notes.map((o, i) => { const [t, ic] = NOTE[o.type] || ["t-info", "bulb"]; return <div key={i} className={`note ${t}`}><span className="ic"><Icon n={ic} s={16} /></span><div><b>{o.type}</b>{o.text}</div></div>; }) : <p className="muted small">Nothing unusual right now.</p>}</div>
      </div>

      {recs && (
        <details className="more"><summary><div>More detail<small>Why promotions were blocked · extra profit by category</small></div></summary>
          <div className="inner grid g2">
            <div className="card"><h2>Why ideas were blocked</h2><p className="sub">{recs.insights?.block}</p><div className="bars">
              {Object.entries(recs.block_reasons || {}).sort((a, b) => b[1] - a[1]).map(([l, v], _, arr) => <BarRow key={l} label={l} right={`${num(v)} ideas`} pct={(v / Math.max(1, arr[0][1])) * 100} color="var(--bad)" />)}
            </div></div>
            <div className="card"><h2>Extra profit by category</h2><p className="sub">{recs.insights?.cat}</p><div className="bars">
              {Object.entries(recs.gp_by_cat || {}).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([l, v], _, arr) => <BarRow key={l} label={l} right={inr(v)} pct={(v / Math.max(1, arr[0][1])) * 100} />)}
            </div></div>
          </div>
        </details>
      )}
      <Pager step={1} />
    </main>
  );
}
