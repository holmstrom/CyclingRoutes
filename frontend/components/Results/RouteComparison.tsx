"use client";

import type { RouteAlternative } from "@/lib/types";

const ROUTE_COLORS = ["#3b82f6", "#10b981", "#f59e0b"];
const ROUTE_LABELS = ["A", "B", "C"];

interface RouteComparisonProps {
  routes: RouteAlternative[];
  compareIndices: [number, number];
  avgSpeed: number;
}

function delta(a: number, b: number, decimals = 1): string {
  const diff = b - a;
  const sign = diff > 0 ? "+" : "";
  return `${sign}${diff.toFixed(decimals)}`;
}

function deltaColor(diff: number, lowerIsBetter: boolean): string {
  if (Math.abs(diff) < 0.1) return "text-gray-400";
  const isBetter = lowerIsBetter ? diff < 0 : diff > 0;
  return isBetter ? "text-green-400" : "text-red-400";
}

export default function RouteComparison({
  routes,
  compareIndices,
  avgSpeed,
}: RouteComparisonProps) {
  const [idxA, idxB] = compareIndices;
  const a = routes[idxA];
  const b = routes[idxB];
  if (!a || !b) return null;

  const metrics = [
    {
      label: "Distance",
      unit: "km",
      valA: a.distance_km,
      valB: b.distance_km,
      decimals: 1,
      lowerIsBetter: true,
    },
    {
      label: "Elevation",
      unit: "m",
      valA: a.elevation_gain_m,
      valB: b.elevation_gain_m,
      decimals: 0,
      lowerIsBetter: false, // subjective — cyclists may want more climbing
    },
    {
      label: "Est. Time",
      unit: "min",
      valA: Math.round((a.distance_km / avgSpeed) * 60),
      valB: Math.round((b.distance_km / avgSpeed) * 60),
      decimals: 0,
      lowerIsBetter: true,
    },
    {
      label: "Quality",
      unit: "%",
      valA: a.quality_score * 100,
      valB: b.quality_score * 100,
      decimals: 0,
      lowerIsBetter: false,
    },
    {
      label: "Cycleway",
      unit: "%",
      valA: a.road_breakdown.cycleway ?? 0,
      valB: b.road_breakdown.cycleway ?? 0,
      decimals: 0,
      lowerIsBetter: false,
    },
  ];

  return (
    <div className="space-y-1.5">
      {/* Header */}
      <div className="grid grid-cols-[1fr_70px_70px_80px] gap-1.5 text-xs text-gray-500 uppercase tracking-wider px-1">
        <div />
        <div className="text-center">
          <span
            className="inline-block w-2 h-2 rounded-full mr-1"
            style={{ backgroundColor: ROUTE_COLORS[idxA] }}
          />
          {ROUTE_LABELS[idxA]}
        </div>
        <div className="text-center">
          <span
            className="inline-block w-2 h-2 rounded-full mr-1"
            style={{ backgroundColor: ROUTE_COLORS[idxB] }}
          />
          {ROUTE_LABELS[idxB]}
        </div>
        <div className="text-center">Diff</div>
      </div>

      {/* Metric rows */}
      {metrics.map((m) => {
        const diff = m.valB - m.valA;
        return (
          <div
            key={m.label}
            className="grid grid-cols-[1fr_70px_70px_80px] gap-1.5 items-center px-1"
          >
            <div className="text-sm text-gray-400">{m.label}</div>
            <div className="text-sm text-white text-center font-semibold">
              {m.valA.toFixed(m.decimals)}
            </div>
            <div className="text-sm text-white text-center font-semibold">
              {m.valB.toFixed(m.decimals)}
            </div>
            <div
              className={`text-sm text-center font-semibold ${deltaColor(diff, m.lowerIsBetter)}`}
            >
              {delta(m.valA, m.valB, m.decimals)} {m.unit}
            </div>
          </div>
        );
      })}
    </div>
  );
}
