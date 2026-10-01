"use client";
// Customer groups as blocks. Footprint = group size. Grey base = buy without an offer; coloured top = extra buyers the offer brings.
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { useRef, useState } from "react";
import * as THREE from "three";
import Stage, { stillMotion, useModel, type Label } from "./Stage";

export interface SegBlock { segment: string; size: number; treated: number; control: number; lift: number }
const TALLEST = 2.5, COLS = 3, STEP = 2.1;

// one linear scale for every block, set by the group most likely to buy, so heights compare honestly
const parts = (s: SegBlock, k: number) => ({ base: Math.max(0.04, Math.min(s.control, s.treated) * k), cap: Math.max(0, (s.treated - s.control) * k) });

function Block({ s, i, x, z, side, k, selected, still, onSelect }: { s: SegBlock; i: number; x: number; z: number; side: number; k: number; selected: boolean; still: boolean; onSelect: (n: string) => void }) {
  const m = useModel();
  const { base, cap } = parts(s, k);
  const g = useRef<THREE.Group>(null), t0 = useRef<number | null>(null);
  const [hover, setHover] = useState(false);
  useFrame(({ clock }) => {
    if (!g.current) return;
    if (t0.current === null) t0.current = clock.elapsedTime;
    const p = still ? 1 : Math.min(1, Math.max(0, (clock.elapsedTime - t0.current - 0.1 - i * 0.08) / 0.8));
    g.current.scale.y = Math.max(0.001, 1 - Math.pow(1 - p, 3));
  });
  const top = selected ? m.warm : m.clay;
  const ev = {
    onClick: (e: { stopPropagation: () => void }) => { e.stopPropagation(); onSelect(s.segment); },
    onPointerOver: (e: { stopPropagation: () => void }) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; },
    onPointerOut: () => { setHover(false); document.body.style.cursor = ""; },
  };
  return (
    <group position={[x, 0.08, z]}>
      {selected && <mesh rotation-x={-Math.PI / 2} position-y={0.003}><ringGeometry args={[side * 0.74, side * 0.84, 4, 1, Math.PI / 4]} /><meshBasicMaterial color={m.warm} /></mesh>}
      <group ref={g}>
        <RoundedBox args={[side, base, side]} radius={0.03} smoothness={3} position-y={base / 2} castShadow receiveShadow {...ev}>
          <meshStandardMaterial color={m.clayLo} roughness={0.9} />
        </RoundedBox>
        {cap > 0.005 && (
          <RoundedBox args={[side, cap, side]} radius={0.03} smoothness={3} position-y={base + cap / 2 + 0.004} castShadow receiveShadow {...ev}>
            <meshStandardMaterial color={top} roughness={0.7} emissive={top} emissiveIntensity={hover ? 0.2 : 0} />
          </RoundedBox>
        )}
      </group>
    </group>
  );
}

export default function SegmentBlocks({ segs, selected, onSelect, reset = 0 }: { segs: SegBlock[]; selected: string; onSelect: (n: string) => void; reset?: number }) {
  const m = useModel();
  const [still] = useState(stillMotion);
  const maxSize = Math.max(...segs.map((s) => s.size), 1), best = Math.max(...segs.map((s) => s.lift)), k = TALLEST / Math.max(...segs.map((s) => s.treated), 1e-6);
  const rows = Math.ceil(segs.length / COLS), w = COLS * STEP, d = rows * STEP;
  const at = (i: number): [number, number] => [((i % COLS) - (COLS - 1) / 2) * STEP, (Math.floor(i / COLS) - (rows - 1) / 2) * STEP];
  const labels: Label[] = segs.map((s, i) => {
    const [x, z] = at(i), { base, cap } = parts(s, k), on = selected === s.segment;
    return { key: s.segment, pos: [x, 0.08 + base + cap + 0.3, z], node: (
      <button type="button" className={`map-label seg-label ${on ? "on" : ""}`} onClick={() => onSelect(s.segment)} aria-pressed={on}>
        {s.segment}<small>{s.lift > 0 ? `+${(s.lift * 100).toFixed(1)} per 100` : "No clear lift"}{s.lift === best && best > 0 ? ", best" : ""}</small>
      </button>
    ) };
  });
  return (
    <Stage label="3D blocks, one per customer group: wider for bigger groups, the coloured top shows extra buyers per 100 when given an offer" reset={reset} turn={0.7} shadowBox={6}
      fit={{ w: w / 2 + 0.4, d: d / 2 + 0.9, el: 34, az: -18, target: [0, 0.9, 0.1] }} labels={labels}>
      <RoundedBox args={[w + 0.3, 0.08, d + 0.3]} radius={0.03} position-y={0.04} receiveShadow>
        <meshStandardMaterial color={m.plate} roughness={0.95} />
      </RoundedBox>
      {segs.map((s, i) => {
        const [x, z] = at(i);
        return <Block key={s.segment} s={s} i={i} x={x} z={z} side={0.55 + 1.05 * Math.sqrt(s.size / maxSize)} k={k} selected={selected === s.segment} still={still} onSelect={onSelect} />;
      })}
    </Stage>
  );
}
