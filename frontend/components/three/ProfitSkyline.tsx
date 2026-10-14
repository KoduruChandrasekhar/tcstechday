"use client";
// Recommended promotions as a row of blocks: height = extra profit, so the ranking reads as a skyline.
// Linked to the table beside it: hovering either one lifts the same promotion.
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { useRef, useState } from "react";
import * as THREE from "three";
import { inr } from "@/lib/api";
import Stage, { stillMotion, useModel, type Label } from "./Stage";

export interface SkyRow { id: string; rank: number; net_gp: number; offer: string; product: string; city_name: string }
const STEP = 0.78, W = 0.52, TALLEST = 2.4;

function Block({ r, i, x, h, on, hl, still, onHover, onSelect }: { r: SkyRow; i: number; x: number; h: number; on: boolean; hl: boolean; still: boolean; onHover: (id: string) => void; onSelect: (id: string) => void }) {
  const m = useModel();
  const g = useRef<THREE.Group>(null), t0 = useRef<number | null>(null), lift = useRef(0);
  const color = r.net_gp < 0 ? m.hot : hl ? m.warm : m.clay;
  useFrame(({ clock }, dt) => {
    if (!g.current) return;
    if (t0.current === null) t0.current = clock.elapsedTime;
    const p = still ? 1 : Math.min(1, Math.max(0, (clock.elapsedTime - t0.current - 0.1 - i * 0.045) / 0.8));
    g.current.scale.y = Math.max(0.001, 1 - Math.pow(1 - p, 3));
    // the hovered block rises slightly off the board, answering the pointer
    lift.current += ((on ? 0.12 : 0) - lift.current) * Math.min(1, dt * 12);
    g.current.position.y = 0.08 + lift.current;
  });
  return (
    <group ref={g} position={[x, 0.08, 0]}>
      <RoundedBox args={[W, h, W]} radius={0.03} smoothness={3} position-y={h / 2} castShadow receiveShadow
        onPointerOver={(e) => { e.stopPropagation(); onHover(r.id); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { onHover(""); document.body.style.cursor = ""; }}
        onClick={(e) => { e.stopPropagation(); onSelect(r.id); }}>
        <meshStandardMaterial color={color} roughness={0.7} emissive={color} emissiveIntensity={on ? 0.18 : 0} />
      </RoundedBox>
    </group>
  );
}

export default function ProfitSkyline({ rows, active, onHover, onSelect, reset = 0 }: { rows: SkyRow[]; active: string; onHover: (id: string) => void; onSelect: (id: string) => void; reset?: number }) {
  const m = useModel();
  const [still] = useState(stillMotion);
  const n = Math.max(rows.length, 1), x0 = -((n - 1) * STEP) / 2;
  const top = Math.max(...rows.map((r) => Math.abs(r.net_gp)), 1);
  const hOf = (r: SkyRow) => 0.12 + TALLEST * (Math.abs(r.net_gp) / top);
  const labels: Label[] = rows.flatMap((r, i) => {
    const x = x0 + i * STEP, on = active === r.id;
    const out: Label[] = [{ key: `r${r.id}`, pos: [x, 0, W / 2 + 0.3], node: <span className={`sky-rank ${on ? "on" : ""}`}>{r.rank}</span> }];
    if (on || (!active && r.rank === 1)) out.push({ key: `v${r.id}`, pos: [x, 0.08 + hOf(r) + (on ? 0.12 : 0) + 0.28, 0], node: (
      <span className="sky-tip"><b>{inr(r.net_gp)}</b><small>{r.offer} on {r.product}, {r.city_name}</small></span>
    ) });
    return out;
  });
  return (
    <Stage label={`3D skyline of ${rows.length} recommended promotions; taller blocks add more profit`} reset={reset} turn={0.5} shadowBox={8} labels={labels}
      fit={{ w: (n * STEP) / 2 + 1.1, d: 2.1, el: 22, az: -9, target: [0, 1.15, 0] }}>
      <RoundedBox args={[n * STEP + 0.4, 0.08, W + 0.7]} radius={0.03} position-y={0.04} receiveShadow>
        <meshStandardMaterial color={m.plate} roughness={0.95} />
      </RoundedBox>
      {rows.map((r, i) => <Block key={r.id} r={r} i={i} x={x0 + i * STEP} h={hOf(r)} on={active === r.id} hl={active ? active === r.id : r.rank === 1} still={still} onHover={onHover} onSelect={onSelect} />)}
    </Stage>
  );
}
