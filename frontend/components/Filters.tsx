"use client";
import { useApp } from "./AppState";
import { Seg } from "./ui";
import { GOALS, catName } from "@/lib/api";

/** Goal, city and product-type filters shared by the promotion lists. */
export default function Filters() {
  const { meta, objective, setObjective, city, setCity, cat, setCat } = useApp();
  const cats = meta ? [...new Set(meta.products.map((p) => p.cat))].sort() : [];
  return <>
    <Seg label="Rank by" value={objective} set={setObjective} opts={GOALS} />
    <select className="select" value={city} onChange={(e) => setCity(e.target.value)} aria-label="City"><option value="">All cities</option>{meta?.cities.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}</select>
    <select className="select" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Product type"><option value="">All product types</option>{cats.map((c) => <option key={c} value={c}>{catName(c)}</option>)}</select>
    {(city || cat) && <button className="btn ghost sm" onClick={() => { setCity(""); setCat(""); }}>Clear filters</button>}
  </>;
}
