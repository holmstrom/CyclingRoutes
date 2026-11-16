"use client";

import { useMemo, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
} from "recharts";
import type { ElevationPoint, HillInfo } from "@/lib/types";
import { detectHills } from "@/lib/hills";

const ROUTE_COLORS = ["#3b82f6", "#10b981", "#f59e0b"];

interface ElevationChartProps {
  profile: ElevationPoint[];
  routeIndex: number;
  highlightKm?: number | null;
  onHover?: (distanceKm: number | null) => void;
  onPeakClick?: (hillIndex: number) => void;
  hills?: HillInfo[];
  activeHillIndex?: number | null;
}

export default function ElevationChart({
  profile,
  routeIndex,
  highlightKm,
  onHover,
  onPeakClick,
  hills: externalHills,
  activeHillIndex,
}: ElevationChartProps) {
  const color = ROUTE_COLORS[routeIndex % ROUTE_COLORS.length];
  const gradientId = `elevGrad-${routeIndex}`;

  const hills = useMemo(
    () => externalHills ?? detectHills(profile),
    [profile, externalHills]
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleMouseMove = useCallback((e: any) => {
    if (e?.activePayload?.[0]?.payload) {
      onHover?.(e.activePayload[0].payload.distance_km);
    }
  }, [onHover]);

  const handleMouseLeave = useCallback(() => {
    onHover?.(null);
  }, [onHover]);

  if (!profile || profile.length === 0) return null;

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={profile}
          margin={{ top: 16, right: 16, bottom: 0, left: 0 }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="distance_km"
            tick={{ fill: "#6b7280", fontSize: 10 }}
            axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
            tickLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}`}
          />
          <YAxis
            tick={{ fill: "#6b7280", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={36}
            tickFormatter={(v: number) => `${v.toFixed(0)}`}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(17,24,39,0.95)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 8,
              fontSize: 12,
              color: "#e5e7eb",
            }}
            formatter={(value: number | string | undefined) => {
              const v = typeof value === "number" ? value : Number(value ?? 0);
              return [`${v.toFixed(1)} m`, "Elevation"];
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            labelFormatter={(label: any) => `${Number(label).toFixed(1)} km`}
          />
          <Area
            type="monotone"
            dataKey="elevation_m"
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />

          {/* Vertical reference line synced with map hover */}
          {highlightKm != null && (
            <ReferenceLine
              x={highlightKm}
              stroke="white"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              strokeOpacity={0.7}
            />
          )}

          {/* Hill extent shading for active hill */}
          {activeHillIndex != null && hills[activeHillIndex] && (
            <>
              <ReferenceLine
                x={hills[activeHillIndex].startKm}
                stroke="#f97316"
                strokeWidth={1}
                strokeOpacity={0.5}
              />
              <ReferenceLine
                x={hills[activeHillIndex].endKm}
                stroke="#f97316"
                strokeWidth={1}
                strokeOpacity={0.5}
              />
            </>
          )}

          {/* Hill peak markers */}
          {hills.map((hill, idx) => (
            <ReferenceDot
              key={hill.peakKm}
              x={hill.peakKm}
              y={hill.peakElevation}
              r={activeHillIndex === idx ? 7 : 5}
              fill={activeHillIndex === idx ? "#f97316" : color}
              stroke="white"
              strokeWidth={activeHillIndex === idx ? 2.5 : 1.5}
              style={{ cursor: "pointer" }}
              onClick={() => onPeakClick?.(idx)}
              label={{
                value: `${hill.gainM}m ↑${hill.avgGradientPercent}%`,
                position: "top",
                fill: "#d1d5db",
                fontSize: 9,
                fontWeight: 600,
              }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
