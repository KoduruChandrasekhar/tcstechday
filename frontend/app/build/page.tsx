"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bar } from "react-chartjs-2";
import { useApp } from "@/components/AppState";
import { cssVar } from "@/components/charts-setup";
import { BarRow, ErrorBox, Icon, PageHead, Pager, Pill, TypeIn } from "@/components/ui";
import { VERDICT, api, fin, inr, num, vk, type AiResult, type Rec, type Spec, ApiError } from "@/lib/api";

const CHECKS: [string, string][] = [["profit", "Makes money"], ["stock", "Stock will last"], ["uplift", "Customers respond"], ["ops", "Stores can cope"], ["fatigue", "Not over-messaged"]];
const ASK = ["Why this discount?", "What's the biggest risk?", "How do I make it safer?"];

export default function Build() {
  const { meta, cur, setCur, win, recs, toast, theme } = useApp();
  const router = useRouter();
  const [r, setR] = useState<Rec | null>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const [pin, setPin] = useState<{ key: string; r: Rec; label: string } | null>(null);
  const [flash, setFlash] = useState(0), [sending, setSending] = useState(false);
  const [brief, setBrief] = useState<AiResult | null>(null), [tab, setTab] = useState("whatsapp"), [aiBusy, setAiBusy] = useState(false);
  const [qa, setQa] = useState<{ q: string; a?: AiResult; e?: string }[]>([]), [question, setQuestion] = useState("");
  const seq = useRef(0), prevVerdict = useRef("");

  useEffect(() => { if (!cur && recs?.top[0]) setCur({ ...recs.top[0], cap: recs.top[0].cap ?? null, window: win }); }, [cur, recs, win, setCur]);

  const run = useCallback(async (s: Spec) => {
    const n = ++seq.current; setBusy(true); setErr("");
    try {
      const d = await api<Rec>("/api/simulate", s);
      if (n !== seq.current) return;
      if (prevVerdict.current && prevVerdict.current !== d.verdict) { setFlash((f) => f + 1); toast(`Decision changed: ${VERDICT[vk(prevVerdict.current)].label} → ${VERDICT[vk(d.verdict)].label}`); }
      prevVerdict.current = d.verdict; setR(d); setBrief(null);
    } catch (e) { if (n === seq.current) setErr((e as ApiError).message); }
    if (n === seq.current) setBusy(false);
  }, [toast]);
  useEffect(() => { if (cur) { const t = setTimeout(() => run(cur), 120); return () => clearTimeout(t); } }, [cur, run]);

  if (!meta || !cur) return <main><div className="card"><div className="skel" /><div className="skel" style={{ width: "50%", marginTop: 10 }} /></div></main>;
  const set = (p: Partial<Spec>) => setCur({ ...cur, ...p });
  const key = JSON.stringify(cur), base = pin && pin.key !== key ? pin.r : null;
  const offerName = meta.offers[cur.offer_idx], cityName = meta.cities.find((c) => c.code === cur.city)?.name;
  const productName = meta.products.find((p) => p.sku === cur.sku)?.name;
  const V = VERDICT[vk(r?.verdict)], blocked = vk(r?.verdict) === "BLOCK", rd = Math.round(fin(r?.readiness));

  const delta = (a: number, b: number | undefined, f: (x: number) => string, better: "up" | "down") => {
    if (!base || b === undefined) return null;
    const d = a - b; if (Math.abs(d) < 1e-9) return <span className="delta eq">same</span>;
    const good = better === "up" ? d > 0 : d < 0;
    return <span className={`delta ${good ? "up" : "dn"}`}>{d > 0 ? "▲" : "▼"} {f(Math.abs(d))}</span>;
  };
  const send = async () => {
    setSending(true);
    try { const c = await api<{ id: string }>("/api/campaigns", cur); toast(`Promotion ${c.id} sent for sign-off`); router.push("/signoff"); }
    catch (e) { toast((e as ApiError).message); }
    setSending(false);
  };
  const writeKit = async () => { setAiBusy(true); try { setBrief(await api<AiResult>("/api/brief", cur)); setTab("whatsapp"); } catch (e) { toast((e as ApiError).message); } setAiBusy(false); };
  const ask = async (q: string) => {
    q = q.trim(); if (!q) return; setQuestion("");
    const i = qa.length; setQa((x) => [...x, { q }]);
    try { const a = await api<AiResult>("/api/ai/ask", { ...cur, question: q }); setQa((x) => x.map((v, j) => (j === i ? { ...v, a } : v))); }
    catch (e) { setQa((x) => x.map((v, j) => (j === i ? { ...v, e: (e as ApiError).message } : v))); }
  };

  const burn = r?.burn || [], s0 = Math.max(fin(burn[0]), 1);
  const hist = (r?.history?.units || []).map(fin), avg = hist.length ? hist.reduce((a, b) => a + b, 0) / hist.length : 0;
  const fm = Math.max(1, ...(r?.frontier || []).map((f) => Math.abs(f.net_gp)));
  const wm = Math.max(1, fin(r?.incr_gp), fin(r?.leakage)), other = Math.max(0, fin(r?.incr_gp) - fin(r?.leakage) - fin(r?.net_gp));
  const li = (a?: string[]) => (a?.length ? <ul>{a.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="small muted" style={{ margin: 0 }}>Nothing to add.</p>);

  return (
    <main>
      <PageHead step={4} title="Try your own promotion" lead="Adjust the promotion on the left. The panel on the right tells you instantly whether it makes money, whether stock will last, and why."
        tips={[["Adjust the setup", "try 25% off instead of 10%."], ["Read the decision", "go, go with a change, wait, or don't run."], ["Send it for sign-off", "when you're happy."]]} />

      <div className="builder">
        <div className="grid" style={{ gap: 20 }}>
          <div className="card">
            <h2>Promotion setup</h2><p className="sub">Every change is checked instantly.</p>
            <div className="fields">
              <div className="field wide"><label>Product</label><select value={cur.sku} onChange={(e) => set({ sku: e.target.value })}>{meta.products.map((p) => <option key={p.sku} value={p.sku}>{p.name}</option>)}</select></div>
              <div className="field"><label>Discount</label>
                <select value={cur.offer_idx} onChange={(e) => set({ offer_idx: +e.target.value })}>{meta.offers.map((o, i) => <option key={i} value={i}>{o}</option>)}</select>
                <div className="slider"><input type="range" min={0} max={meta.offers.length - 1} value={cur.offer_idx} onChange={(e) => set({ offer_idx: +e.target.value })} aria-label="Drag to compare discounts" />
                  <div className="ticks">{meta.offers.map((o, i) => <button key={i} className={i === cur.offer_idx ? "on" : ""} onClick={() => set({ offer_idx: i })} title={o}>{o.replace(" + free installation", "+install").replace("Flat ", "")}</button>)}</div></div>
                <span className="live">Drag the slider: decision updates live</span>
              </div>
              <div className="field"><label>Customer group</label><select value={cur.segment} onChange={(e) => set({ segment: e.target.value })}>{Object.keys(meta.segments).map((s) => <option key={s}>{s}</option>)}</select></div>
              <div className="field"><label>City</label><select value={cur.city} onChange={(e) => set({ city: e.target.value })}>{meta.cities.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
              <div className="field"><label>Sent by</label><select value={cur.channel} onChange={(e) => set({ channel: e.target.value })}>{meta.channels.map((c) => <option key={c}>{c}</option>)}</select></div>
              <div className="field"><label>Season</label><div className="fixed">{meta.windows[cur.window]?.name}</div><span className="hint">Change it at the top of the page</span></div>
              <div className="field"><label>Unit limit</label>
                <input type="number" min={1} placeholder="No limit" defaultValue={cur.cap ?? ""} key={`cap-${cur.cap}`} onBlur={(e) => {
                  const v = Math.round(+e.target.value); if (e.target.value && !(v > 0)) { toast("Limit must be a positive number, so it was removed"); set({ cap: null }); } else set({ cap: v > 0 ? v : null });
                }} /><span className="hint">Optional</span></div>
            </div>
            <div className="summary"><b>In short:</b> {offerName} on <b>{productName}</b> for {cur.segment} in {cityName}, via {cur.channel}{cur.cap ? `, up to ${num(cur.cap)} units` : ""}.</div>
          </div>

          <div className="card why"><h2>Why this decision</h2>
            {r ? <div className="whycols">
              <div><h3 style={{ color: "var(--good)" }}><Icon n="plus" s={15} /> What helps</h3>{li(r.drivers)}</div>
              <div>
                {r.blocks.length > 0 && <><h3 style={{ color: "var(--bad)" }}><Icon n="x" s={15} /> What stops it</h3>{li(r.blocks)}</>}
                {r.risks.length > 0 && <><h3 style={{ color: "var(--warn)" }}><Icon n="alert" s={15} /> Watch out for</h3>{li(r.risks)}</>}
                <h3 style={{ color: "var(--info)" }}><Icon n="bulb" s={15} /> What would change this</h3>{li(r.what_would_change)}
              </div></div> : <div className="skel" />}
          </div>

          <div className="card"><h2>Will stock last?</h2><p className="sub">{r?.insights?.burn}</p>
            <div className="chart">{burn.length ? <Bar key={theme + key} data={{ labels: burn.map((_, i) => `Day ${i + 1}`), datasets: [{ label: "Units left", data: burn.map(fin), borderRadius: 6, maxBarThickness: 42,
              backgroundColor: burn.map((v) => (fin(v) <= 0 ? cssVar("--bad") : fin(v) / s0 < 0.25 ? cssVar("--warn") : cssVar("--accent"))) }] }}
              options={{ plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ((c.raw as number) <= 0 ? "Sold out" : `${num(c.raw)} units left (${Math.round(((c.raw as number) / s0) * 100)}% of start)`) } } },
                scales: { x: { grid: { display: false } }, y: { beginAtZero: true, title: { display: true, text: "Units left in stock" } } } }} />
              : <div className="chart-empty">No stock data for this product and city.</div>}</div>
          </div>
        </div>

        <aside key={flash} className={`card panel ${flash ? "flash" : ""}`} style={{ ["--c" as string]: V.color, opacity: busy ? 0.55 : 1 }}>
          {err ? <div style={{ padding: 20 }}><ErrorBox msg={err} retry={() => run(cur)} /></div> : !r ? <div style={{ padding: 22 }}><div className="skel" /></div> : <>
            <div className="top"><div className="lbl" style={{ color: "var(--muted)" }}>Our decision</div><div className="v">{V.label}</div><p>{blocked && r.blocks[0] ? r.blocks[0] + "." : V.text}</p>
              <div className="meterrow"><span>Confidence</span><b>{rd}/100</b></div><div className="meter"><i style={{ width: `${Math.max(2, rd)}%`, background: "var(--c)" }} /></div></div>
            <div className="sec"><h4>Expected result</h4>
              <div className="kv"><span>Extra profit</span><b style={{ color: r.net_gp >= 0 ? "var(--good)" : "var(--bad)" }}>{r.fmt?.net_gp ?? inr(r.net_gp)}{delta(r.net_gp, base?.net_gp, inr, "up")}</b></div>
              <div className="kv"><span>Extra units sold</span><b>{num(r.incr_units)}{delta(r.incr_units, base?.incr_units, num, "up")}</b></div>
              <div className="kv"><span>Chance of selling out</span><b style={{ color: r.p_stockout > 0.2 ? "var(--bad)" : undefined }}>{(r.p_stockout * 100).toFixed(0)}%{delta(r.p_stockout * 100, base ? base.p_stockout * 100 : undefined, (v) => `${v.toFixed(0)} pts`, "down")}</b></div>
              <div className="kv"><span>Discount wasted on people who&apos;d buy anyway</span><b>{r.fmt?.leakage ?? inr(r.leakage)}{delta(r.leakage, base?.leakage, inr, "down")}</b></div>
              <div className="pinbar">{pin ? <><span>{base ? <>Compared with pinned: <b style={{ color: "var(--ink)" }}>{pin.label}</b></> : "This is your pinned version. Change something to compare."}</span><button className="btn ghost xs" onClick={() => setPin(null)}>Unpin</button></>
                : <><span>Pin this version, then change things to compare.</span><button className="btn ghost xs" onClick={() => { setPin({ key, r, label: `${offerName}, ${cityName}` }); toast("Pinned. Now change the discount, city or group to compare"); }}>📌 Pin</button></>}</div>
            </div>
            <div className="sec"><h4>Five checks</h4>{CHECKS.map(([k, n]) => { const v = Math.round(fin(r.scores?.[k])), c = v >= 70 ? "var(--good)" : v >= 40 ? "var(--warn)" : "var(--bad)";
              return <div key={k} className="ck" style={{ ["--c" as string]: c }}><Icon n={v >= 70 ? "check" : v >= 40 ? "minus" : "alert"} s={16} /><span>{n}</span><span className="t"><i style={{ width: `${Math.max(3, v)}%` }} /></span><span className="s">{v >= 70 ? "Good" : v >= 40 ? "Okay" : "Risk"}</span></div>; })}</div>
            <div className="act"><button className="btn" disabled={blocked || busy || sending} onClick={send}>{sending ? "Sending…" : "Send for sign-off"} <Icon n="arrow" s={16} /></button>
              <span className="small muted" style={{ textAlign: "center" }}>{blocked ? "Blocked promotions can't be sent. Try a fix from “What would change this”." : "Marketing, Merchandising and Store Ops will each review it."}</span></div>
          </>}
        </aside>
      </div>

      <div className="card ai section">
        <div className="row between"><div><h2>Campaign kit</h2><p className="sub" style={{ margin: 0 }}>Manager summary, customer messages (incl. Hindi) and staff talking points, written by AI using only the engine&apos;s numbers.</p></div>
          <button className="btn sm" onClick={writeKit} disabled={aiBusy || !r}><Icon n="spark" s={16} />{aiBusy ? "Writing…" : brief ? "Rewrite" : "Write campaign kit"}</button></div>
        {brief && <div className="ai-out">
          <div><div className="lbl">For the manager</div><p><TypeIn text={String(brief.summary || "")} /></p></div>
          <div><div className="lbl">Customer message</div>
            <div className="chips" style={{ margin: "6px 0 8px" }}>{[["whatsapp", "WhatsApp"], ["sms", "SMS"], ["email_subject", "Email subject"], ["hindi", "हिंदी"]].map(([k, l]) => <button key={k} className={`chip ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}</div>
            <div className="bubble"><TypeIn text={String(brief[tab] || "")} />
              <button className="btn ghost xs" style={{ position: "absolute", top: 8, right: 8 }} onClick={() => navigator.clipboard?.writeText(String(brief[tab] || "")).then(() => toast("Message copied"), () => toast("Copy is not available here"))}>Copy</button></div></div>
          <div><div className="lbl">Talking points for store staff</div><ul>{((brief.talking_points as string[]) || []).map((t, i) => <li key={i}>{t}</li>)}</ul></div>
          <div className={`ai-note ${brief.source === "ai" ? "ok" : ""}`}>{brief.source === "ai" ? "✓ " : ""}{brief.note}</div>
        </div>}
        <div className="section" style={{ marginTop: 18 }}><div className="lbl">Ask about this promotion</div>
          <div className="chips" style={{ margin: "6px 0 10px" }}>{ASK.map((q) => <button key={q} className="chip" onClick={() => ask(q)}>{q}</button>)}</div>
          <form className="row" onSubmit={(e) => { e.preventDefault(); ask(question); }}><input className="search" style={{ maxWidth: "none" }} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Type a question…" /><button className="btn sm" disabled={!question.trim()}>Ask</button></form>
          <div className="ai-out">{qa.map((x, i) => <div key={i} className="qa"><b>{x.q}</b>{x.e ? <span className="ai-note">{x.e}</span> : x.a ? <><TypeIn text={String(x.a.answer || "")} /><div className={`ai-note ${x.a.source === "ai" ? "ok" : ""}`}>{x.a.note}</div></> : <span className="muted small">Thinking…</span>}</div>)}</div>
        </div>
      </div>

      {r && <details className="more"><summary><div>More detail<small>Compare discount levels · where the profit goes · past sales · similar promotions</small></div></summary>
        <div className="inner grid g2">
          <div className="card"><h2>Compare discount levels</h2><p className="sub">{r.insights?.frontier}</p><div className="bars">
            {(r.frontier || []).map((f, i) => <BarRow key={i} hl={i === cur.offer_idx} label={<>{f.offer} {i === cur.offer_idx && <span className="tag">current</span>}</>} right={<>{inr(f.net_gp)} <Pill v={f.verdict} /></>} pct={(Math.abs(f.net_gp) / fm) * 100} color={f.net_gp < 0 ? "var(--bad)" : undefined} />)}
          </div></div>
          <div className="card"><h2>Where the profit goes</h2><p className="sub">{r.insights?.waterfall}</p><div className="bars">
            <BarRow label="Profit from extra sales" right={inr(r.incr_gp)} pct={100} color="var(--good)" />
            <BarRow label="Discount to people who'd buy anyway" right={`− ${inr(r.leakage)}`} pct={(r.leakage / wm) * 100} color="var(--bad)" />
            <BarRow label="Messaging and stock-out costs" right={`− ${inr(other)}`} pct={(other / wm) * 100} color="var(--warn)" />
            <BarRow hl label={r.net_gp < 0 ? "Money we lose" : "Profit we keep"} right={inr(r.net_gp)} pct={(Math.abs(r.net_gp) / wm) * 100} color={r.net_gp < 0 ? "var(--bad)" : undefined} />
          </div></div>
          <div className="card"><h2>Weekly sales in this city</h2><p className="sub">{r.insights?.history}</p><div className="chart">
            {hist.some((v) => v > 0) ? <Bar key={theme + key} data={{ labels: r.history!.weeks, datasets: [
              { label: "Last 8 weeks", data: hist.map((v, i) => (i >= hist.length - 8 ? v : null)), backgroundColor: cssVar("--accent"), borderRadius: 3, grouped: false },
              { label: "Earlier weeks", data: hist.map((v, i) => (i < hist.length - 8 ? v : null)), backgroundColor: cssVar("--neutral"), borderRadius: 3, grouped: false },
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              { type: "line" as any, label: "Yearly average", data: hist.map(() => avg), borderColor: cssVar("--ink2"), borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0 } as any] }}
              options={{ plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } }, scales: { x: { ticks: { maxTicksLimit: 6 }, grid: { display: false } }, y: { beginAtZero: true, title: { display: true, text: "Units sold per week" } } } }} />
              : <div className="chart-empty">No sales history for this city and category yet.</div>}</div></div>
          <div className="card"><h2>Similar past promotions</h2><p className="sub">{r.insights?.twins}</p>
            {r.twins?.length ? r.twins.map((t, i) => <div key={i} className="lrow"><div className="grow"><div>{t.name}</div><div className="small muted">Expected {t.pred_roi}× · actual {t.actual_roi}×</div></div><span className={`pill ${t.actual_roi >= t.pred_roi ? "p-GO" : "p-CONDITIONAL"}`}>{t.actual_roi >= t.pred_roi ? "Beat forecast" : "Below forecast"}</span></div>)
              : <p className="muted small">No similar past promotions found.</p>}</div>
        </div></details>}
      <Pager step={4} />
    </main>
  );
}
