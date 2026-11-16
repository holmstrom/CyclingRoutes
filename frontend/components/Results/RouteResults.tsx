"use client";

import { useState } from "react";
import type { RouteAlternative, WindInfo } from "@/lib/types";
import ElevationChart from "./ElevationChart";
import RouteComparison from "./RouteComparison";
import { getGpxDownloadUrl } from "@/lib/api";

const ROUTE_COLORS = ["#3b82f6", "#10b981", "#f59e0b"];
const ROUTE_LABELS = ["Route A", "Route B", "Route C"];

const ROAD_TYPE_COLORS: Record<string, string> = {
  cycleway: "#22c55e",
  residential: "#60a5fa",
  tertiary: "#a78bfa",
  tertiary_link: "#a78bfa",
  secondary: "#f59e0b",
  secondary_link: "#f59e0b",
  unclassified: "#6b7280",
  living_street: "#34d399",
  service: "#9ca3af",
  primary: "#ef4444",
  primary_link: "#ef4444",
};

// Wind direction arrow: points where wind is GOING (opposite of meteorological "from")
function windArrow(deg: number): string {
  // Meteorological convention: deg = direction wind comes FROM
  // We show where it goes TO = deg + 180
  const arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"];
  return arrows[Math.round(((deg + 180) % 360) / 45) % 8];
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

interface RouteResultsProps {
  routes: RouteAlternative[];
  selectedIndex: number;
  onSelectRoute: (index: number) => void;
  avgSpeed: number;
  onAvgSpeedChange: (speed: number) => void;
  hoveredDistanceKm: number | null;
  onChartHover: (km: number | null) => void;
  activeHillIndex: number | null;
  onPeakClick: (index: number | null) => void;
  wind: WindInfo | null;
}

export default function RouteResults({
  routes,
  selectedIndex,
  onSelectRoute,
  avgSpeed,
  onAvgSpeedChange,
  hoveredDistanceKm,
  onChartHover,
  activeHillIndex,
  onPeakClick,
  wind,
}: RouteResultsProps) {
  const [chartOpen, setChartOpen] = useState(true);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIndex, setCompareIndex] = useState<number>(1);

  if (routes.length === 0) return null;

  const selected = routes[selectedIndex];

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]">
      {/* Elevation Chart (collapsible) */}
      {chartOpen && selected && (
        <div className="mx-4 mb-2 h-40 rounded-xl bg-gray-900/85 backdrop-blur-xl border border-white/10 overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">
              Elevation Profile
            </span>
            <button
              onClick={() => setChartOpen(false)}
              className="text-gray-600 hover:text-gray-400 transition text-sm"
            >
              Hide
            </button>
          </div>
          <div className="h-[calc(100%-24px)]">
            <ElevationChart
              profile={selected.elevation_profile}
              routeIndex={selectedIndex}
              highlightKm={hoveredDistanceKm}
              onHover={onChartHover}
              onPeakClick={(idx) => onPeakClick(activeHillIndex === idx ? null : idx)}
              activeHillIndex={activeHillIndex}
            />
          </div>
        </div>
      )}

      {/* Route Tabs + Stats Bar */}
      <div className="mx-4 mb-4 rounded-xl bg-gray-900/85 backdrop-blur-xl border border-white/10 overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-white/5">
          {routes.map((route, i) => (
            <button
              key={route.id}
              onClick={() => onSelectRoute(i)}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-all relative ${
                i === selectedIndex
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{
                    backgroundColor: ROUTE_COLORS[i],
                    opacity: i === selectedIndex ? 1 : 0.4,
                  }}
                />
                <span>{ROUTE_LABELS[i]}</span>
                <span className="text-gray-500 text-sm">{route.distance_km.toFixed(1)} km</span>
              </div>
              {i === selectedIndex && (
                <div
                  className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                  style={{ backgroundColor: ROUTE_COLORS[i] }}
                />
              )}
            </button>
          ))}
          {!chartOpen && (
            <button
              onClick={() => setChartOpen(true)}
              className="px-3 text-sm text-gray-600 hover:text-gray-400 transition"
            >
              Chart
            </button>
          )}
          {routes.length >= 2 && (
            <button
              onClick={() => setCompareMode(!compareMode)}
              className={`px-3 text-sm transition ${
                compareMode ? "text-blue-400" : "text-gray-600 hover:text-gray-400"
              }`}
            >
              Compare
            </button>
          )}
        </div>

        {/* Stats */}
        {selected && (
          <div className="p-3">
            <div className={`grid ${wind ? "grid-cols-5" : "grid-cols-4"} gap-3 text-center mb-3`}>
              <div>
                <div className="text-2xl font-bold text-white">
                  {selected.distance_km.toFixed(1)}
                </div>
                <div className="text-sm text-gray-500">km</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">
                  {selected.elevation_gain_m.toFixed(0)}
                </div>
                <div className="text-sm text-gray-500">m gain</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">
                  {formatDuration(Math.round(selected.distance_km / avgSpeed * 60))}
                </div>
                <div className="text-sm text-gray-500">est. time</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-white">
                  {(selected.quality_score * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-gray-500">quality</div>
              </div>
              {wind && (
                <div>
                  <div className="text-2xl font-bold text-white">
                    {windArrow(wind.direction_deg)} {Math.round(wind.speed_kmh)}
                  </div>
                  <div className="text-sm text-gray-500">km/h wind</div>
                </div>
              )}
            </div>

            {/* Road breakdown bar */}
            <div className="mb-3">
              <div className="flex h-2 rounded-full overflow-hidden bg-white/5">
                {Object.entries(selected.road_breakdown)
                  .filter(([, pct]) => pct >= 1)
                  .map(([type, pct]) => (
                    <div
                      key={type}
                      style={{
                        width: `${pct}%`,
                        backgroundColor:
                          ROAD_TYPE_COLORS[type] || "#4b5563",
                      }}
                      title={`${type}: ${pct.toFixed(1)}%`}
                    />
                  ))}
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5">
                {Object.entries(selected.road_breakdown)
                  .filter(([, pct]) => pct >= 3)
                  .map(([type, pct]) => (
                    <span key={type} className="flex items-center gap-1 text-xs text-gray-500">
                      <span
                        className="w-1.5 h-1.5 rounded-full inline-block"
                        style={{
                          backgroundColor:
                            ROAD_TYPE_COLORS[type] || "#4b5563",
                        }}
                      />
                      {type} {pct.toFixed(0)}%
                    </span>
                  ))}
              </div>
            </div>

            {/* Route comparison */}
            {compareMode && routes.length >= 2 && (
              <div className="mb-3 p-2 rounded-lg bg-white/5 border border-white/5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-gray-500 uppercase tracking-wider">Compare with</span>
                  {routes.map((_, i) => {
                    if (i === selectedIndex) return null;
                    return (
                      <button
                        key={i}
                        onClick={() => setCompareIndex(i)}
                        className={`text-sm px-2.5 py-1 rounded ${
                          compareIndex === i
                            ? "bg-white/10 text-white"
                            : "text-gray-500 hover:text-gray-300"
                        }`}
                      >
                        Route {["A", "B", "C"][i]}
                      </button>
                    );
                  })}
                </div>
                <RouteComparison
                  routes={routes}
                  compareIndices={[selectedIndex, compareIndex === selectedIndex ? (selectedIndex + 1) % routes.length : compareIndex]}
                  avgSpeed={avgSpeed}
                />
              </div>
            )}

            {/* Avg speed + GPX Download */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5">
                <label className="text-sm text-gray-500 whitespace-nowrap">Avg</label>
                <input
                  type="number"
                  min={5}
                  max={50}
                  step={1}
                  value={avgSpeed}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    if (v >= 5 && v <= 50) onAvgSpeedChange(v);
                  }}
                  className="w-12 bg-transparent text-white text-base font-semibold text-center outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <span className="text-sm text-gray-500">km/h</span>
              </div>
              <a
                href={getGpxDownloadUrl(selected.id)}
                download
                className="flex-1 text-center py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm font-medium text-gray-300 hover:bg-white/10 hover:text-white transition"
              >
                Download GPX
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
