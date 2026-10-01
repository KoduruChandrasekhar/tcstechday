"use client";
// The store network as a scale model: India as a raised plate, one tower per city.
// Tower height = festival demand, footprint = number of stores, colour = how many products are about to run short.
import { useFrame } from "@react-three/fiber";
import { QuadraticBezierLine, RoundedBox } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { shortLevel, type CityLight } from "@/lib/api";
import Stage, { stillMotion, useModel, type Label } from "./Stage";

const K = 0.36, LON0 = 81.8, LAT0 = 22.4, PLATE = 0.2;
const toXZ = (lat: number, lon: number): [number, number] => [(lon - LON0) * K, -(lat - LAT0) * K];

// Simplified mainland outline (lon, lat), clockwise from Kutch. Stylised, not survey-accurate.
const INDIA: [number, number][] = [
  [68.2, 23.6], [69.1, 22.4], [70.4, 20.9], [71.6, 20.7], [72.6, 21.4], [72.9, 20.2], [72.8, 18.9], [73.4, 16.6], [73.9, 15.2],
  [74.7, 13.0], [75.8, 11.2], [76.3, 9.6], [77.5, 8.1], [78.2, 8.9], [79.3, 10.3], [79.9, 12.0], [80.3, 13.4], [80.1, 15.4],
  [81.2, 16.3], [82.4, 17.1], [83.4, 17.8], [85.1, 19.5], [86.9, 20.6], [87.6, 21.7], [88.8, 21.6], [89.0, 22.6], [88.7, 24.2],
  [88.1, 25.5], [88.3, 26.3], [89.9, 26.0], [92.0, 25.2], [92.3, 24.2], [92.8, 22.6], [93.4, 23.8], [94.2, 24.5], [95.0, 26.3],
  [96.2, 27.3], [97.3, 28.2], [96.0, 29.4], [94.4, 29.2], [92.4, 27.9], [91.6, 26.9], [89.8, 26.8], [88.9, 27.3], [88.6, 28.0],
  [88.1, 27.6], [88.1, 26.6], [86.0, 26.6], [84.3, 27.2], [83.3, 27.4], [81.6, 28.0], [80.1, 28.8], [80.9, 30.2], [79.1, 31.3],
  [78.8, 32.5], [79.5, 33.3], [78.4, 34.6], [77.8, 35.5], [76.2, 35.8], [74.6, 35.0], [73.8, 34.3], [74.0, 33.2], [74.7, 32.6],
  [75.3, 32.2], [74.6, 31.0], [73.9, 30.0], [73.3, 29.6], [72.3, 28.1], [70.8, 27.8], [70.0, 27.0], [69.6, 26.4], [70.1, 25.6],
  [70.8, 25.0], [71.0, 24.4], [69.6, 24.3], [68.8, 24.0],
];

function Plate() {
  const m = useModel();
  const { geo, line } = useMemo(() => {
    const pts = INDIA.map(([lon, lat]) => { const [x, z] = toXZ(lat, lon); return new THREE.Vector2(x, -z); });
    const geo = new THREE.ExtrudeGeometry(new THREE.Shape(pts), { depth: PLATE, bevelEnabled: true, bevelThickness: 0.025, bevelSize: 0.025, bevelSegments: 2 });
    const line = new THREE.BufferGeometry().setFromPoints([...pts, pts[0]].map((p) => new THREE.Vector3(p.x, PLATE + 0.027, -p.y)));
    return { geo, line };
  }, []);
  const outline = useMemo(() => new THREE.Line(line, new THREE.LineBasicMaterial({ color: m.outline })), [line, m.outline]);
  return (
    <group>
      <mesh geometry={geo} rotation-x={-Math.PI / 2} castShadow receiveShadow>
        <meshStandardMaterial attach="material-0" color={m.plate} roughness={0.95} />
        <meshStandardMaterial attach="material-1" color={m.side} roughness={0.95} />
      </mesh>
      <primitive object={outline} />
    </group>
  );
}

function Arc({ from, to, still }: { from: [number, number]; to: [number, number]; still: boolean }) {
  const m = useModel();
  const ref = useRef<{ material: { dashOffset: number } } | null>(null);
  const [ax, az] = toXZ(from[0], from[1]), [bx, bz] = toXZ(to[0], to[1]);
  const top = PLATE + 0.04, len = Math.hypot(bx - ax, bz - az);
  // dashes drift from source to destination, so the direction of the move reads without arrowheads
  useFrame((_, dt) => { if (!still && ref.current) ref.current.material.dashOffset -= dt * 0.5; });
  return <QuadraticBezierLine ref={ref as never} start={[ax, top, az]} end={[bx, top, bz]} mid={[(ax + bx) / 2, top + 0.4 + len * 0.3, (az + bz) / 2]}
    color={m.arc} lineWidth={2} dashed dashSize={0.14} gapSize={0.09} />;
}

interface Max { demand: number; short: number; stores: number }
const dims = (c: CityLight, mx: Max) => ({ h: 0.25 + 2.3 * Math.sqrt(c.demand / Math.max(mx.demand, 1e-6)), w: 0.2 + 0.16 * Math.sqrt(c.stores / Math.max(mx.stores, 1)) });

interface TowerProps { c: CityLight; i: number; mx: Max; selected: boolean; still: boolean; onSelect?: (n: string) => void }
function Tower({ c, i, mx, selected, still, onSelect }: TowerProps) {
  const m = useModel();
  const [x, z] = toXZ(c.lat, c.lon);
  const { h, w } = dims(c, mx), maxShort = mx.short;
  const lvl = shortLevel(c.short, maxShort), color = [m.clay, m.warm, m.hot][lvl];
  const g = useRef<THREE.Group>(null), t0 = useRef<number | null>(null);
  const [hover, setHover] = useState(false);

  useFrame(({ clock }) => {
    if (!g.current) return;
    if (t0.current === null) t0.current = clock.elapsedTime;
    const p = still ? 1 : Math.min(1, Math.max(0, (clock.elapsedTime - t0.current - 0.15 - i * 0.06) / 0.9));
    const e = 1 - Math.pow(1 - p, 3);
    g.current.scale.y = Math.max(0.001, e);
  });

  return (
    <group position={[x, PLATE + 0.025, z]}>
      {selected && (
        <mesh rotation-x={-Math.PI / 2} position-y={0.004}>
          <ringGeometry args={[w * 0.95, w * 1.25, 40]} />
          <meshBasicMaterial color={m.warm} />
        </mesh>
      )}
      <group ref={g}>
        <RoundedBox args={[w, h, w]} radius={0.03} smoothness={3} position-y={h / 2} castShadow receiveShadow
          onClick={onSelect ? (e) => { e.stopPropagation(); onSelect(c.name); } : undefined}
          onPointerOver={onSelect ? (e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; } : undefined}
          onPointerOut={onSelect ? () => { setHover(false); document.body.style.cursor = ""; } : undefined}>
          <meshStandardMaterial color={color} roughness={0.7} emissive={color} emissiveIntensity={hover || selected ? 0.22 : 0} />
        </RoundedBox>
      </group>
    </group>
  );
}

export interface NetworkMapProps { lights: CityLight[]; selected?: string; onSelect?: (name: string) => void; arcs?: { from: [number, number]; to: [number, number] }[]; reset?: number }

export default function NetworkMap({ lights, selected, onSelect, arcs = [], reset = 0 }: NetworkMapProps) {
  const [still] = useState(stillMotion);
  const mx: Max = { demand: Math.max(...lights.map((l) => l.demand), 1), short: Math.max(...lights.map((l) => l.short), 0), stores: Math.max(...lights.map((l) => l.stores), 1) };
  const labels: Label[] = lights.map((c) => {
    const [x, z] = toXZ(c.lat, c.lon), { h } = dims(c, mx), on = selected === c.name;
    return { key: c.name, pos: [x, PLATE + h + 0.2, z], node: (
      <button type="button" className={`map-label ${on ? "on" : ""} ${onSelect ? "" : "static"}`} tabIndex={onSelect ? 0 : -1} onClick={() => onSelect?.(c.name)}
        aria-pressed={onSelect ? on : undefined} aria-label={`${c.name}: ${c.short} products running short, ${c.stores} stores`}>
        {c.name}{on && <small>{c.short} short</small>}
      </button>
    ) };
  });
  return (
    <Stage label="3D model of the store network: one tower per city, taller for more festival demand, amber or red where products are running short"
      fit={{ w: 5.35, d: 4.85, el: 42, az: 0, target: [0.35, 0.55, 0.7] }} reset={reset} labels={labels}>
      <Plate />
      {arcs.map((a, i) => <Arc key={i} from={a.from} to={a.to} still={still} />)}
      {lights.map((c, i) => (
        <Tower key={c.name} c={c} i={i} mx={mx} selected={selected === c.name} still={still} onSelect={onSelect} />
      ))}
    </Stage>
  );
}
