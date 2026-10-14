"use client";
// GSAP set-up, imported only by Overview and the Planner so other pages don't download it.
import gsap from "gsap";

gsap.defaults({ ease: "power3.out", duration: 0.6 });

export { gsap };

export const reduced = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** How much of an opening sequence to play: all of it once per browser session, a short version after, none if motion is reduced. */
export type Opening = "full" | "short" | "none";
export function openingFor(key: string): Opening {
  if (typeof window === "undefined" || reduced()) return "none";
  try { return sessionStorage.getItem("pf.seen." + key) ? "short" : "full"; } catch { return "short"; }
}
export function markSeen(key: string) { try { sessionStorage.setItem("pf.seen." + key, "1"); } catch {} }

/**
 * Animations belonging to an opening sequence. Any click, key or scroll finishes them at once,
 * so the sequence never stands between someone and the page.
 */
const running = new Set<gsap.core.Animation>();
let listening = false;
function finishAll() { running.forEach((a) => a.progress(1)); running.clear(); }
export function skippable<T extends gsap.core.Animation>(a: T): T {
  running.add(a);
  a.eventCallback("onComplete", () => running.delete(a));
  if (!listening && typeof window !== "undefined") {
    listening = true;
    for (const ev of ["pointerdown", "keydown", "wheel", "touchstart"]) window.addEventListener(ev, finishAll, { passive: true });
  }
  return a;
}
