"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppState";
import { Tip } from "@/components/fx";
import { Answer, BarRow, ErrorBox, Icon, PageHead, Pager, Skeleton } from "@/components/ui";
import { api, fin, num, specOf, ApiError } from "@/lib/api";

interface Aud {
  segments: { segment: string; size: number; persuadable: number; treated: number; control: number; lift: number; top_categories: string[] }[];
  model: { train_rows: number; treated: number; control: number; obs_uplift_top30_pts: number; obs_uplift_rest_pts: number; obs_uplift_all_pts: number };
  dnc: number; chart_insight: string;
}

export default function Customers() {
  const { recs, cur, setCur, win, toast } = useApp();
  const router = useRouter();
  const [d, setD] = useState<Aud | null>(null), [err, setErr] = useState("");
  const load = () => { api<Aud>("/api/audiences").then((x) => { setD(x); setErr(""); }).catch((e: ApiError) => setErr(e.message)); };
  useEffect(() => { load(); }, []);

  const segs = [...(d?.segments || [])].sort((a, b) => b.lift - a.lift), mx = Math.max(0, ...segs.map((s) => fin(s.lift)));
  const top = Math.max(0.0001, ...segs.flatMap((s) => [s.treated, s.control]));
  const build = (g: string) => {
    const best = recs?.top.find((r) => r.segment === g);
    if (best) setCur(specOf(best, win)); else if (cur) setCur({ ...cur, segment: g });
    toast(best ? `Loaded the best pick for ${g}` : `Set customer group to ${g}`); router.push("/build");
  };
  const mc = d?.model, vals: [string, number, string][] = mc ? [["Customers we pick (top 30%)", mc.obs_uplift_top30_pts, "var(--accent)"], ["Everyone else", mc.obs_uplift_rest_pts, "var(--neutral)"], ["If we offered to everyone", mc.obs_uplift_all_pts, "var(--muted)"]] : [];
  const vm = Math.max(0.01, ...vals.map((v) => v[1]));

  return (
    <main>
      <PageHead step={3} title="Who actually needs an offer?" lead="A discount given to someone who would have bought anyway is money lost. We compare people who got an offer with similar people who didn't, to see who an offer really persuades."
        tips={[["Each card is a customer group", "anonymous, consenting customers only."], ["Compare the two bars", "with offer vs without."], ["The gap is what matters", "bigger gap, better offer."]]} />
      {err && <ErrorBox msg={err} retry={load} />}
      <Answer icon="users">{d?.chart_insight || <span className="skel" style={{ display: "block", width: "60%" }} />}</Answer>
      <div className="grid g3">
        {!d && !err && <Skeleton />}
        {d && !segs.length && <div className="card empty" style={{ gridColumn: "1/-1" }}><b>No customer groups available</b>Check that customer data has been generated.</div>}
        {segs.map((s, i) => { const best = s.lift === mx && mx > 0; return (
          <div key={s.segment} className={`segcard rise ${best ? "best" : ""}`} style={{ animationDelay: `${i * 55}ms` }}>
            <div className="row between" style={{ alignItems: "flex-start" }}><div><b>{s.segment}</b><div className="small muted">{num(s.size)} customers</div></div>{best && <span className="pill p-GO">Best response</span>}</div>
            <div className="cmp">
              <div className="r"><span>With offer</span><div className="tr"><i style={{ width: `${(s.treated / top) * 100}%`, background: "var(--accent)" }} /></div><b>{(s.treated * 100).toFixed(1)}%</b></div>
              <div className="r"><span>Without offer</span><div className="tr"><i style={{ width: `${(s.control / top) * 100}%`, background: "var(--neutral)" }} /></div><b>{(s.control * 100).toFixed(1)}%</b></div>
            </div>
            <div className="small">{s.lift > 0 ? <><b style={{ color: "var(--accent)" }}>+{(s.lift * 100).toFixed(1)}%</b> more buy with an offer <Tip k="uplift" /></> : <b>No clear effect from offers</b>} · <b>{(s.persuadable * 100).toFixed(0)}%</b> of the group needs one</div>
            <div className="row">{(s.top_categories || []).map((x) => <span key={x} className="tag">Likes {x.split(" ")[0]}</span>)}</div>
            <button className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={() => build(s.segment)}>Build a promotion for this group <Icon n="arrow" s={14} /></button>
          </div>); })}
      </div>
      {d && <p className="small muted" style={{ marginTop: 14 }}>{num(d.dnc)} customers are never contacted (Do Not Disturb, unsubscribed or no consent).</p>}
      {mc?.train_rows ? <details className="more"><summary><div>How do we know this works?<small>Tested against customers who got no offer</small></div></summary><div className="inner">
        <p className="small muted" style={{ marginTop: 0 }}>We learned from {num(mc.train_rows)} past offers: {num(mc.treated)} people got one, {num(mc.control)} similar people didn&apos;t. Then we checked who bought extra because of the offer.</p>
        <div className="bars" style={{ maxWidth: 640 }}>{vals.map(([l, v, c]) => <BarRow key={l} label={l} right={`+${v}% more buyers`} pct={(v / vm) * 100} color={c} />)}</div>
        <div className="answer" style={{ margin: "16px 0 0" }}><span className="ic"><Icon n="check" /></span><div><div className="lbl">Result</div><p>Offering only to the customers we pick brings {(mc.obs_uplift_top30_pts / Math.max(mc.obs_uplift_all_pts, 0.01)).toFixed(1)}× more extra buyers than offering to everyone.</p></div></div>
      </div></details> : null}
      <Pager step={3} />
    </main>
  );
}
