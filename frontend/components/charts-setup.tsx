"use client";
import { Chart, BarElement, CategoryScale, Filler, Legend, LineElement, LinearScale, PointElement, Tooltip, ScatterController, LineController, BarController } from "chart.js";
import { useEffect } from "react";
import { useApp } from "./AppState";

Chart.register(BarElement, CategoryScale, Filler, Legend, LineElement, LinearScale, PointElement, Tooltip, ScatterController, LineController, BarController);

export const cssVar = (v: string) => (typeof window === "undefined" ? "#888" : getComputedStyle(document.documentElement).getPropertyValue(v).trim());

/** Keeps Chart.js defaults in step with the light/dark theme. */
export default function Charts() {
  const { theme } = useApp();
  useEffect(() => {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.color = cssVar("--muted");
    Chart.defaults.borderColor = cssVar("--grid");
    Chart.defaults.maintainAspectRatio = false;
    Object.assign(Chart.defaults.plugins.tooltip, { backgroundColor: cssVar("--ink"), titleColor: cssVar("--surface"), bodyColor: cssVar("--surface"), padding: 10, cornerRadius: 8, displayColors: false });
  }, [theme]);
  return null;
}
