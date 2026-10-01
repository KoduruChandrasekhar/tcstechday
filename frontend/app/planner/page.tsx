"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bar } from "react-chartjs-2";
import { useApp } from "@/components/AppState";
import { cssVar } from "@/components/charts-setup";
import { Tip, Tween } from "@/components/fx";
import { CHECKS } from "@/components/PromoDrawer";
import { StockRunway } from "@/components/three/lazy";
import { ErrorBox, HBar, Icon, Meter, PageHeader, Panel, Skeleton, TypeIn, Verdict } from "@/components/ui";
import { VERDICT, api, catName, fin, inr, num, vk, type AiResult, type Rec, type Spec, ApiError } from "@/lib/api";

const QUESTIONS = ["Why this discount?", "What is the biggest risk?", "How do I make it safer?"];
const MESSAGES: [string, string][] = [["whatsapp", "WhatsApp"], ["sms", "SMS"], ["email_subject", "Email subject"], ["hindi", "Hindi"]];
const TABS: [string, string][] = [["breakdown", "Profit breakdown"], ["history", "Sales history"], ["similar", "Similar promotions"], ["kit", "Campaign kit"], ["ask", "Ask"]];

export default function Planner() {
  const { meta, cur, setCur, win, recs, toast, theme, reloadCampaigns } = useApp();
  const router = useRouter();
  const [r, setR] = useState<Rec | null>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const [pin, setPin] = useState<{ key: string; r: Rec; label: string } | null>(null);
  const [flash, setFlash] = useState(0), [sending, setSending] = useState(false), [reset, setReset] = useState(0);
  const [tab, setTab] = useState("breakdown");
  const [kit, setKit] = useState<AiResult | null>(null), [msg, setMsg] = useState("whatsapp"), [kitBusy, setKitBusy] = useState(false);
  const [qa, setQa] = useState<{ q: string; a?: AiResult; e?: string }[]>([]), [question, setQuestion] = useState("");
  const seq = useRef(0), prevVerdict = useRef("");

  useEffect(() => { if (!cur && recs?.top[0]) setCur({ ...recs.top[0], cap: recs.top[0].cap ?? null, window: win }); }, [cur, recs, win, setCur]);

  const run = useCallback(async (s: Spec) => {
    const n = ++seq.current; setBusy(true); setErr("");
    try {
      const d = await api<Rec>("/api/simulate", s);
      if (n !== seq.current) return;
      if (prevVerdict.current && prevVerdict.current !== d.verdict) { setFlash((f) => f + 1); toast(`Decision changed to ${VERDICT[vk(d.verdict)].label}`); }
      prevVerdict.current = d.verdict; setR(d); setKit(null);
    } catch (e) { if (n === seq.current) setErr((e as ApiError).message); }
    if (n === seq.current) setBusy(false);
  }, [toast]);
  useEffect(() => { if (cur) { const t = setTimeout(() => run(cur), 120); return () => clearTimeout(t); } }, [cur, run]);

  if (!meta || !cur) return <><PageHeader title="Planner" sub="Loading products, cities and customer groups" /><Skeleton lines={8} /></>;

  const set = (p: Partial<Spec>) => setCur({ ...cur, ...p });
  const key = JSON.stringify(cur), base = pin && pin.key !== key ? pin.r : null;
  const offerName = meta.offers[cur.offer_idx], cityName = meta.cities.find((c) => c.code === cur.city)?.name;
  const product = meta.products.find((p) => p.sku === cur.sku);
  const V = VERDICT[vk(r?.verdict)], blocked = vk(r?.verdict) === "BLOCK", rd = Math.round(fin(r?.readiness));

  const delta = (a: number, b: number | undefined, f: (x: number) => string, better: "up" | "down") => {
    if (!base || b === undefined) return null;
    const dd = a - b;
    if (Math.abs(dd) < 1e-9) return <span className="delta eq">same</span>;
    return <span className={`delta ${(better === "up" ? dd > 0 : dd < 0) ? "up" : "dn"}`}>{dd > 0 ? "+" : "−"}{f(Math.abs(dd))}</span>;
  };
  const send = async () => {
    setSending(true);
    try { const c = await api<{ id: string }>("/api/campaigns", cur); reloadCampaigns(); toast(`Sent for approval as ${c.id}`); router.push(`/approvals?c=${c.id}`); }
    catch (e) { toast((e as ApiError).message); }
    setSending(false);
  };
  const writeKit = async () => { setKitBusy(true); try { setKit(await api<AiResult>("/api/brief", cur)); setMsg("whatsapp"); } catch (e) { toast((e as ApiError).message); } setKitBusy(false); };
  const ask = async (q: string) => {
    q = q.trim(); if (!q) return; setQuestion("");
    const i = qa.length; setQa((x) => [...x, { q }]);
    try { const a = await api<AiResult>("/api/ai/ask", { ...cur, question: q }); setQa((x) => x.map((v, j) => (j === i ? { ...v, a } : v))); }
    catch (e) { setQa((x) => x.map((v, j) => (j === i ? { ...v, e: (e as ApiError).message } : v))); }
  };

  const burn = (r?.burn || []).map(fin);
  const hist = (r?.history?.units || []).map(fin), avg = hist.length ? hist.reduce((a, b) => a + b, 0) / hist.length : 0;
  const fm = Math.max(1, ...(r?.frontier || []).map((f) => Math.abs(f.net_gp)));
  const wm = Math.max(1, fin(r?.incr_gp), fin(r?.leakage)), other = Math.max(0, fin(r?.incr_gp) - fin(r?.leakage) - fin(r?.net_gp));
  const list = (a?: string[]) => (a?.length ? <ul className="bul">{a.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="muted">Nothing to add.</p>);

  return (
    <>
      <PageHeader title="Planner" sub="Set up a promotion and see the decision, the stock outlook and the reasons before you send it for approval."
        actions={<>
          {pin ? <button className="btn" onClick={() => setPin(null)}><Icon n="x" s={15} />Stop comparing</button>
            : <button className="btn" disabled={!r} onClick={() => { if (r) { setPin({ key, r, label: `${offerName} in ${cityName}` }); toast("Saved as the comparison. Change something to see the difference."); } }}><Icon n="bookmark" s={15} />Compare against this</button>}
          <button className="btn primary" disabled={blocked || busy || sending || !r} onClick={send} title={blocked ? "Blocked promotions can't be sent" : undefined}><Icon n="send" s={15} />{sending ? "Sending" : "Send for approval"}</button>
        </>} />

      <div className="planner">
        <Panel title="Promotion" className="sticky">
          <div className="form">
            <div className="field"><label htmlFor="f-sku">Product</label>
              <select id="f-sku" value={cur.sku} onChange={(e) => set({ sku: e.target.value })}>{meta.products.map((p) => <option key={p.sku} value={p.sku}>{p.name}</option>)}</select></div>
            <div className="field"><span id="f-offer">Discount</span>
              <div className="offers" role="radiogroup" aria-labelledby="f-offer">
                {meta.offers.map((o, i) => <button key={i} role="radio" aria-checked={i === cur.offer_idx} className={i === cur.offer_idx ? "on" : ""} onClick={() => set({ offer_idx: i })}>{o}</button>)}
              </div></div>
            <div className="field"><label htmlFor="f-seg">Customer group</label>
              <select id="f-seg" value={cur.segment} onChange={(e) => set({ segment: e.target.value })}>{Object.keys(meta.segments).map((s) => <option key={s}>{s}</option>)}</select></div>
            <div className="field"><label htmlFor="f-city">City</label>
              <select id="f-city" value={cur.city} onChange={(e) => set({ city: e.target.value })}>{meta.cities.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
            <div className="field"><label htmlFor="f-ch">Channel</label>
              <select id="f-ch" value={cur.channel} onChange={(e) => set({ channel: e.target.value })}>{meta.channels.map((c) => <option key={c}>{c}</option>)}</select></div>
            <div className="field"><label htmlFor="f-cap">Unit limit</label>
              <input id="f-cap" type="number" min={1} placeholder="No limit" defaultValue={cur.cap ?? ""} key={`cap-${cur.cap}`} onBlur={(e) => {
                const v = Math.round(+e.target.value);
                if (e.target.value && !(v > 0)) { toast("A unit limit has to be a positive number, so it was removed"); set({ cap: null }); } else set({ cap: v > 0 ? v : null });
              }} /><span className="hint">Caps how many units sell at the offer price.</span></div>
          </div>
          <p className="sentence"><b>{offerName}</b> on {product?.name} ({catName(product?.cat)}) for {cur.segment} in {cityName}, {meta.windows[cur.window]?.name}, by {cur.channel}{cur.cap ? `, limited to ${num(cur.cap)} units` : ""}.</p>
        </Panel>

        <div className="stack">
          <Panel className="model" title="Stock through the promotion" sub={r?.insights?.burn || "Each carton is a tenth of the opening stock"}
            actions={<button className="icon-btn" onClick={() => setReset((x) => x + 1)} aria-label="Reset the 3D view" title="Reset view"><Icon n="rotate" s={15} /></button>} flush>
            <div className="stage" style={{ ["--h" as string]: "380px" }}>
              {burn.length ? <StockRunway start={fin(r?.stock) || burn[0]} burn={burn} inbound={r?.inbound} reset={reset} />
                : <div className="stage-fallback">{r ? "No stock data for this product in this city." : "Projecting stock"}</div>}
              <div className="stage-legend top"><span><i style={{ background: "#d4b48a" }} />Stock left</span><span><i style={{ background: "var(--marigold)" }} />Under a quarter left</span><span><i style={{ background: "var(--sindoor)" }} />Sold out</span></div>
            </div>
          </Panel>

          <Panel title="Why this decision">
            {r ? <div className="why">
              <div><h3 style={{ color: "var(--leaf)" }}>What supports it</h3>{list(r.drivers)}</div>
              <div>
                {r.blocks.length > 0 && <><h3 style={{ color: "var(--sindoor)" }}>Rules it breaks</h3>{list(r.blocks)}</>}
                {r.risks.length > 0 && <><h3 style={{ color: "var(--amber)", marginTop: r.blocks.length ? 14 : 0 }}>Risks</h3>{list(r.risks)}</>}
                <h3 style={{ marginTop: r.blocks.length || r.risks.length ? 14 : 0 }}>What would change it</h3>{list(r.what_would_change)}
              </div>
            </div> : <Skeleton />}
          </Panel>

          {r && (
            <section className="panel">
              <nav className="tabs in-panel" role="tablist" aria-label="Detail">
                {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
              </nav>
              <div className="panel-b" role="tabpanel">
                {tab === "breakdown" && <div className="why">
                  <div><h3>Other discount levels</h3><p className="muted small" style={{ margin: "2px 0 12px" }}>{r.insights?.frontier}</p>
                    {(r.frontier || []).map((f, i) => <HBar key={i} hl={i === cur.offer_idx} label={<>{f.offer}{i === cur.offer_idx ? " (current)" : ""}</>} right={inr(f.net_gp)} pct={(Math.abs(f.net_gp) / fm) * 100} color={f.net_gp < 0 ? "var(--sindoor)" : i === cur.offer_idx ? "var(--accent)" : "var(--line-2)"} />)}</div>
                  <div><h3>Where the profit goes</h3><p className="muted small" style={{ margin: "2px 0 12px" }}>{r.insights?.waterfall}</p>
                    <HBar label="Profit from extra sales" right={inr(r.incr_gp)} pct={100} color="var(--leaf)" />
                    <HBar label="Discount to people who'd buy anyway" right={`− ${inr(r.leakage)}`} pct={(r.leakage / wm) * 100} color="var(--sindoor)" />
                    <HBar label="Messages and stock-out costs" right={`− ${inr(other)}`} pct={(other / wm) * 100} color="var(--amber)" />
                    <HBar hl label={r.net_gp < 0 ? "Money lost" : "Profit kept"} right={inr(r.net_gp)} pct={(Math.abs(r.net_gp) / wm) * 100} color={r.net_gp < 0 ? "var(--sindoor)" : "var(--accent)"} /></div>
                </div>}
                {tab === "history" && <>
                  <p className="muted small" style={{ marginBottom: 12 }}>{r.insights?.history}</p>
                  <div className="chart">{hist.some((v) => v > 0) ? <Bar key={theme + key} data={{ labels: r.history!.weeks, datasets: [
                    { label: "Last 8 weeks", data: hist.map((v, i) => (i >= hist.length - 8 ? v : null)), backgroundColor: cssVar("--accent"), borderRadius: 2, grouped: false },
                    { label: "Earlier weeks", data: hist.map((v, i) => (i < hist.length - 8 ? v : null)), backgroundColor: cssVar("--line-2"), borderRadius: 2, grouped: false },
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    { type: "line" as any, label: "Weekly average", data: hist.map(() => avg), borderColor: cssVar("--marigold"), borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0 } as any] }}
                    options={{ plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } }, scales: { x: { ticks: { maxTicksLimit: 8 }, grid: { display: false } }, y: { beginAtZero: true, title: { display: true, text: "Units a week" } } } }} />
                    : <div className="chart-empty">No sales history for this city and product type yet.</div>}</div>
                </>}
                {tab === "similar" && <>
                  <p className="muted small" style={{ marginBottom: 8 }}>{r.insights?.twins}</p>
                  {r.twins?.length ? <table><thead><tr><th>Past promotion</th><th className="r">Forecast return</th><th className="r">Actual return</th><th>Result</th></tr></thead>
                    <tbody>{r.twins.map((t, i) => <tr key={i}><td><b>{t.name}</b></td><td className="r num">{t.pred_roi}×</td><td className="r num">{t.actual_roi}×</td><td><span className={`badge ${t.actual_roi >= t.pred_roi ? "green" : "amber"}`}><i />{t.actual_roi >= t.pred_roi ? "Beat forecast" : "Fell short"}</span></td></tr>)}</tbody></table>
                    : <p className="muted">No similar promotions on record.</p>}
                </>}
                {tab === "kit" && <>
                  <p className="muted" style={{ marginBottom: 12 }}>A manager summary, customer messages (including Hindi) and talking points for store staff, written from the figures above.</p>
                  <button className="btn" onClick={writeKit} disabled={kitBusy}><Icon n="doc" s={15} />{kitBusy ? "Writing" : kit ? "Write again" : "Write the campaign kit"}</button>
                  {kit && <div style={{ display: "grid", gap: 18, marginTop: 18 }}>
                    <div><h3>For the manager</h3><p style={{ marginTop: 4 }}><TypeIn text={String(kit.summary || "")} /></p></div>
                    <div><h3>Customer message</h3>
                      <div className="seg" role="tablist" style={{ margin: "8px 0 10px" }}>{MESSAGES.map(([k, l]) => <button key={k} role="tab" aria-selected={msg === k} className={msg === k ? "on" : ""} onClick={() => setMsg(k)}>{l}</button>)}</div>
                      <div className="bubble"><TypeIn text={String(kit[msg] || "")} /></div>
                      <button className="link" style={{ marginTop: 8 }} onClick={() => navigator.clipboard?.writeText(String(kit[msg] || "")).then(() => toast("Message copied"), () => toast("Copying isn't available in this browser"))}>Copy message</button></div>
                    <div><h3>Talking points for store staff</h3><ul className="bul">{((kit.talking_points as string[]) || []).map((t, i) => <li key={i}>{t}</li>)}</ul></div>
                    <p className={`note ${kit.source === "ai" ? "ok" : ""}`}>{kit.note}</p>
                  </div>}
                </>}
                {tab === "ask" && <>
                  <div className="toolbar" style={{ marginBottom: 10 }}>{QUESTIONS.map((q) => <button key={q} className="btn sm" onClick={() => ask(q)}>{q}</button>)}</div>
                  <form className="toolbar" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
                    <input className="input" style={{ flex: 1, minWidth: 220 }} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about this promotion" aria-label="Your question" />
                    <button className="btn primary" disabled={!question.trim()}>Ask</button>
                  </form>
                  <div style={{ marginTop: 10 }}>{qa.map((x, i) => <div key={i} className="qa"><b>{x.q}</b>{x.e ? <span className="note">{x.e}</span> : x.a ? <><span><TypeIn text={String(x.a.answer || "")} /></span><span className={`note ${x.a.source === "ai" ? "ok" : ""}`}>{x.a.note}</span></> : <span className="muted">Working it out</span>}</div>)}</div>
                </>}
              </div>
            </section>
          )}
        </div>

        <div className="decision-col">
          <aside key={flash} className={`panel decision sticky ${flash ? "flash" : ""}`} style={{ ["--c" as string]: V.color, opacity: busy ? 0.65 : 1 }} aria-live="polite">
            {err ? <div className="panel-b"><ErrorBox msg={err} retry={() => run(cur)} /></div> : !r ? <div className="panel-b"><Skeleton lines={7} /></div> : <>
              <div className="decision-sec">
                <h3>Decision</h3>
                <div className="decision-word">{V.label}</div>
                <p className="small" style={{ color: "var(--ink-2)" }}>{blocked && r.blocks[0] ? r.blocks[0] + "." : V.text}</p>
                <div className="kv" style={{ marginTop: 10 }}><span>Confidence<Tip k="confidence" /></span><b>{rd}<span className="muted small">/100</span><Meter v={rd} /></b></div>
              </div>
              <div className="decision-sec">
                <h3>Forecast{base ? `, against ${pin!.label}` : ""}</h3>
                <div className="kv"><span>Extra profit<Tip k="profit" /></span><b style={{ color: r.net_gp < 0 ? "var(--sindoor)" : undefined }}><Tween value={r.net_gp} fmt="inr" />{delta(r.net_gp, base?.net_gp, inr, "up")}</b></div>
                <div className="kv"><span>Extra units<Tip k="units" /></span><b><Tween value={r.incr_units} />{delta(r.incr_units, base?.incr_units, num, "up")}</b></div>
                <div className="kv"><span>Sell-out risk<Tip k="stockout" /></span><b style={{ color: r.p_stockout > 0.2 ? "var(--sindoor)" : undefined }}><Tween value={r.p_stockout * 100} fmt="pct0" />{delta(r.p_stockout * 100, base ? base.p_stockout * 100 : undefined, (v) => `${v.toFixed(0)} pts`, "down")}</b></div>
                <div className="kv"><span>Wasted discount<Tip k="wasted" /></span><b><Tween value={r.leakage} fmt="inr" />{delta(r.leakage, base?.leakage, inr, "down")}</b></div>
              </div>
              <div className="decision-sec">
                <h3>Checks</h3>
                <div className="checks">{CHECKS.map(([k, n]) => { const v = Math.round(fin(r.scores?.[k])); return <div key={k} className="check"><span>{n}</span><Meter v={v} /><b className="num">{v}</b></div>; })}</div>
              </div>
              <div className="decision-sec"><Verdict v={r.verdict} /> <span className="muted small" style={{ marginLeft: 6 }}>{blocked ? "Fix the rule above to send it." : "Marketing, Merchandising and Store Ops review it next."}</span></div>
            </>}
          </aside>
        </div>
      </div>
    </>
  );
}
