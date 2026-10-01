"use client";
// Stock through the promotion as stacked cartons: one stack per day, each carton a tenth of the opening stock.
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three-stdlib";
import { num } from "@/lib/api";
import Stage, { stillMotion, useModel, type Label } from "./Stage";

const SLOTS = 10, CW = 0.6, CH = 0.26, CD = 0.5, GAP = 0.86;

function Stack({ x, count, color, tape, still }: { x: number; count: number; color: string; tape: string; still: boolean }) {
  const geo = useMemo(() => new RoundedBoxGeometry(CW, CH * 0.94, CD, 2, 0.025), []);
  const mat = useMemo(() => new THREE.MeshStandardMaterial({ color, roughness: 0.9 }), [color]);
  const tapeMat = useMemo(() => new THREE.MeshStandardMaterial({ color: tape, roughness: 0.6 }), [tape]);
  const refs = useRef<(THREE.Group | null)[]>([]);
  // each carton eases toward shown or hidden, top first, so a change in stock reads as cartons arriving or leaving
  useFrame((_, dt) => {
    refs.current.forEach((g, i) => {
      if (!g) return;
      const want = i < count ? 1 : 0, k = still ? 1 : Math.min(1, dt * (10 - Math.abs(i - count) * 0.4));
      const s = g.scale.x + (want - g.scale.x) * Math.max(0.05, k);
      g.scale.setScalar(Math.abs(s - want) < 0.002 ? want : s);
      g.visible = g.scale.x > 0.01;
    });
  });
  return (
    <group position-x={x}>
      {Array.from({ length: SLOTS }, (_, i) => (
        <group key={i} ref={(el) => { refs.current[i] = el; }} position-y={0.06 + CH * (i + 0.5)} scale={0.001} rotation-y={(i % 3 - 1) * 0.025}>
          <mesh geometry={geo} material={mat} castShadow receiveShadow />
          <mesh position-y={CH * 0.47} material={tapeMat}><boxGeometry args={[0.1, 0.006, CD * 1.002]} /></mesh>
        </group>
      ))}
    </group>
  );
}

export interface RunwayProps { start: number; burn: number[]; inbound?: { day: number; qty: number }[]; reset?: number }

export default function StockRunway({ start, burn, inbound = [], reset = 0 }: RunwayProps) {
  const m = useModel();
  const [still] = useState(stillMotion);
  const top = Math.max(start, ...burn, 1), n = burn.length, x0 = -((n - 1) * GAP) / 2;
  const arrivals = new Map(inbound.map((b) => [b.day, b.qty]));
  const cells = burn.map((u, i) => ({ u, x: x0 + i * GAP, count: u <= 0 ? 0 : Math.max(1, Math.round((u / top) * SLOTS)), low: u > 0 && u / Math.max(start, 1) < 0.25 }));
  const labels: Label[] = cells.flatMap(({ u, x, count, low }, i) => [
    { key: `v${i}`, pos: [x, 0.06 + CH * count + 0.22, 0], node: <span className={`stack-label ${u <= 0 ? "out" : low ? "low" : ""}`}>{u <= 0 ? "Sold out" : num(u)}</span> },
    { key: `d${i}`, pos: [x, 0, CD / 2 + 0.36], node: <span className="stack-day">Day {i + 1}{arrivals.has(i + 1) && <b>+{num(arrivals.get(i + 1))} arrive</b>}</span> },
  ]);
  return (
    <Stage label={`3D stack of cartons showing stock left at the end of each of ${n} days`} reset={reset} turn={0.6} shadowBox={6} labels={labels}
      fit={{ w: (n * GAP) / 2 + 0.5, d: 2.2, el: 24, az: -22, target: [0, 1.2, 0] }}>
      <RoundedBox args={[n * GAP + 0.5, 0.06, CD + 0.6]} radius={0.02} position-y={0.03} receiveShadow>
        <meshStandardMaterial color={m.plate} roughness={0.95} />
      </RoundedBox>
      {cells.map(({ u, x, count, low }, i) => {
        return (
          <group key={i}>
            <Stack x={x} count={count} color={low ? m.warm : m.kraft} tape={m.tape} still={still} />
            {u <= 0 && (
              <mesh position={[x, 0.065, 0]} rotation-x={-Math.PI / 2}><planeGeometry args={[CW, CD]} /><meshBasicMaterial color={m.hot} transparent opacity={0.85} /></mesh>
            )}
          </group>
        );
      })}
    </Stage>
  );
}
