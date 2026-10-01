"use client";
// Shared set-up for every 3D view: the business shown as a matte scale model on a table, lit from the top left.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { OrbitControls as OC } from "three-stdlib";
import { useApp } from "../AppState";

export const MODEL = {
  light: { plate: "#e6e1ee", side: "#cbc2d9", outline: "#9d8fb5", clay: "#6d4ea8", clayLo: "#b7aecb", warm: "#e09a2b", hot: "#c4412f",
    kraft: "#d4b48a", tape: "#b8925f", leaf: "#2f7d5b", arc: "#5b2f91", shadow: 0.16 },
  dark: { plate: "#3e3556", side: "#272036", outline: "#7d6fa0", clay: "#9c80da", clayLo: "#4d4563", warm: "#f0b04a", hot: "#ef7a6c",
    kraft: "#b3946b", tape: "#8c6f4b", leaf: "#5fbf8c", arc: "#c9b3e6", shadow: 0.4 },
};
export const useModel = () => MODEL[useApp().theme === "dark" ? "dark" : "light"];

export const stillMotion = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** A DOM label pinned to a point in the scene. Plain DOM keeps text crisp and lets labels be real buttons. */
export interface Label { key: string; pos: [number, number, number]; node: React.ReactNode }

/**
 * Places the camera so a box of the given half-width and half-depth fills the view at any panel shape,
 * from a fixed elevation and turn. Re-runs when the panel resizes or `reset` changes.
 */
function Fit({ w, d, el, az, target: [tx, ty, tz], reset }: { w: number; d: number; el: number; az: number; target: [number, number, number]; reset: number }) {
  const { camera, size, invalidate } = useThree();
  const controls = useThree((s) => s.controls) as unknown as OC | null;
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera, aspect = size.width / Math.max(size.height, 1);
    const v = THREE.MathUtils.degToRad(cam.fov) / 2, h = Math.atan(Math.tan(v) * aspect);
    const dist = Math.max(w / Math.tan(h), d / Math.tan(v));
    const e = THREE.MathUtils.degToRad(el), a = THREE.MathUtils.degToRad(az), t = new THREE.Vector3(tx, ty, tz);
    cam.position.set(t.x + dist * Math.cos(e) * Math.sin(a), t.y + dist * Math.sin(e), t.z + dist * Math.cos(e) * Math.cos(a));
    cam.lookAt(t);
    if (controls) { controls.target.copy(t); controls.update(); }
    invalidate();
  }, [camera, size, controls, invalidate, w, d, el, az, tx, ty, tz, reset]);
  return null;
}

/** Moves each label's DOM node to its projected screen position, every frame, without React renders. */
function Projector({ labels, nodes }: { labels: Label[]; nodes: React.RefObject<Map<string, HTMLDivElement>> }) {
  const v = useRef(new THREE.Vector3());
  useFrame(({ camera, size }) => {
    for (const l of labels) {
      const el = nodes.current.get(l.key);
      if (!el) continue;
      v.current.set(...l.pos).project(camera);
      const x = (v.current.x + 1) / 2 * size.width, y = (1 - v.current.y) / 2 * size.height;
      el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -50%)`;
      el.style.visibility = v.current.z < 1 ? "visible" : "hidden";
    }
  });
  return null;
}

export interface StageProps {
  children: React.ReactNode; label: string; fit: { w: number; d: number; el: number; az?: number; target: [number, number, number] };
  reset?: number; turn?: number; shadowBox?: number; labels?: Label[];
}

export default function Stage({ children, label, fit, reset = 0, turn = 0.8, shadowBox = 8, labels = [] }: StageProps) {
  const [ok] = useState(() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; } });
  const [still] = useState(stillMotion);
  const [fine] = useState(() => matchMedia("(pointer: fine)").matches);
  const nodes = useRef(new Map<string, HTMLDivElement>());
  const dark = useApp().theme === "dark";
  if (!ok) return <div className="stage-fallback">This browser can&apos;t draw 3D views. The table alongside has the same figures.</div>;
  return (
    <div className="stage-3d">
      <Canvas shadows="percentage" flat dpr={[1, 2]} frameloop={still ? "demand" : "always"} camera={{ fov: 32, near: 0.1, far: 120 }} gl={{ antialias: true, alpha: true }} aria-label={label} role="img">
        <hemisphereLight args={[dark ? "#b9a8d9" : "#ffffff", dark ? "#140f1d" : "#d9d2e4", dark ? 1.1 : 1.35]} />
        <directionalLight position={[-5, 9, 6]} intensity={dark ? 1.5 : 1.9} castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004}
          shadow-camera-left={-shadowBox} shadow-camera-right={shadowBox} shadow-camera-top={shadowBox} shadow-camera-bottom={-shadowBox} shadow-camera-far={40} />
        <mesh rotation-x={-Math.PI / 2} position-y={-0.001} receiveShadow>
          <planeGeometry args={[80, 80]} />
          <shadowMaterial transparent opacity={dark ? MODEL.dark.shadow : MODEL.light.shadow} />
        </mesh>
        {children}
        <OrbitControls makeDefault enabled={fine} enableZoom={false} enablePan={false} enableDamping={!still} dampingFactor={0.08} rotateSpeed={0.5}
          minAzimuthAngle={THREE.MathUtils.degToRad(fit.az || 0) - turn} maxAzimuthAngle={THREE.MathUtils.degToRad(fit.az || 0) + turn}
          minPolarAngle={0.35} maxPolarAngle={1.3} />
        <Fit w={fit.w} d={fit.d} el={fit.el} az={fit.az || 0} target={fit.target} reset={reset} />
        <Projector labels={labels} nodes={nodes} />
      </Canvas>
      <div className="labels">
        {labels.map((l) => <div key={l.key} className="lbl" ref={(el) => { if (el) nodes.current.set(l.key, el); else nodes.current.delete(l.key); }}>{l.node}</div>)}
      </div>
    </div>
  );
}
