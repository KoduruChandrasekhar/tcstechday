"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApp } from "./AppState";
import { Tip } from "./fx";
import { Drawer, Icon, Meter, Verdict } from "./ui";
import { api, catName, fin, inr, num, specOf, vk, ApiError } from "@/lib/api";

export const CHECKS: [string, string][] = [["profit", "Makes money"], ["stock", "Stock will last"], ["uplift", "Customers respond"], ["ops", "Stores can cope"], ["fatigue", "Not over-messaged"]];

/** Promotion details in a side panel, opened from any table. */
export default function PromoDrawer() {
  const { peek: r, setPeek, setCur, win, reloadCampaigns, toast } = useApp();
  const router = useRouter();
  const [sending, setSending] = useState(false);
  const close = () => setPeek(null);
  const blocked = r ? vk(r.verdict) === "BLOCK" : false;

  const send = async () => {
    if (!r) return;
    setSending(true);
    try { const c = await api<{ id: string }>("/api/campaigns", specOf(r, win)); reloadCampaigns(); toast(`Sent for approval as ${c.id}`); close(); router.push(`/approvals?c=${c.id}`); }
    catch (e) { toast((e as ApiError).message); }
    setSending(false);
  };
  const list = (a?: string[]) => (a?.length ? <ul className="bul">{a.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="muted">None.</p>);

  return (
    <Drawer open={!!r} onClose={close} title={r ? `${r.offer} on ${r.product}` : ""} sub={r ? `${r.segment} in ${r.city_name}, by ${r.channel}` : ""}
      footer={r && <>
        <button className="btn" onClick={() => { setCur(specOf(r, win)); close(); router.push("/planner"); }}><Icon n="sliders" s={15} />Open in planner</button>
        <button className="btn primary" disabled={blocked || sending} onClick={send} title={blocked ? "Blocked promotions can't be sent. Fix it in the planner first." : undefined}><Icon n="send" s={15} />{sending ? "Sending" : "Send for approval"}</button>
      </>}>
      {r && <>
        <div className="dr-verdict">
          <Verdict v={r.verdict} />
          <span className="muted">Confidence <b className="num">{Math.round(r.readiness)}</b> of 100<Tip k="confidence" /></span>
        </div>
        <div className="figs">
          <div><span>Extra profit<Tip k="profit" /></span><b style={{ color: r.net_gp < 0 ? "var(--sindoor)" : undefined }}>{r.fmt?.net_gp ?? inr(r.net_gp)}</b></div>
          <div><span>Extra units<Tip k="units" /></span><b>{num(r.incr_units)}</b></div>
          <div><span>Sell-out risk<Tip k="stockout" /></span><b style={{ color: r.p_stockout > 0.2 ? "var(--sindoor)" : undefined }}>{Math.round(r.p_stockout * 100)}%</b></div>
          <div><span>Wasted discount<Tip k="wasted" /></span><b>{r.fmt?.leakage ?? inr(r.leakage)}</b></div>
        </div>
        <p className="dr-sentence">{r.sentence}.</p>
        <h3 className="dr-h">Checks</h3>
        <div className="checks">
          {CHECKS.map(([k, n]) => { const v = Math.round(fin(r.scores?.[k])); return <div key={k} className="check"><span>{n}</span><Meter v={v} /><b className="num">{v}</b></div>; })}
        </div>
        {r.blocks?.length > 0 && <><h3 className="dr-h red">Why it is blocked</h3>{list(r.blocks)}</>}
        <h3 className="dr-h">What supports it</h3>{list(r.drivers)}
        {r.risks?.length > 0 && <><h3 className="dr-h">Risks</h3>{list(r.risks)}</>}
        <h3 className="dr-h">What would change the decision</h3>{list(r.what_would_change)}
        <dl className="dl">
          <dt>Product type</dt><dd>{catName(r.category)}</dd>
          <dt>Customers reached</dt><dd className="num">{num(r.reach)}</dd>
          <dt>Stock available</dt><dd className="num">{num(r.available)} units, {r.cover_days} days of cover</dd>
          <dt>Margin after discount</dt><dd className="num">{(r.gp_margin * 100).toFixed(1)}%</dd>
          <dt>Discount given</dt><dd className="num">{r.fmt?.discount_spend ?? inr(r.discount_spend)}</dd>
        </dl>
      </>}
    </Drawer>
  );
}
